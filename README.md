# CalcinhaShop — Guia Completo de Instalação

## Integração entre os 2 sistemas (Railway)

Objetivo: o site do teu colega regista compras na tua API, o teu stock baixa automaticamente e ambos recebem notificação em tempo real.

### 1) Configurar variáveis no backend (Railway)

No serviço da API, define estas variáveis de ambiente:

- `DB_HOST`
- `DB_PORT` (ex: `3306`)
- `DB_USER`
- `DB_PASSWORD`
- `DB_NAME`
- `INTEGRATION_API_KEY` (uma chave secreta partilhada só entre vocês)

Opcional: podes usar `MYSQL_URL` em vez dos campos `DB_*`.

### 2) Endpoint de compra para o teu colega

Ele deve fazer `POST` para:

`/api/compra`

Headers:

- `Content-Type: application/json`
- `X-API-Key: <INTEGRATION_API_KEY>`

Body de exemplo:

```json
{
  "cliente_nome": "João Silva",
  "cliente_email": "joao@email.com",
  "itens": [
    { "produto_id": 1, "quantidade": 2 },
    { "produto_id": 4, "quantidade": 1 }
  ]
}
```

Se houver stock suficiente:

- debita stock em `produtos`
- cria registo em `vendas`
- cria registos em `venda_itens`
- envia evento websocket `nova_compra`

### 3) Notificações para ambos

Tanto o teu ERP como o site do teu colega devem ligar websocket ao mesmo backend:

`io(BASE_URL, { transports: ['websocket', 'polling'] })`

Eventos emitidos:

- `nova_compra`
- `alerta_stock`

### 4) Verificação rápida de produção

Endpoint para teste:

`GET /api/health`

Deve devolver `{"status":"ok","service":"calcinashop-api"}`.

### 5) Exemplo fetch (lado do teu colega)

```javascript
await fetch('https://SEU_BACKEND/api/compra', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'SUA_CHAVE_PARTILHADA'
  },
  body: JSON.stringify({
    cliente_nome: 'Maria',
    cliente_email: 'maria@email.com',
    itens: [
      { produto_id: 1, quantidade: 1 }
    ]
  })
});
```

---

## PASSO 1 — Base de Dados no XAMPP

### 1.1 Iniciar o XAMPP
1. Abre o **XAMPP Control Panel**
2. Clica **Start** no **Apache**
3. Clica **Start** no **MySQL**
4. Ambos devem ficar a verde ✅

### 1.2 Criar a base de dados
1. Abre o browser e vai a: **http://localhost/phpmyadmin**
2. No menu da esquerda clica em **Novo** (ou "New")
3. No campo "Nome da base de dados" escreve: `calcinashop`
4. Clica **Criar**
5. Agora clica no separador **SQL** (barra do topo)
6. Copia **todo** o conteúdo do ficheiro `database.sql`
7. Cola na caixa de texto e clica **Executar**
8. Deves ver uma mensagem de sucesso a verde ✅

> A base de dados está criada com os produtos de exemplo já inseridos!

---

## PASSO 2 — Instalar dependências Python

Abre o **CMD** na pasta `backend/` e corre:

```
pip install -r requirements.txt
```

---

## PASSO 3 — Arrancar o servidor Flask

No mesmo terminal, corre:

```
python app.py
```

Deves ver:
```
==================================================
  CalcinhaShop API a arrancar...
  http://localhost:5000
==================================================
```

> Deixa este terminal aberto — o servidor tem de estar sempre a correr!

---

## PASSO 4 — Expor com ngrok

Como já tens o ngrok instalado e configurado, é simples.

### 4.1 Abre um SEGUNDO terminal
Não feches o do Flask! Abre outro CMD.

### 4.2 Corre o ngrok
```
ngrok http 5000
```

### 4.3 O que vais ver
```
Session Status   online
Account          o-teu-email@gmail.com
Forwarding       https://abc123xyz.ngrok-free.app -> http://localhost:5000
```

O URL na linha **Forwarding** é o endereço público da tua API.

> O URL muda cada vez que reinicias o ngrok (versão gratuita).
> Tens de partilhar o novo URL com o teu colega sempre que o reiniciares.

### 4.4 Envia ao teu colega
O endpoint que ele vai chamar para registar compras é:
```
https://abc123xyz.ngrok-free.app/api/compra
```

---

## PASSO 5 — Atualizar o URL na tua página da loja

No ficheiro `CalcinhaShop.html`, procura esta linha perto do fim:

```javascript
const API_URL = 'http://localhost:5000';
```

- **Abrindo a loja no teu próprio PC** → deixa como está
- **Abrindo a loja noutro PC** → muda para o URL do ngrok:

```javascript
const API_URL = 'https://abc123xyz.ngrok-free.app';
```

---

## FLUXO COMPLETO

```
PC DO COLEGA                         O TEU PC
┌───────────────────┐           ┌─────────────────────┐
│ Página do Cliente │           │  CalcinhaShop.html  │
│                   │           │  (tua loja)         │
│ faz compra →      │           │                     │
│ POST /api/compra  │──ngrok──▶ │  Flask :5000        │
│                   │           │  MySQL (XAMPP)      │
│ ◀── Resposta OK   │◀──ngrok── │                     │
│                   │           │                     │
│ WebSocket 🛒      │◀──────────│  WebSocket 🛒       │
└───────────────────┘           └─────────────────────┘
```

1. Cliente faz compra na página dele
2. Envia POST para o teu URL ngrok
3. Flask verifica stock e debita na base de dados
4. Flask responde com sucesso (ou erro se sem stock)
5. Ambos recebem notificação WebSocket em tempo real

---

## ENDPOINTS DA API

### GET /api/stock
```
GET https://SEU-NGROK.ngrok-free.app/api/stock
```

### POST /api/compra
```json
{
  "cliente_nome": "João Silva",
  "cliente_email": "joao@email.com",
  "itens": [
    { "produto_id": 1, "quantidade": 2 },
    { "produto_id": 4, "quantidade": 3 }
  ]
}
```

### GET /api/vendas
```
GET https://SEU-NGROK.ngrok-free.app/api/vendas
```

---

## ORDEM DE ARRANQUE (todos os dias)

```
1. XAMPP Control Panel  →  Start Apache  +  Start MySQL
2. Terminal 1           →  python app.py
3. Terminal 2           →  ngrok http 5000
4. Copia o URL ngrok    →  envia ao teu colega
5. Abre CalcinhaShop.html no browser
```
