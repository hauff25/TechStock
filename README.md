# TechStore - Módulo de Checkout e Vendas (CLI)

Projeto desenvolvido para a disciplina e atividade prática da TechStore Informática (Demanda 2026-INV05). É um sistema de linha de comando em Python que gerencia frente de caixa (PDV), faz baixa de estoque com transações ACID no SQLite e separa o que cada perfil (Operador e Gerente) pode fazer.

---

## Como executar

O projeto usa apenas a biblioteca padrão do Python (versão 3.10 ou superior). Não precisa instalar nenhum pacote externo via pip.

No Windows, abra o terminal na pasta do projeto e use:

```bash
# Rodar os testes automatizados da entrega
py main.py --test

# Abrir o sistema interativo
py main.py
```

---

## Usuários de teste cadastrados

O banco já vem com duas contas criadas para homologação:

| E-mail | Senha | Perfil | O que pode fazer |
|---|---|---|---|
| `operador@techstore.com` | `operador123` | OPERADOR | Ver catálogo, montar carrinho, fechar venda e emitir recibo. |
| `gerente@techstore.com` | `gerente123` | GERENTE | Tudo do operador mais: alterar preços, cadastrar produtos, ajustar estoque, cancelar vendas e ver relatórios. |

As senhas ficam salvas com hash SHA-256 no banco de dados.

---

## Passo a passo para testar o sistema

Você pode testar tudo de duas formas: direto pelo script de testes ou navegando pelos menus da CLI.

### Opção 1: Teste rápido automatizado
Execute:
```bash
py main.py --test
```
Esse comando cria um banco temporário e testa sozinho:
1. Criação das 7 tabelas e integridade referencial.
2. Login com hash e bloqueio de rotas para operador.
3. Venda de múltiplos itens com baixa correta de estoque.
4. Tentativa de venda sem estoque suficiente (dispara o rollback e não grava nada).
5. Cancelamento feito por gerente (devolve o estoque e registra auditoria).
6. Recibo com número de pedido, chave SHA-256 e badges de itens físicos e digitais.

---

### Opção 2: Teste manual passo a passo

1. **Entrar como Operador:**
   Execute `py main.py`, digite `operador@techstore.com` e a senha `operador123`.

2. **Testar o bloqueio de permissão (RBAC):**
   No menu principal, tente entrar na opção `[4] Relatórios Financeiros` ou `[5] Cancelamento`. O sistema avisa que o operador não tem acesso a essa parte.

3. **Fazer uma venda com múltiplos itens:**
   - Escolha a opção `[2] Frente de Caixa / PDV`.
   - Adicione 2 unidades da Memória RAM (produto 1).
   - Adicione 1 unidade do Windows 11 Pro (produto 3).
   - Escolha `[4] Fechar Pedido`.
   - Coloque o nome do cliente, o CPF/CNPJ e escolha a forma de pagamento (PIX, Cartão ou Boleto).
   - O pedido fecha, mostra o recibo na tela com as tags `[COMPONENTE FÍSICO]` e `[LICENÇA DIGITAL]`, e grava uma cópia em texto dentro da pasta `recibos/`.

4. **Testar a recusa de venda sem estoque (Rollback ACID):**
   - No PDV, tente colocar 1 Memória RAM e 50 unidades do Switch Dell (o estoque dele é só 2).
   - Ao tentar fechar o pedido, o sistema aborta a operação inteira.
   - O SQLite faz `ROLLBACK`. Nada é salvo em Vendas, nenhum item é registrado e o estoque da Memória RAM não é descontado.

5. **Trocar para a conta de Gerente:**
   - Escolha `[9] Alternar Usuário` e entre com `gerente@techstore.com` e `gerente123`.

6. **Cancelar uma venda e devolver o estoque:**
   - Escolha `[5] Cancelamento / Estorno de Transações`.
   - Digite o número do pedido feito no passo 3.
   - O status da venda muda para `CANCELADA`, as quantidades voltam para o estoque dos produtos e uma entrada de estorno é gravada na tabela `Movimentacoes`.

7. **Conferir relatórios e auditoria:**
   - Opção `[4] Relatórios Financeiros`: mostra o total faturado, cancelamentos e vendas por forma de pagamento.
   - Opção `[6] Auditoria do Livro-Razão`: mostra o histórico de saídas (vendas) e entradas (estornos/cadastros) com data, hora e responsável.

---

## Banco de dados e tabelas

O banco usado é o SQLite (`techstore.db`), com chaves estrangeiras ativadas (`PRAGMA foreign_keys = ON;`).

### Tabelas do projeto:
- `Usuarios`: id, nome_completo, email (único), senha_hash, perfil_acesso (OPERADOR ou GERENTE) e status (ATIVO ou INATIVO).
- `Vendas`: id, numero_pedido (único), data_hora, cliente_nome, cliente_documento, forma_pagamento (PIX, CARTAO_CREDITO, BOLETO_FATURADO), valor_total, status_venda (CONCLUIDA ou CANCELADA) e usuario_id.
- `Itens_Venda`: id, venda_id, produto_id, quantidade_vendida (maior que zero), preco_unitario_praticado (congelado na data da venda) e subtotal_item.
- `Produtos`: id, categoria_id, fornecedor_id, nome, tipo (COMPONENTE_FISICO ou LICENCA_DIGITAL), preco, estoque_atual (não permite valor negativo) e estoque_minimo.
- `Categorias`: id, nome e descricao.
- `Fornecedores`: id, razao_social, cnpj, telefone e email.
- `Movimentacoes`: id, produto_id, tipo_movimentacao (ENTRADA ou SAIDA), quantidade, motivo, data_hora e usuario_id.

### Como a transação ACID funciona no código
Toda a operação de venda roda dentro de um bloco:
1. `conn.execute("BEGIN IMMEDIATE TRANSACTION;")`
2. O sistema checa se cada produto tem estoque suficiente.
3. Se algum item faltar, levanta erro e chama `conn.rollback()`.
4. Se todos tiverem saldo, insere o registro em `Vendas`, os itens em `Itens_Venda`, debita o estoque em `Produtos` e cria as linhas de auditoria em `Movimentacoes`.
5. Executa `conn.commit()`.

---

## Arquivos da entrega

- `main.py`: inicializador do CLI e rotina de testes.
- `database.sql`: criação de todas as tabelas, constraints e dados iniciais.
- `migration_v2.sql`: script SQL de migração e dados de teste.
- `README.md`: documentação e instruções de teste.
- `techstore/`: código modular em Python (database, regras de negócio, modelos, segurança e interface).
- `recibos/`: pasta onde são salvos os arquivos `.txt` das vendas concluídas.
