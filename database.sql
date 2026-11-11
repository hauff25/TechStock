PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Categorias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS Fornecedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    razao_social TEXT NOT NULL,
    cnpj TEXT NOT NULL UNIQUE,
    telefone TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS Produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria_id INTEGER NOT NULL,
    fornecedor_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ('COMPONENTE_FISICO', 'LICENCA_DIGITAL')),
    preco REAL NOT NULL CHECK(preco > 0),
    estoque_atual INTEGER NOT NULL CHECK(estoque_atual >= 0),
    estoque_minimo INTEGER NOT NULL DEFAULT 5,
    FOREIGN KEY (categoria_id) REFERENCES Categorias(id),
    FOREIGN KEY (fornecedor_id) REFERENCES Fornecedores(id)
);

CREATE TABLE IF NOT EXISTS Usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_completo TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil_acesso TEXT NOT NULL CHECK(perfil_acesso IN ('OPERADOR', 'GERENTE')),
    status TEXT NOT NULL CHECK(status IN ('ATIVO', 'INATIVO'))
);

CREATE TABLE IF NOT EXISTS Movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL,
    tipo_movimentacao TEXT NOT NULL CHECK(tipo_movimentacao IN ('ENTRADA', 'SAIDA')),
    quantidade INTEGER NOT NULL CHECK(quantidade > 0),
    motivo TEXT NOT NULL,
    data_hora TEXT NOT NULL,
    usuario_id INTEGER,
    FOREIGN KEY (produto_id) REFERENCES Produtos(id),
    FOREIGN KEY (usuario_id) REFERENCES Usuarios(id)
);

CREATE TABLE IF NOT EXISTS Vendas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_pedido TEXT NOT NULL UNIQUE,
    data_hora TEXT NOT NULL,
    cliente_nome TEXT NOT NULL,
    cliente_documento TEXT NOT NULL,
    forma_pagamento TEXT NOT NULL CHECK(forma_pagamento IN ('PIX', 'CARTAO_CREDITO', 'BOLETO_FATURADO')),
    valor_total REAL NOT NULL CHECK(valor_total >= 0),
    status_venda TEXT NOT NULL CHECK(status_venda IN ('CONCLUIDA', 'CANCELADA')),
    usuario_id INTEGER NOT NULL,
    FOREIGN KEY (usuario_id) REFERENCES Usuarios(id)
);

CREATE TABLE IF NOT EXISTS Itens_Venda (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venda_id INTEGER NOT NULL,
    produto_id INTEGER NOT NULL,
    quantidade_vendida INTEGER NOT NULL CHECK(quantidade_vendida > 0),
    preco_unitario_praticado REAL NOT NULL CHECK(preco_unitario_praticado > 0),
    subtotal_item REAL NOT NULL CHECK(subtotal_item > 0),
    FOREIGN KEY (venda_id) REFERENCES Vendas(id) ON DELETE CASCADE,
    FOREIGN KEY (produto_id) REFERENCES Produtos(id)
);

INSERT OR IGNORE INTO Categorias (id, nome, descricao) VALUES
(1, 'Hardware & Componentes', 'Componentes físicos de computadores e servidores'),
(2, 'Licenciamento Corporativo', 'Softwares empresariais e licenças digitais OEM/FPP'),
(3, 'Redes & Conectividade', 'Switches, roteadores e equipamentos de infraestrutura');

INSERT OR IGNORE INTO Fornecedores (id, razao_social, cnpj, telefone, email) VALUES
(1, 'Dell Computadores do Brasil Ltda', '72.381.189/0001-10', '(11) 4004-0100', 'contato@dell.com.br'),
(2, 'Microsoft Informática Ltda', '60.316.817/0001-03', '(11) 4706-0900', 'comercial@microsoft.com'),
(3, 'Kingston Technology do Brasil', '04.606.324/0001-85', '(11) 3652-5200', 'vendas@kingston.com.br');

INSERT OR IGNORE INTO Usuarios (id, nome_completo, email, senha_hash, perfil_acesso, status) VALUES
(1, 'Operador TechStore', 'operador@techstore.com', '1725165c9a0b3698a3d01016e0d8205155820b8d7f21835ca64c0f81c728d880', 'OPERADOR', 'ATIVO'),
(2, 'Gerente Geral TechStore', 'gerente@techstore.com', 'ecfba551324356e5bd27b548adf36b728783f60d9b573d142caac7baad62be49', 'GERENTE', 'ATIVO');

INSERT OR IGNORE INTO Produtos (id, categoria_id, fornecedor_id, nome, tipo, preco, estoque_atual, estoque_minimo) VALUES
(1, 1, 3, 'Memória RAM DDR4 16GB 3200MHz Kingston Fury', 'COMPONENTE_FISICO', 289.90, 20, 5),
(2, 1, 3, 'SSD NVMe M.2 1TB Kingston KC3000 PCIe 4.0', 'COMPONENTE_FISICO', 549.00, 15, 5),
(3, 2, 2, 'Licença Windows 11 Pro Corporativo FPP Digital', 'LICENCA_DIGITAL', 890.00, 10, 3),
(4, 2, 2, 'Licença Microsoft 365 Business Standard Anual', 'LICENCA_DIGITAL', 680.00, 25, 5),
(5, 3, 1, 'Switch Gigabit 24 Portas Gerenciável Dell PowerConnect', 'COMPONENTE_FISICO', 2490.00, 2, 1),
(6, 1, 1, 'Placa de Vídeo RTX 4060 8GB GDDR6', 'COMPONENTE_FISICO', 2199.00, 4, 2);

INSERT OR IGNORE INTO Vendas (id, numero_pedido, data_hora, cliente_nome, cliente_documento, forma_pagamento, valor_total, status_venda, usuario_id) VALUES
(1, 'PED-2026-0001', '2026-11-10 14:30:00', 'Tech Solutions Consultoria ME', '12.345.678/0001-90', 'BOLETO_FATURADO', 1469.80, 'CONCLUIDA', 1);

INSERT OR IGNORE INTO Itens_Venda (id, venda_id, produto_id, quantidade_vendida, preco_unitario_praticado, subtotal_item) VALUES
(1, 1, 1, 2, 289.90, 579.80),
(2, 1, 3, 1, 890.00, 890.00);

INSERT OR IGNORE INTO Movimentacoes (id, produto_id, tipo_movimentacao, quantidade, motivo, data_hora, usuario_id) VALUES
(1, 1, 'SAIDA', 2, 'Venda PED-2026-0001', '2026-11-10 14:30:00', 1),
(2, 3, 'SAIDA', 1, 'Venda PED-2026-0001', '2026-11-10 14:30:00', 1);
