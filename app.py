from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import mysql.connector
from datetime import datetime
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.config['SECRET_KEY'] = 'calcinashop_secret_2024'
CORS(app, origins="*", allow_headers=["Content-Type", "Authorization", "X-API-Key", "ngrok-skip-browser-warning"])

@app.after_request
def after_request(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key, ngrok-skip-browser-warning"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    return jsonify({'erro': str(error)}), 500


socketio = SocketIO(app, cors_allowed_origins="*")

# ── CONFIGURAÇÃO DA BASE DE DADOS ──
# Lê variáveis de ambiente para facilitar deploy no Railway/Render/etc.
def env_first(*names, default=None):
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def build_db_config():
    mysql_url = env_first('MYSQL_URL', 'DATABASE_URL')
    if mysql_url:
        parsed = urlparse(mysql_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 3306,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/'),
        }

    return {
        'host': env_first('DB_HOST', 'MYSQLHOST', default='localhost'),
        'port': int(env_first('DB_PORT', 'MYSQLPORT', default='3306')),
        'user': env_first('DB_USER', 'MYSQLUSER', default='root'),
        'password': env_first('DB_PASSWORD', 'MYSQLPASSWORD', default=''),
        'database': env_first('DB_NAME', 'MYSQLDATABASE', default='calcinashop'),
    }


DB_CONFIG = build_db_config()
INTEGRATION_API_KEY = os.getenv('INTEGRATION_API_KEY', '').strip()
SCHEMA_READY = False

SAMPLE_PRODUCTS = [
    ('Nike Air Max 270', 'NK-AM270-001', 'Nike', 42, 18, 149.90),
    ('Adidas Ultraboost 22', 'AD-UB22-045', 'Adidas', 40, 3, 189.00),
    ('New Balance 550', 'NB-550-NY', 'New Balance', 43, 0, 120.00),
    ('Puma Suede Classic', 'PU-SD-BK', 'Puma', 41, 24, 85.00),
    ('Nike Dunk Low Retro', 'NK-DL-RET', 'Nike', 44, 12, 109.99),
    ('Adidas Forum Mid', 'AD-FM-WHT', 'Adidas', 41, 8, 120.00),
    ('Puma RS-X Efekt', 'PU-RSX-EF', 'Puma', 43, 2, 135.00),
]


def ensure_database_schema(db):
    global SCHEMA_READY

    if SCHEMA_READY:
        return

    cursor = db.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nome VARCHAR(150) NOT NULL,
                sku VARCHAR(50) NOT NULL UNIQUE,
                marca VARCHAR(80),
                tamanho INT,
                stock INT NOT NULL DEFAULT 0,
                preco DECIMAL(10,2) NOT NULL,
                estado ENUM('em_stock','baixo_stock','esgotado')
                    GENERATED ALWAYS AS (
                        CASE
                            WHEN stock = 0 THEN 'esgotado'
                            WHEN stock <= 5 THEN 'baixo_stock'
                            ELSE 'em_stock'
                        END
                    ) STORED
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cliente_nome VARCHAR(150),
                cliente_email VARCHAR(150),
                total DECIMAL(10,2) NOT NULL,
                data_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS venda_itens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                venda_id INT NOT NULL,
                produto_id INT NOT NULL,
                quantidade INT NOT NULL,
                preco_unitario DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (venda_id) REFERENCES vendas(id),
                FOREIGN KEY (produto_id) REFERENCES produtos(id)
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM produtos")
        total_produtos = cursor.fetchone()[0]

        if total_produtos == 0:
            cursor.executemany(
                """
                INSERT INTO produtos (nome, sku, marca, tamanho, stock, preco)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                SAMPLE_PRODUCTS,
            )

        db.commit()
        SCHEMA_READY = True
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()

def get_db():
    db = mysql.connector.connect(**DB_CONFIG)
    ensure_database_schema(db)
    return db


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check simples para monitorização no Railway."""
    return jsonify({'status': 'ok', 'service': 'calcinashop-api'})


# ══════════════════════════════════════
#  STOCK
# ══════════════════════════════════════

@app.route('/api/stock', methods=['GET'])
def get_stock():
    """Devolve todo o stock"""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM produtos ORDER BY nome")
        produtos = cursor.fetchall()
        cursor.close(); db.close()
        return jsonify(produtos)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@app.route('/api/stock/<int:produto_id>', methods=['GET'])
def get_produto(produto_id):
    """Devolve um produto específico"""
    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM produtos WHERE id = %s", (produto_id,))
        produto = cursor.fetchone()
        cursor.close(); db.close()
        if not produto:
            return jsonify({'erro': 'Produto não encontrado'}), 404
        return jsonify(produto)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


# ══════════════════════════════════════
#  COMPRAS — endpoint principal
# ══════════════════════════════════════

@app.route('/api/compra', methods=['POST'])
def registar_compra():
    """
    O software do cliente chama este endpoint quando faz uma compra.

    Body JSON esperado:
    {
        "cliente_nome": "João Silva",
        "cliente_email": "joao@email.com",
        "itens": [
            {"produto_id": 1, "quantidade": 2},
            {"produto_id": 3, "quantidade": 1}
        ]
    }
    """
    # Se definida, exige chave de integração para aceitar compras.
    if INTEGRATION_API_KEY:
        received_key = request.headers.get('X-API-Key', '').strip()
        if received_key != INTEGRATION_API_KEY:
            return jsonify({'erro': 'Não autorizado'}), 401

    data = request.get_json()

    # Validação básica
    if not data or 'itens' not in data or not data['itens']:
        return jsonify({'erro': 'Dados inválidos. É necessário "itens".'}), 400

    db = get_db()
    cursor = db.cursor(dictionary=True)

    try:
        total = 0.0
        itens_detalhes = []

        # Verificar stock para todos os itens antes de debitar
        for item in data['itens']:
            pid = item.get('produto_id')
            qty = item.get('quantidade')

            if not isinstance(pid, int) or not isinstance(qty, int) or qty <= 0:
                db.rollback()
                return jsonify({
                    'erro': 'Item inválido. Use produto_id (int) e quantidade (int > 0).'
                }), 400

            cursor.execute("SELECT * FROM produtos WHERE id = %s FOR UPDATE", (pid,))
            produto = cursor.fetchone()

            if not produto:
                db.rollback()
                return jsonify({'erro': f'Produto ID {pid} não existe'}), 404

            if produto['stock'] < qty:
                db.rollback()
                return jsonify({
                    'erro': f'Stock insuficiente para "{produto["nome"]}"',
                    'stock_disponivel': produto['stock'],
                    'quantidade_pedida': qty
                }), 409

            subtotal = produto['preco'] * qty
            total += subtotal
            itens_detalhes.append({
                'produto_id': pid,
                'nome': produto['nome'],
                'preco_unitario': produto['preco'],
                'quantidade': qty,
                'subtotal': subtotal,
                'stock_antes': produto['stock'],
                'stock_depois': produto['stock'] - qty
            })

        # Debitar stock
        for item in itens_detalhes:
            cursor.execute(
                "UPDATE produtos SET stock = stock - %s WHERE id = %s",
                (item['quantidade'], item['produto_id'])
            )

        # Registar venda
        cursor.execute(
            """INSERT INTO vendas (cliente_nome, cliente_email, total, data_hora)
               VALUES (%s, %s, %s, %s)""",
            (
                data.get('cliente_nome', 'Desconhecido'),
                data.get('cliente_email', ''),
                total,
                datetime.now()
            )
        )
        venda_id = cursor.lastrowid

        # Registar itens da venda
        for item in itens_detalhes:
            cursor.execute(
                """INSERT INTO venda_itens (venda_id, produto_id, quantidade, preco_unitario)
                   VALUES (%s, %s, %s, %s)""",
                (venda_id, item['produto_id'], item['quantidade'], item['preco_unitario'])
            )

        db.commit()

        # ── NOTIFICAÇÃO EM TEMPO REAL ──
        notificacao = {
            'venda_id': venda_id,
            'cliente_nome': data.get('cliente_nome', 'Desconhecido'),
            'cliente_email': data.get('cliente_email', ''),
            'total': total,
            'itens': itens_detalhes,
            'data_hora': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        }
        # Envia para todos os clientes WebSocket ligados (tua loja + software do colega)
        socketio.emit('nova_compra', notificacao)

        # Alerta se algum produto ficou com stock baixo
        for item in itens_detalhes:
            if item['stock_depois'] <= 5:
                socketio.emit('alerta_stock', {
                    'produto_id': item['produto_id'],
                    'nome': item['nome'],
                    'stock_restante': item['stock_depois'],
                    'urgente': item['stock_depois'] <= 2
                })

        return jsonify({
            'sucesso': True,
            'venda_id': venda_id,
            'total': total,
            'itens': itens_detalhes,
            'mensagem': f'Compra #{venda_id} registada com sucesso!'
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'erro': str(e)}), 500
    finally:
        cursor.close()
        db.close()


# ══════════════════════════════════════
#  VENDAS — histórico
# ══════════════════════════════════════

@app.route('/api/vendas', methods=['GET'])
def get_vendas():
    """Devolve histórico de vendas"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT v.*, 
               GROUP_CONCAT(p.nome SEPARATOR ', ') as produtos
        FROM vendas v
        LEFT JOIN venda_itens vi ON v.id = vi.venda_id
        LEFT JOIN produtos p ON vi.produto_id = p.id
        GROUP BY v.id
        ORDER BY v.data_hora DESC
        LIMIT 100
    """)
    vendas = cursor.fetchall()
    cursor.close(); db.close()
    return jsonify(vendas)


# ══════════════════════════════════════
#  WEBSOCKET — eventos
# ══════════════════════════════════════

@socketio.on('connect')
def on_connect():
    print(f'[WS] Cliente ligado: {request.sid}')
    emit('ligado', {'mensagem': 'Ligado ao CalcinhaShop em tempo real!'})

@socketio.on('disconnect')
def on_disconnect():
    print(f'[WS] Cliente desligado: {request.sid}')


# ══════════════════════════════════════
#  ARRANQUE
# ══════════════════════════════════════

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    print("=" * 50)
    print("  CalcinhaShop API a arrancar...")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    socketio.run(app, host='0.0.0.0', port=port, debug=debug_mode, allow_unsafe_werkzeug=True)
