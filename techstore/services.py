import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

from techstore.database import Database
from techstore.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    InsufficientStockError,
    SaleNotFoundError,
    ValidationError
)
from techstore.models import (
    User,
    Product,
    CartItem,
    Sale,
    SaleItem,
    MovementAudit
)
from techstore.security import (
    hash_password,
    verify_password,
    generate_receipt_signature
)

class AuthService:
    def __init__(self, db: Database):
        self.db = db

    def authenticate(self, email: str, raw_password: str) -> User:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome_completo, email, senha_hash, perfil_acesso, status FROM Usuarios WHERE email = ?",
                (email.strip().lower(),)
            )
            row = cursor.fetchone()
            if not row:
                raise AuthenticationError("Usuário ou senha inválidos.")
            if row["status"] != "ATIVO":
                raise AuthenticationError("Acesso negado: Este usuário está inativo no sistema.")
            if not verify_password(raw_password, row["senha_hash"]):
                raise AuthenticationError("Usuário ou senha inválidos.")
            return User(
                id=row["id"],
                nome_completo=row["nome_completo"],
                email=row["email"],
                perfil_acesso=row["perfil_acesso"],
                status=row["status"]
            )
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nome_completo, email, perfil_acesso, status FROM Usuarios WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return User(
                id=row["id"],
                nome_completo=row["nome_completo"],
                email=row["email"],
                perfil_acesso=row["perfil_acesso"],
                status=row["status"]
            )
        finally:
            conn.close()

    def list_users(self, actor: User) -> List[User]:
        if not actor.is_gerente:
            raise PermissionDeniedError("Apenas gerentes podem visualizar a lista completa de usuários.")
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome_completo, email, perfil_acesso, status FROM Usuarios ORDER BY id")
            return [
                User(
                    id=row["id"],
                    nome_completo=row["nome_completo"],
                    email=row["email"],
                    perfil_acesso=row["perfil_acesso"],
                    status=row["status"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def create_user(self, actor: User, nome_completo: str, email: str, raw_password: str, perfil_acesso: str) -> User:
        if not actor.is_gerente:
            raise PermissionDeniedError("Apenas gerentes podem cadastrar novos colaboradores.")
        perfil = perfil_acesso.strip().upper()
        if perfil not in ("OPERADOR", "GERENTE"):
            raise ValidationError("Perfil de acesso inválido. Use OPERADOR ou GERENTE.")
        if len(raw_password) < 6:
            raise ValidationError("A senha deve ter no mínimo 6 caracteres.")
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO Usuarios (nome_completo, email, senha_hash, perfil_acesso, status) VALUES (?, ?, ?, ?, 'ATIVO')",
                (nome_completo.strip(), email.strip().lower(), hash_password(raw_password), perfil)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return User(
                id=user_id,
                nome_completo=nome_completo.strip(),
                email=email.strip().lower(),
                perfil_acesso=perfil,
                status="ATIVO"
            )
        finally:
            conn.close()

class CatalogService:
    def __init__(self, db: Database):
        self.db = db

    def list_products(self) -> List[Product]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.categoria_id, p.fornecedor_id, p.nome, p.tipo, p.preco, p.estoque_atual, p.estoque_minimo,
                       c.nome AS categoria_nome, f.razao_social AS fornecedor_nome
                FROM Produtos p
                LEFT JOIN Categorias c ON p.categoria_id = c.id
                LEFT JOIN Fornecedores f ON p.fornecedor_id = f.id
                ORDER BY p.id
            """)
            return [
                Product(
                    id=row["id"],
                    categoria_id=row["categoria_id"],
                    fornecedor_id=row["fornecedor_id"],
                    nome=row["nome"],
                    tipo=row["tipo"],
                    preco=row["preco"],
                    estoque_atual=row["estoque_atual"],
                    estoque_minimo=row["estoque_minimo"],
                    categoria_nome=row["categoria_nome"],
                    fornecedor_nome=row["fornecedor_nome"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def get_product(self, product_id: int) -> Optional[Product]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.categoria_id, p.fornecedor_id, p.nome, p.tipo, p.preco, p.estoque_atual, p.estoque_minimo,
                       c.nome AS categoria_nome, f.razao_social AS fornecedor_nome
                FROM Produtos p
                LEFT JOIN Categorias c ON p.categoria_id = c.id
                LEFT JOIN Fornecedores f ON p.fornecedor_id = f.id
                WHERE p.id = ?
            """, (product_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Product(
                id=row["id"],
                categoria_id=row["categoria_id"],
                fornecedor_id=row["fornecedor_id"],
                nome=row["nome"],
                tipo=row["tipo"],
                preco=row["preco"],
                estoque_atual=row["estoque_atual"],
                estoque_minimo=row["estoque_minimo"],
                categoria_nome=row["categoria_nome"],
                fornecedor_nome=row["fornecedor_nome"]
            )
        finally:
            conn.close()

    def create_product(
        self,
        actor: User,
        categoria_id: int,
        fornecedor_id: int,
        nome: str,
        tipo: str,
        preco: float,
        estoque_inicial: int,
        estoque_minimo: int = 5
    ) -> Product:
        if not actor.is_gerente:
            raise PermissionDeniedError("Operadores não têm autorização para cadastrar novos produtos.")
        tipo_normalizado = tipo.strip().upper()
        if tipo_normalizado not in ("COMPONENTE_FISICO", "LICENCA_DIGITAL"):
            raise ValidationError("Tipo de produto deve ser COMPONENTE_FISICO ou LICENCA_DIGITAL.")
        if preco <= 0:
            raise ValidationError("O preço de venda deve ser estritamente maior que zero.")
        if estoque_inicial < 0:
            raise ValidationError("O estoque inicial não pode ser negativo.")

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Produtos (categoria_id, fornecedor_id, nome, tipo, preco, estoque_atual, estoque_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (categoria_id, fornecedor_id, nome.strip(), tipo_normalizado, preco, estoque_inicial, estoque_minimo))
            product_id = cursor.lastrowid

            if estoque_inicial > 0:
                data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO Movimentacoes (produto_id, tipo_movimentacao, quantidade, motivo, data_hora, usuario_id)
                    VALUES (?, 'ENTRADA', ?, 'Carga de estoque inicial no cadastro', ?, ?)
                """, (product_id, estoque_inicial, data_hora, actor.id))

            conn.commit()
            return Product(
                id=product_id,
                categoria_id=categoria_id,
                fornecedor_id=fornecedor_id,
                nome=nome.strip(),
                tipo=tipo_normalizado,
                preco=preco,
                estoque_atual=estoque_inicial,
                estoque_minimo=estoque_minimo
            )
        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            conn.close()

    def update_product_price(self, actor: User, product_id: int, novo_preco: float) -> Product:
        if not actor.is_gerente:
            raise PermissionDeniedError("Operadores não têm permissão para alterar o preço base de catálogo.")
        if novo_preco <= 0:
            raise ValidationError("O novo preço deve ser estritamente maior que zero.")

        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE Produtos SET preco = ? WHERE id = ?", (novo_preco, product_id))
            if cursor.rowcount == 0:
                raise ValidationError(f"Produto ID {product_id} não encontrado.")
            conn.commit()
            return self.get_product(product_id)
        finally:
            conn.close()

    def adjust_stock(self, actor: User, product_id: int, quantidade: int, tipo_movimento: str, motivo: str) -> Product:
        if not actor.is_gerente:
            raise PermissionDeniedError("Operadores não têm permissão para efetuar ajustes manuais de estoque.")
        tipo_norm = tipo_movimento.strip().upper()
        if tipo_norm not in ("ENTRADA", "SAIDA"):
            raise ValidationError("Tipo de movimentação deve ser ENTRADA ou SAIDA.")
        if quantidade <= 0:
            raise ValidationError("Quantidade de ajuste deve ser maior que zero.")

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            cursor = conn.cursor()
            cursor.execute("SELECT id, estoque_atual FROM Produtos WHERE id = ?", (product_id,))
            row = cursor.fetchone()
            if not row:
                raise ValidationError(f"Produto ID {product_id} não encontrado.")

            atual = row["estoque_atual"]
            if tipo_norm == "SAIDA":
                if atual < quantidade:
                    raise InsufficientStockError(f"Estoque atual ({atual}) é insuficiente para debitar {quantidade}.")
                novo_saldo = atual - quantidade
            else:
                novo_saldo = atual + quantidade

            cursor.execute("UPDATE Produtos SET estoque_atual = ? WHERE id = ?", (novo_saldo, product_id))
            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO Movimentacoes (produto_id, tipo_movimentacao, quantidade, motivo, data_hora, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (product_id, tipo_norm, quantidade, motivo.strip(), data_hora, actor.id))

            conn.commit()
            return self.get_product(product_id)
        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            conn.close()

class SaleService:
    def __init__(self, db: Database):
        self.db = db

    def checkout(
        self,
        actor: User,
        cliente_nome: str,
        cliente_documento: str,
        forma_pagamento: str,
        cart_items: List[CartItem]
    ) -> Tuple[Sale, List[SaleItem]]:
        if not cart_items:
            raise ValidationError("O carrinho está vazio. Adicione itens antes de fechar o pedido.")

        nome = cliente_nome.strip()
        doc = cliente_documento.strip()
        if not nome:
            raise ValidationError("O nome do cliente é obrigatório.")
        if not doc:
            raise ValidationError("O documento CPF/CNPJ do cliente é obrigatório.")

        forma = forma_pagamento.strip().upper()
        if forma not in ("PIX", "CARTAO_CREDITO", "BOLETO_FATURADO"):
            raise ValidationError("Forma de pagamento inválida. Escolha PIX, CARTAO_CREDITO ou BOLETO_FATURADO.")

        total_pedido = round(sum(item.subtotal for item in cart_items), 2)
        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sufixo = uuid.uuid4().hex[:6].upper()
        numero_pedido = f"PED-{datetime.now().strftime('%Y%m%d')}-{sufixo}"

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            cursor = conn.cursor()

            for item in cart_items:
                cursor.execute(
                    "SELECT id, nome, tipo, preco, estoque_atual FROM Produtos WHERE id = ?",
                    (item.product_id,)
                )
                prod = cursor.fetchone()
                if not prod:
                    raise ValidationError(f"Produto ID {item.product_id} não existe no cadastro.")
                if prod["estoque_atual"] < item.quantidade:
                    raise InsufficientStockError(
                        f"Estoque insuficiente para '{prod['nome']}' (ID {item.product_id}). "
                        f"Estoque disponível: {prod['estoque_atual']} unidade(s). "
                        f"Quantidade solicitada no carrinho: {item.quantidade} unidade(s)."
                    )

            cursor.execute("""
                INSERT INTO Vendas (numero_pedido, data_hora, cliente_nome, cliente_documento, forma_pagamento, valor_total, status_venda, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, 'CONCLUIDA', ?)
            """, (numero_pedido, data_hora, nome, doc, forma, total_pedido, actor.id))
            venda_id = cursor.lastrowid

            itens_confirmados: List[SaleItem] = []

            for item in cart_items:
                cursor.execute("""
                    INSERT INTO Itens_Venda (venda_id, produto_id, quantidade_vendida, preco_unitario_praticado, subtotal_item)
                    VALUES (?, ?, ?, ?, ?)
                """, (venda_id, item.product_id, item.quantidade, item.preco_unitario, item.subtotal))
                item_venda_id = cursor.lastrowid

                cursor.execute("""
                    UPDATE Produtos
                    SET estoque_atual = estoque_atual - ?
                    WHERE id = ?
                """, (item.quantidade, item.product_id))

                cursor.execute("""
                    INSERT INTO Movimentacoes (produto_id, tipo_movimentacao, quantidade, motivo, data_hora, usuario_id)
                    VALUES (?, 'SAIDA', ?, ?, ?, ?)
                """, (item.product_id, item.quantidade, f"Venda {numero_pedido}", data_hora, actor.id))

                itens_confirmados.append(
                    SaleItem(
                        id=item_venda_id,
                        venda_id=venda_id,
                        produto_id=item.product_id,
                        quantidade_vendida=item.quantidade,
                        preco_unitario_praticado=item.preco_unitario,
                        subtotal_item=item.subtotal,
                        produto_nome=item.nome,
                        tipo=item.tipo
                    )
                )

            conn.commit()

            venda = Sale(
                id=venda_id,
                numero_pedido=numero_pedido,
                data_hora=data_hora,
                cliente_nome=nome,
                cliente_documento=doc,
                forma_pagamento=forma,
                valor_total=total_pedido,
                status_venda="CONCLUIDA",
                usuario_id=actor.id,
                usuario_nome=actor.nome_completo
            )

            return venda, itens_confirmados

        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            conn.close()

    def get_sale_by_number(self, numero_pedido: str) -> Tuple[Sale, List[SaleItem]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.numero_pedido, v.data_hora, v.cliente_nome, v.cliente_documento,
                       v.forma_pagamento, v.valor_total, v.status_venda, v.usuario_id, u.nome_completo AS usuario_nome
                FROM Vendas v
                LEFT JOIN Usuarios u ON v.usuario_id = u.id
                WHERE v.numero_pedido = ?
            """, (numero_pedido.strip(),))
            row = cursor.fetchone()
            if not row:
                raise SaleNotFoundError(f"Venda com número '{numero_pedido}' não encontrada.")

            sale = Sale(
                id=row["id"],
                numero_pedido=row["numero_pedido"],
                data_hora=row["data_hora"],
                cliente_nome=row["cliente_nome"],
                cliente_documento=row["cliente_documento"],
                forma_pagamento=row["forma_pagamento"],
                valor_total=row["valor_total"],
                status_venda=row["status_venda"],
                usuario_id=row["usuario_id"],
                usuario_nome=row["usuario_nome"]
            )

            cursor.execute("""
                SELECT iv.id, iv.venda_id, iv.produto_id, iv.quantidade_vendida, iv.preco_unitario_praticado, iv.subtotal_item,
                       p.nome AS produto_nome, p.tipo
                FROM Itens_Venda iv
                LEFT JOIN Produtos p ON iv.produto_id = p.id
                WHERE iv.venda_id = ?
                ORDER BY iv.id
            """, (sale.id,))

            items = [
                SaleItem(
                    id=irow["id"],
                    venda_id=irow["venda_id"],
                    produto_id=irow["produto_id"],
                    quantidade_vendida=irow["quantidade_vendida"],
                    preco_unitario_praticado=irow["preco_unitario_praticado"],
                    subtotal_item=irow["subtotal_item"],
                    produto_nome=irow["produto_nome"],
                    tipo=irow["tipo"]
                )
                for irow in cursor.fetchall()
            ]

            return sale, items
        finally:
            conn.close()

    def list_sales(self, limit: int = 50) -> List[Sale]:
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT v.id, v.numero_pedido, v.data_hora, v.cliente_nome, v.cliente_documento,
                       v.forma_pagamento, v.valor_total, v.status_venda, v.usuario_id, u.nome_completo AS usuario_nome
                FROM Vendas v
                LEFT JOIN Usuarios u ON v.usuario_id = u.id
                ORDER BY v.id DESC
                LIMIT ?
            """, (limit,))
            return [
                Sale(
                    id=row["id"],
                    numero_pedido=row["numero_pedido"],
                    data_hora=row["data_hora"],
                    cliente_nome=row["cliente_nome"],
                    cliente_documento=row["cliente_documento"],
                    forma_pagamento=row["forma_pagamento"],
                    valor_total=row["valor_total"],
                    status_venda=row["status_venda"],
                    usuario_id=row["usuario_id"],
                    usuario_nome=row["usuario_nome"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def cancel_sale(self, actor: User, numero_pedido: str, motivo: str = "Cancelamento homologado pela gerencia") -> Sale:
        if not actor.is_gerente:
            raise PermissionDeniedError("Apenas usuários com perfil GERENTE possuem autorização para cancelar transações.")

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, numero_pedido, status_venda FROM Vendas WHERE numero_pedido = ?
            """, (numero_pedido.strip(),))
            row = cursor.fetchone()
            if not row:
                raise SaleNotFoundError(f"Venda '{numero_pedido}' não encontrada.")
            if row["status_venda"] == "CANCELADA":
                raise ValidationError(f"A venda '{numero_pedido}' já se encontra cancelada.")

            venda_id = row["id"]
            cursor.execute("UPDATE Vendas SET status_venda = 'CANCELADA' WHERE id = ?", (venda_id,))

            cursor.execute("""
                SELECT produto_id, quantidade_vendida FROM Itens_Venda WHERE venda_id = ?
            """, (venda_id,))
            itens = cursor.fetchall()

            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for it in itens:
                cursor.execute("""
                    UPDATE Produtos
                    SET estoque_atual = estoque_atual + ?
                    WHERE id = ?
                """, (it["quantidade_vendida"], it["produto_id"]))

                cursor.execute("""
                    INSERT INTO Movimentacoes (produto_id, tipo_movimentacao, quantidade, motivo, data_hora, usuario_id)
                    VALUES (?, 'ENTRADA', ?, ?, ?, ?)
                """, (it["produto_id"], it["quantidade_vendida"], f"Estorno / Cancelamento {numero_pedido}: {motivo}", data_hora, actor.id))

            conn.commit()
            sale, _ = self.get_sale_by_number(numero_pedido)
            return sale
        except Exception as exc:
            conn.rollback()
            raise exc
        finally:
            conn.close()

class ReportService:
    def __init__(self, db: Database):
        self.db = db

    def get_financial_summary(self, actor: User) -> Dict[str, Any]:
        if not actor.is_gerente:
            raise PermissionDeniedError("Apenas gerentes possuem permissão para emitir relatórios financeiros.")

        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(*) AS total_pedidos,
                    COALESCE(SUM(CASE WHEN status_venda = 'CONCLUIDA' THEN valor_total ELSE 0 END), 0) AS faturamento_liquido,
                    COALESCE(SUM(CASE WHEN status_venda = 'CANCELADA' THEN valor_total ELSE 0 END), 0) AS valor_estornado,
                    COALESCE(SUM(CASE WHEN status_venda = 'CONCLUIDA' THEN 1 ELSE 0 END), 0) AS concluidas,
                    COALESCE(SUM(CASE WHEN status_venda = 'CANCELADA' THEN 1 ELSE 0 END), 0) AS canceladas
                FROM Vendas
            """)
            geral = cursor.fetchone()

            cursor.execute("""
                SELECT forma_pagamento, COUNT(*) AS qtd, COALESCE(SUM(valor_total), 0) AS total
                FROM Vendas
                WHERE status_venda = 'CONCLUIDA'
                GROUP BY forma_pagamento
            """)
            pagamentos = [dict(row) for row in cursor.fetchall()]

            cursor.execute("""
                SELECT p.id, p.nome, p.tipo, SUM(iv.quantidade_vendida) AS total_unidades, SUM(iv.subtotal_item) AS total_faturado
                FROM Itens_Venda iv
                JOIN Vendas v ON iv.venda_id = v.id
                JOIN Produtos p ON iv.produto_id = p.id
                WHERE v.status_venda = 'CONCLUIDA'
                GROUP BY p.id, p.nome, p.tipo
                ORDER BY total_unidades DESC
                LIMIT 10
            """)
            top_produtos = [dict(row) for row in cursor.fetchall()]

            return {
                "faturamento_liquido": geral["faturamento_liquido"],
                "valor_estornado": geral["valor_estornado"],
                "total_pedidos": geral["total_pedidos"],
                "concluidas": geral["concluidas"],
                "canceladas": geral["canceladas"],
                "por_forma_pagamento": pagamentos,
                "top_produtos": top_produtos
            }
        finally:
            conn.close()

    def get_audit_log(self, actor: User, limit: int = 50) -> List[MovementAudit]:
        if not actor.is_gerente:
            raise PermissionDeniedError("Apenas gerentes possuem permissão para auditar o livro-razão de estoque.")

        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.produto_id, m.tipo_movimentacao, m.quantidade, m.motivo, m.data_hora, m.usuario_id,
                       p.nome AS produto_nome, u.nome_completo AS usuario_nome
                FROM Movimentacoes m
                LEFT JOIN Produtos p ON m.produto_id = p.id
                LEFT JOIN Usuarios u ON m.usuario_id = u.id
                ORDER BY m.id DESC
                LIMIT ?
            """, (limit,))
            return [
                MovementAudit(
                    id=row["id"],
                    produto_id=row["produto_id"],
                    tipo_movimentacao=row["tipo_movimentacao"],
                    quantidade=row["quantidade"],
                    motivo=row["motivo"],
                    data_hora=row["data_hora"],
                    usuario_id=row["usuario_id"],
                    produto_nome=row["produto_nome"],
                    usuario_nome=row["usuario_nome"]
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

class ReceiptFormatter:
    @staticmethod
    def format_receipt(sale: Sale, items: List[SaleItem]) -> str:
        signature = generate_receipt_signature(
            sale.numero_pedido,
            sale.data_hora,
            sale.valor_total,
            sale.cliente_documento
        )

        linhas = []
        largura = 78
        sep_duplo = "=" * largura
        sep_simples = "-" * largura

        linhas.append(sep_duplo)
        linhas.append("TECHSTORE INFORMATICA & SERVICOS CORPORATIVOS".center(largura))
        linhas.append("COMPROVANTE FORMAL DE FATURAMENTO / ORDEM DE VENDA".center(largura))
        linhas.append("Demanda Tecnica: DEMANDA-2026-INV05 | Modulo de Checkout ACID".center(largura))
        linhas.append(sep_duplo)
        linhas.append(f" PEDIDO: {sale.numero_pedido:<35} STATUS: {sale.status_venda}")
        linhas.append(f" DATA/HORA: {sale.data_hora:<32} FORMA PGTO: {sale.forma_pagamento}")
        linhas.append(f" OPERADOR: {sale.usuario_nome or ('ID ' + str(sale.usuario_id))}")
        linhas.append(f" CLIENTE: {sale.cliente_nome}")
        linhas.append(f" DOCUMENTO: {sale.cliente_documento}")
        linhas.append(sep_simples)
        linhas.append(f" {'ITEM / DESCRICAO':<38} {'TIPO':<18} {'QTD':>4} {'UNIT (R$)':>10} {'SUBTOTAL':>10}")
        linhas.append(sep_simples)

        for item in items:
            nome_truncado = (item.produto_nome or "Produto")[:36]
            tipo_label = item.tipo_badge
            linhas.append(
                f" {nome_truncado:<38} {tipo_label:<18} {item.quantidade_vendida:>4} "
                f"{item.preco_unitario_praticado:>10.2f} {item.subtotal_item:>10.2f}"
            )

        linhas.append(sep_simples)
        total_str = f"R$ {sale.valor_total:.2f}"
        linhas.append(f" VALOR TOTAL DA TRANSACAO:{total_str:>53}")
        linhas.append(sep_duplo)
        linhas.append(" CHAVE DE AUTENTICIDADE E INTEGRIDADE:")
        linhas.append(f" {signature}")
        linhas.append(sep_duplo)
        linhas.append(" Documento gerado com garantia transacional estrita (ACID).".center(largura))
        linhas.append(sep_duplo)

        return "\n".join(linhas)

    @staticmethod
    def save_receipt_to_file(sale: Sale, receipt_text: str, directory: str = "recibos") -> str:
        pasta = Path(directory)
        pasta.mkdir(parents=True, exist_ok=True)
        arquivo = pasta / f"recibo_{sale.numero_pedido}.txt"
        arquivo.write_text(receipt_text, encoding="utf-8")
        return str(arquivo.resolve())
