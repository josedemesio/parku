-- Cria o banco de dados
CREATE DATABASE IF NOT EXISTS parku;

-- Seleciona o banco de dados
USE parku;

-- Cria a tabela de registros de entrada/saída de veículos
CREATE TABLE IF NOT EXISTS registros (
    id INT AUTO_INCREMENT PRIMARY KEY,
    placa VARCHAR(10) NOT NULL,
    modelo VARCHAR(50),
    horario_entrada DATETIME NOT NULL,
    horario_saida DATETIME,
    tempo_permanencia TIME,
    valor_total DECIMAL(10, 2),
    UNIQUE (placa, horario_entrada)
);

-- Cria a tabela de configurações do sistema (como o valor da hora)
CREATE TABLE IF NOT EXISTS configuracoes (
    id INT PRIMARY KEY,
    valor_hora DECIMAL(10, 2) NOT NULL
);

-- Insere um valor padrão para o valor da hora na tabela de configurações
INSERT INTO configuracoes (id, valor_hora) VALUES (1, 10.00)
ON DUPLICATE KEY UPDATE valor_hora = VALUES(valor_hora);