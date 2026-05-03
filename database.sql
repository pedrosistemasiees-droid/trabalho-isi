-- ══════════════════════════════════════════════
--  CalcinhaShop — Base de Dados
--  Colar no phpMyAdmin > SQL
-- ══════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS calcinashop
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE calcinashop;

-- ── PRODUTOS ──
CREATE TABLE IF NOT EXISTS produtos (
  id       INT AUTO_INCREMENT PRIMARY KEY,
  nome     VARCHAR(150)   NOT NULL,
  sku      VARCHAR(50)    NOT NULL UNIQUE,
  marca    VARCHAR(80),
  tamanho  INT,
  stock    INT            NOT NULL DEFAULT 0,
  preco    DECIMAL(10,2)  NOT NULL,
  estado   ENUM('em_stock','baixo_stock','esgotado') 
           GENERATED ALWAYS AS (
             CASE
               WHEN stock = 0 THEN 'esgotado'
               WHEN stock <= 5 THEN 'baixo_stock'
               ELSE 'em_stock'
             END
           ) STORED
);

-- ── VENDAS ──
CREATE TABLE IF NOT EXISTS vendas (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  cliente_nome   VARCHAR(150),
  cliente_email  VARCHAR(150),
  total          DECIMAL(10,2) NOT NULL,
  data_hora      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── ITENS DE CADA VENDA ──
CREATE TABLE IF NOT EXISTS venda_itens (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  venda_id       INT            NOT NULL,
  produto_id     INT            NOT NULL,
  quantidade     INT            NOT NULL,
  preco_unitario DECIMAL(10,2)  NOT NULL,
  FOREIGN KEY (venda_id)   REFERENCES vendas(id),
  FOREIGN KEY (produto_id) REFERENCES produtos(id)
);

-- ── DADOS DE EXEMPLO ──
INSERT INTO produtos (nome, sku, marca, tamanho, stock, preco) VALUES
  ('Nike Air Max 270',    'NK-AM270-001', 'Nike',        42, 18, 149.90),
  ('Adidas Ultraboost 22','AD-UB22-045',  'Adidas',      40,  3, 189.00),
  ('New Balance 550',     'NB-550-NY',    'New Balance',  43,  0, 120.00),
  ('Puma Suede Classic',  'PU-SD-BK',     'Puma',        41, 24,  85.00),
  ('Nike Dunk Low Retro', 'NK-DL-RET',    'Nike',        44, 12, 109.99),
  ('Adidas Forum Mid',    'AD-FM-WHT',    'Adidas',      41,  8, 120.00),
  ('Puma RS-X Efekt',     'PU-RSX-EF',    'Puma',        43,  2, 135.00);
