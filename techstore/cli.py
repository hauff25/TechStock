import getpass
import os
import sys
from typing import List, Optional

from techstore.database import Database
from techstore.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    InsufficientStockError,
    SaleNotFoundError,
    ValidationError
)
from techstore.models import User, Product, CartItem
from techstore.services import (
    AuthService,
    CatalogService,
    SaleService,
    ReportService,
    ReceiptFormatter
)

class TechStoreCLI:
    def __init__(self, db: Database):
        self.db = db
        self.auth_service = AuthService(db)
        self.catalog_service = CatalogService(db)
        self.sale_service = SaleService(db)
        self.report_service = ReportService(db)
        self.current_user: Optional[User] = None
        self.cart: List[CartItem] = []

    def pause(self) -> None:
        input("\nPressione [ENTER] para continuar...")

    def banner(self, titulo: str) -> None:
        largura = 78
        print("\n" + "=" * largura)
        print(f" TECHSTORE CHECKOUT & GESTAO COMERCIAL B2B | {titulo}".center(largura))
        print("=" * largura)

    def print_alert_error(self, titulo: str, mensagem: str) -> None:
        largura = 78
        print("\n" + "!" * largura)
        print(f" [ALERTA DE ERRO] {titulo}".center(largura))
        print("-" * largura)
        print(f" {mensagem}")
        print("!" * largura)

    def print_alert_success(self, mensagem: str) -> None:
        largura = 78
        print("\n" + "*" * largura)
        print(f" [SUCESSO] {mensagem}".center(largura))
        print("*" * largura)

    def login_loop(self) -> bool:
        while True:
            self.banner("AUTENTICACAO & CONTROLE DE ACESSO (RBAC)")
            print(" Contas padrão pré-configuradas para homologação:")
            print("  - Operador: operador@techstore.com | Senha: operador123")
            print("  - Gerente : gerente@techstore.com  | Senha: gerente123")
            print("-" * 78)
            email = input(" E-mail corporativo (ou 'sair' para encerrar): ").strip()
            if email.lower() in ("sair", "exit", "q"):
                return False

            try:
                senha = getpass.getpass(" Senha de acesso: ")
            except Exception:
                senha = input(" Senha de acesso: ")

            try:
                user = self.auth_service.authenticate(email, senha)
                self.current_user = user
                self.cart = []
                self.print_alert_success(f"Bem-vindo(a), {user.nome_completo}! Perfil: [{user.perfil_acesso}]")
                return True
            except AuthenticationError as exc:
                self.print_alert_error("FALHA NA AUTENTICACAO", str(exc))
                self.pause()

    def run(self) -> None:
        while True:
            if not self.current_user:
                if not self.login_loop():
                    print("\nEncerrando sistema TechStore. Ate logo!\n")
                    sys.exit(0)

            self.render_main_menu()

    def render_main_menu(self) -> None:
        largura = 78
        print("\n" + "=" * largura)
        user_info = f"USUARIO: {self.current_user.nome_completo} | PERFIL: [{self.current_user.perfil_acesso}]"
        print(f" {user_info:<55} ITENS NO CARRINHO: {len(self.cart):>2}")
        print("=" * largura)
        print(" OPERACOES GERAIS & FRENTE DE CAIXA:")
        print("  [1] Consultar Catalogo de Produtos e Licencas")
        print("  [2] Frente de Caixa / PDV (Montar Carrinho e Checkout ACID)")
        print("  [3] Consultar Vendas e Emitir Comprovante / Recibo")
        print("-" * 78)
        print(" MODULO EXECUTIVO & GESTAO RESTRITA (REQUER PERFIL GERENTE):")
        print("  [4] Relatorios Financeiros e Faturamento Corporativo")
        print("  [5] Cancelamento / Estorno de Transacoes com Devolucao de Estoque")
        print("  [6] Auditoria do Livro-Razao de Movimentacoes (Estoque)")
        print("  [7] Gestao de Catalogo (Novo Produto / Preco / Ajuste de Estoque)")
        print("  [8] Gestao de Usuarios e Acessos")
        print("-" * 78)
        print(" SISTEMA:")
        print("  [9] Alternar Usuario (Logout)")
        print("  [0] Sair do Sistema")
        print("=" * largura)

        opcao = input(" Escolha uma opcao: ").strip()

        if opcao == "1":
            self.view_catalog()
        elif opcao == "2":
            self.pdv_menu()
        elif opcao == "3":
            self.view_sales()
        elif opcao == "4":
            self.handle_financial_reports()
        elif opcao == "5":
            self.handle_cancel_sale()
        elif opcao == "6":
            self.handle_audit_log()
        elif opcao == "7":
            self.handle_catalog_management()
        elif opcao == "8":
            self.handle_user_management()
        elif opcao == "9":
            self.current_user = None
            self.cart = []
        elif opcao == "0":
            print("\nEncerrando TechStore CLI. Operacoes finalizadas com seguranca.\n")
            sys.exit(0)
        else:
            self.print_alert_error("OPCAO INVALIDA", "Por favor, selecione uma opcao valida do menu.")
            self.pause()

    def view_catalog(self) -> None:
        self.banner("CATALOGO DE PRODUTOS E LICENCAS DISPONIVEIS")
        produtos = self.catalog_service.list_products()
        if not produtos:
            print(" Nenhum produto cadastrado.")
            self.pause()
            return

        print(f" {'ID':<4} {'NOME':<36} {'TIPO':<20} {'PRECO (R$)':>10} {'ESTOQUE':>8}")
        print("-" * 82)
        for p in produtos:
            status_estoque = f"{p.estoque_atual} un"
            if p.estoque_atual <= p.estoque_minimo:
                status_estoque += " (!)"
            print(f" {p.id:<4} {p.nome[:35]:<36} {p.tipo_badge:<20} {p.preco:>10.2f} {status_estoque:>8}")
        print("-" * 82)
        print(" Legenda: (!) Estoque igual ou abaixo do minimo operacional.")
        self.pause()

    def pdv_menu(self) -> None:
        while True:
            total_carrinho = sum(i.subtotal for i in self.cart)
            self.banner(f"PDV / TERMINAL DE VENDAS (TOTAL: R$ {total_carrinho:.2f})")

            if not self.cart:
                print(" O carrinho esta atualmente VAZIO.")
            else:
                print(f" {'N':<3} {'ID':<4} {'DESCRICAO':<32} {'TIPO':<18} {'QTD':>4} {'UNIT':>9} {'SUBTOTAL':>9}")
                print("-" * 82)
                for idx, item in enumerate(self.cart, start=1):
                    print(
                        f" {idx:<3} {item.product_id:<4} {item.nome[:30]:<32} {item.tipo_badge:<18} "
                        f"{item.quantidade:>4} {item.preco_unitario:>9.2f} {item.subtotal:>9.2f}"
                    )
                print("-" * 82)
                print(f" TOTAL PARCIAL DO CARRINHO:{'R$ ' + f'{total_carrinho:.2f}':>54}")

            print("\n Acoes do PDV:")
            print("  [1] Adicionar produto ao carrinho")
            print("  [2] Remover item do carrinho")
            print("  [3] Esvaziar carrinho")
            print("  [4] Fechar Pedido (Confirmar Checkout Transacional ACID)")
            print("  [0] Retornar ao Menu Principal")

            escolha = input("\n Selecione a acao do PDV: ").strip()

            if escolha == "1":
                self.add_item_to_cart()
            elif escolha == "2":
                self.remove_item_from_cart()
            elif escolha == "3":
                self.cart = []
                self.print_alert_success("Carrinho esvaziado com sucesso.")
            elif escolha == "4":
                if self.execute_acid_checkout():
                    break
            elif escolha == "0":
                break
            else:
                self.print_alert_error("OPCAO INVALIDA", "Selecione uma opcao valida do PDV.")

    def add_item_to_cart(self) -> None:
        produtos = self.catalog_service.list_products()
        print("\n" + "-" * 78)
        print(f" {'ID':<4} {'NOME':<38} {'TIPO':<18} {'PRECO':>10} {'ESTOQUE':>6}")
        print("-" * 78)
        for p in produtos:
            print(f" {p.id:<4} {p.nome[:36]:<38} {p.tipo_badge:<18} {p.preco:>10.2f} {p.estoque_atual:>6}")
        print("-" * 78)

        entrada_id = input(" Digite o ID do produto desejado (ou 0 para cancelar): ").strip()
        if not entrada_id.isdigit() or int(entrada_id) == 0:
            return

        prod_id = int(entrada_id)
        produto = self.catalog_service.get_product(prod_id)
        if not produto:
            self.print_alert_error("PRODUTO NAO ENCONTRADO", f"Nao existe produto cadastrado com o ID {prod_id}.")
            self.pause()
            return

        entrada_qtd = input(f" Quantidade desejada para '{produto.nome}' (Estoque atual: {produto.estoque_atual}): ").strip()
        if not entrada_qtd.isdigit() or int(entrada_qtd) <= 0:
            self.print_alert_error("QUANTIDADE INVALIDA", "A quantidade deve ser um numero inteiro estritamente positivo.")
            self.pause()
            return

        qtd = int(entrada_qtd)

        item_existente = next((it for it in self.cart if it.product_id == prod_id), None)
        if item_existente:
            item_existente.quantidade += qtd
        else:
            self.cart.append(
                CartItem(
                    product_id=produto.id,
                    nome=produto.nome,
                    tipo=produto.tipo,
                    preco_unitario=produto.preco,
                    quantidade=qtd
                )
            )

        self.print_alert_success(f"Item '{produto.nome}' ({qtd}x) adicionado ao carrinho com sucesso.")

    def remove_item_from_cart(self) -> None:
        if not self.cart:
            self.print_alert_error("CARRINHO VAZIO", "Nao ha itens no carrinho para remover.")
            self.pause()
            return

        pos = input(" Digite o numero ordinal do item da lista que deseja remover: ").strip()
        if not pos.isdigit():
            return
        idx = int(pos)
        if 1 <= idx <= len(self.cart):
            removido = self.cart.pop(idx - 1)
            self.print_alert_success(f"Item '{removido.nome}' removido do carrinho.")
        else:
            self.print_alert_error("INDICE INVALIDO", "Indice de item inexistente no carrinho.")
            self.pause()

    def execute_acid_checkout(self) -> bool:
        if not self.cart:
            self.print_alert_error("CARRINHO VAZIO", "Nao e possivel finalizar uma transacao sem itens no carrinho.")
            self.pause()
            return False

        total = sum(i.subtotal for i in self.cart)
        self.banner("CONFIRMACAO DE CHECKOUT TRANSACIONAL (ACID)")
        print(f" Total de itens distintos: {len(self.cart)}")
        print(f" Valor Total da Venda   : R$ {total:.2f}")
        print("-" * 78)

        cliente_nome = input(" Nome do Cliente / Razao Social: ").strip()
        if not cliente_nome:
            self.print_alert_error("DADO OBRIGATORIO", "O nome do cliente deve ser informado.")
            self.pause()
            return False

        cliente_doc = input(" Documento do Cliente (CPF ou CNPJ): ").strip()
        if not cliente_doc:
            self.print_alert_error("DADO OBRIGATORIO", "O documento do cliente deve ser informado.")
            self.pause()
            return False

        print("\n Formas de Pagamento Homologadas:")
        print("  [1] PIX")
        print("  [2] CARTAO_CREDITO")
        print("  [3] BOLETO_FATURADO")
        escolha_pgto = input(" Selecione a forma de pagamento (1/2/3): ").strip()

        mapa_pgto = {
            "1": "PIX",
            "2": "CARTAO_CREDITO",
            "3": "BOLETO_FATURADO"
        }

        forma_pagamento = mapa_pgto.get(escolha_pgto)
        if not forma_pagamento:
            self.print_alert_error("PAGAMENTO INVALIDO", "Selecione uma das opcoes de pagamento validas.")
            self.pause()
            return False

        print("\n" + "=" * 78)
        print(" INICIANDO TRANSACAO EXPLÍCITA DE BANCO DE DADOS (BEGIN TRANSACTION)...")
        print("=" * 78)

        try:
            sale, items = self.sale_service.checkout(
                actor=self.current_user,
                cliente_nome=cliente_nome,
                cliente_documento=cliente_doc,
                forma_pagamento=forma_pagamento,
                cart_items=self.cart
            )

            print("\n COMMIT REALIZADO COM SUCESSO! Transacao persistida de forma atomica.")
            receipt_text = ReceiptFormatter.format_receipt(sale, items)
            print("\n" + receipt_text)

            arquivo_salvo = ReceiptFormatter.save_receipt_to_file(sale, receipt_text)
            print(f"\n [ARQUIVO DE COMPROVANTE GERADO]: {arquivo_salvo}")

            self.cart = []
            self.pause()
            return True

        except InsufficientStockError as exc:
            largura = 78
            print("\n" + "X" * largura)
            print(" [FALHA TRANSACIONAL - ROLLBACK EXECUTADO COM SUCESSO]".center(largura))
            print(" CLAUSULA DE ABORTO ACID ATIVADA: NENHUM DADO FOI GRAVADO NO BANCO".center(largura))
            print("-" * largura)
            print(f" Motivo da Reversao:\n {exc}")
            print("-" * largura)
            print(" Integridade Assegurada: As tabelas Vendas, Itens_Venda, Produtos e")
            print(" Movimentacoes foram restauradas ao estado exato anterior a tentativa.")
            print("X" * largura)
            self.pause()
            return False

        except Exception as exc:
            print("\n" + "X" * 78)
            print(" [ERRO TRANSACIONAL INESPERADO - ROLLBACK EXECUTADO]")
            print(f" Detalhes do erro: {exc}")
            print("X" * 78)
            self.pause()
            return False

    def view_sales(self) -> None:
        self.banner("CONSULTA DE VENDAS REALIZADAS E EMISSAO DE COMPROVANTE")
        sales = self.sale_service.list_sales(limit=30)
        if not sales:
            print(" Nenhuma venda registrada no sistema.")
            self.pause()
            return

        print(f" {'PEDIDO':<22} {'DATA/HORA':<20} {'CLIENTE':<22} {'STATUS':<10} {'TOTAL (R$)':>10}")
        print("-" * 88)
        for s in sales:
            print(f" {s.numero_pedido:<22} {s.data_hora:<20} {s.cliente_nome[:20]:<22} {s.status_venda:<10} {s.valor_total:>10.2f}")
        print("-" * 88)

        numero = input("\n Digite o numero do pedido para visualizar o comprovante formal (ou ENTER para voltar): ").strip()
        if not numero:
            return

        try:
            sale, items = self.sale_service.get_sale_by_number(numero)
            receipt_text = ReceiptFormatter.format_receipt(sale, items)
            print("\n" + receipt_text)

            salvar = input("\n Deseja salvar/atualizar arquivo de impressao deste comprovante? (s/n): ").strip().lower()
            if salvar == "s":
                caminho = ReceiptFormatter.save_receipt_to_file(sale, receipt_text)
                self.print_alert_success(f"Arquivo salvo com sucesso em: {caminho}")

            self.pause()
        except SaleNotFoundError as exc:
            self.print_alert_error("NAO ENCONTRADO", str(exc))
            self.pause()

    def handle_financial_reports(self) -> None:
        try:
            summary = self.report_service.get_financial_summary(self.current_user)
        except PermissionDeniedError as exc:
            self.print_alert_error("BLOQUEIO DE SEGURANCA RBAC", str(exc))
            self.pause()
            return

        self.banner("RELATORIO FINANCEIRO CONSOLIDADO E FATURAMENTO")
        print(f" Total de Pedidos Processados : {summary['total_pedidos']}")
        print(f" Vendas Concluidas com Sucesso: {summary['concluidas']}")
        print(f" Vendas Canceladas / Estornadas: {summary['canceladas']}")
        print(f" Faturamento Liquido Efetuado : R$ {summary['faturamento_liquido']:.2f}")
        print(f" Total em Valores Estornados  : R$ {summary['valor_estornado']:.2f}")
        print("-" * 78)
        print(" Faturamento por Meio de Pagamento:")
        for fp in summary["por_forma_pagamento"]:
            print(f"  - {fp['forma_pagamento']:<20}: {fp['qtd']:>3} pedido(s) | Total: R$ {fp['total']:.2f}")
        print("-" * 78)
        print(" Produtos Mais Vendidos:")
        for prod in summary["top_produtos"]:
            badge = "[LICENCA]" if prod["tipo"] == "LICENCA_DIGITAL" else "[COMPONENTE]"
            print(f"  - {badge:<13} {prod['nome'][:34]:<35} : {prod['total_unidades']:>4} un | R$ {prod['total_faturado']:.2f}")
        print("=" * 78)
        self.pause()

    def handle_cancel_sale(self) -> None:
        if not self.current_user.is_gerente:
            self.print_alert_error(
                "BLOQUEIO DE SEGURANCA RBAC",
                "Apenas usuarios com perfil GERENTE possuem prerrogativa para cancelamento e estorno de vendas."
            )
            self.pause()
            return

        self.banner("CANCELAMENTO E ESTORNO DE TRANSACOES COM REPOSICAO DE ESTOQUE")
        sales = [s for s in self.sale_service.list_sales(limit=20) if s.status_venda == "CONCLUIDA"]
        if not sales:
            print(" Nenhuma venda ativa apta a cancelamento encontrada.")
            self.pause()
            return

        print(f" {'PEDIDO':<22} {'DATA/HORA':<20} {'CLIENTE':<22} {'TOTAL (R$)':>10}")
        print("-" * 78)
        for s in sales:
            print(f" {s.numero_pedido:<22} {s.data_hora:<20} {s.cliente_nome[:20]:<22} {s.valor_total:>10.2f}")
        print("-" * 78)

        pedido = input(" Digite o numero do pedido a ser CANCELADO (ou ENTER para cancelar): ").strip()
        if not pedido:
            return

        motivo = input(" Digite a justificativa formal para a auditoria do estorno: ").strip()
        if not motivo:
            motivo = "Cancelamento homologado pela gerencia comercial"

        confirmacao = input(f" Confirmar cancelamento transacional do pedido {pedido}? (s/n): ").strip().lower()
        if confirmacao != "s":
            print(" Operacao abortada pelo usuario.")
            self.pause()
            return

        try:
            sale = self.sale_service.cancel_sale(self.current_user, pedido, motivo)
            self.print_alert_success(
                f"Pedido {sale.numero_pedido} CANCELADO COM SUCESSO!\n"
                f" Estoque restituido integralmente e registro de auditoria gravado no livro-razao."
            )
            self.pause()
        except Exception as exc:
            self.print_alert_error("FALHA NO CANCELAMENTO", str(exc))
            self.pause()

    def handle_audit_log(self) -> None:
        try:
            logs = self.report_service.get_audit_log(self.current_user, limit=40)
        except PermissionDeniedError as exc:
            self.print_alert_error("BLOQUEIO DE SEGURANCA RBAC", str(exc))
            self.pause()
            return

        self.banner("LIVRO-RAZAO & AUDITORIA DE MOVIMENTACOES DE ESTOQUE")
        if not logs:
            print(" Nenhuma movimentacao registrada.")
            self.pause()
            return

        print(f" {'ID':<4} {'DATA/HORA':<20} {'TIPO':<8} {'QTD':>4} {'PRODUTO':<26} {'RESPONSAVEL':<14}")
        print("-" * 88)
        for log in logs:
            resp = (log.usuario_nome or f"ID {log.usuario_id}")[:13]
            prod = (log.produto_nome or f"Prod {log.produto_id}")[:25]
            print(f" {log.id:<4} {log.data_hora:<20} {log.tipo_movimentacao:<8} {log.quantidade:>4} {prod:<26} {resp:<14}")
        print("-" * 88)
        self.pause()

    def handle_catalog_management(self) -> None:
        if not self.current_user.is_gerente:
            self.print_alert_error(
                "BLOQUEIO DE SEGURANCA RBAC",
                "Apenas usuarios com perfil GERENTE podem alterar o catalogo de produtos."
            )
            self.pause()
            return

        self.banner("GESTAO DE CATALOGO E PRECOS (ACESSO GERENCIAL)")
        print("  [1] Cadastrar Novo Produto ou Licenca")
        print("  [2] Atualizar Preco Base de Catalogo")
        print("  [3] Ajustar Estoque Manualmente (Entrada/Saida Avulsa)")
        print("  [0] Voltar")

        opcao = input("\n Escolha uma opcao: ").strip()

        if opcao == "1":
            self.create_product_flow()
        elif opcao == "2":
            self.update_price_flow()
        elif opcao == "3":
            self.adjust_stock_flow()

    def create_product_flow(self) -> None:
        print("\n Cadastro de Novo Produto / Licenca:")
        nome = input(" Nome do Produto: ").strip()
        if not nome:
            self.print_alert_error("ERRO", "Nome obrigatorio.")
            self.pause()
            return

        print(" Tipos disponiveis:")
        print("  [1] COMPONENTE_FISICO")
        print("  [2] LICENCA_DIGITAL")
        t_opt = input(" Selecione o tipo (1/2): ").strip()
        tipo = "COMPONENTE_FISICO" if t_opt == "1" else ("LICENCA_DIGITAL" if t_opt == "2" else "")
        if not tipo:
            self.print_alert_error("ERRO", "Tipo invalido.")
            self.pause()
            return

        try:
            preco = float(input(" Preco de Venda (R$): ").strip().replace(",", "."))
            estoque = int(input(" Quantidade Inicial em Estoque: ").strip())
        except ValueError:
            self.print_alert_error("ERRO", "Preco ou estoque em formato numerico invalido.")
            self.pause()
            return

        try:
            p = self.catalog_service.create_product(
                actor=self.current_user,
                categoria_id=1 if tipo == "COMPONENTE_FISICO" else 2,
                fornecedor_id=1,
                nome=nome,
                tipo=tipo,
                preco=preco,
                estoque_inicial=estoque
            )
            self.print_alert_success(f"Produto '{p.nome}' (ID {p.id}) cadastrado com sucesso!")
            self.pause()
        except Exception as exc:
            self.print_alert_error("FALHA NO CADASTRO", str(exc))
            self.pause()

    def update_price_flow(self) -> None:
        self.view_catalog()
        id_str = input("\n Digite o ID do produto cujo preco deseja alterar: ").strip()
        if not id_str.isdigit():
            return
        prod_id = int(id_str)
        try:
            novo_preco = float(input(" Digite o novo preco base (R$): ").strip().replace(",", "."))
            p = self.catalog_service.update_product_price(self.current_user, prod_id, novo_preco)
            self.print_alert_success(f"Preco do produto '{p.nome}' atualizado para R$ {p.preco:.2f} com sucesso!")
            self.pause()
        except Exception as exc:
            self.print_alert_error("FALHA NA ALTERACAO", str(exc))
            self.pause()

    def adjust_stock_flow(self) -> None:
        self.view_catalog()
        id_str = input("\n Digite o ID do produto para ajuste de estoque: ").strip()
        if not id_str.isdigit():
            return
        prod_id = int(id_str)
        print(" Tipo de ajuste: [1] ENTRADA  [2] SAIDA")
        t_ajuste = input(" Escolha: ").strip()
        tipo_mov = "ENTRADA" if t_ajuste == "1" else ("SAIDA" if t_ajuste == "2" else "")
        if not tipo_mov:
            self.print_alert_error("ERRO", "Tipo de ajuste invalido.")
            self.pause()
            return

        try:
            qtd = int(input(" Quantidade: ").strip())
        except ValueError:
            self.print_alert_error("ERRO", "Quantidade invalida.")
            self.pause()
            return

        motivo = input(" Motivo / Justificativa do ajuste: ").strip()
        if not motivo:
            motivo = "Ajuste manual de inventario autorizado pela gerencia"

        try:
            p = self.catalog_service.adjust_stock(self.current_user, prod_id, qtd, tipo_mov, motivo)
            self.print_alert_success(f"Estoque de '{p.nome}' ajustado com sucesso. Saldo atual: {p.estoque_atual} un.")
            self.pause()
        except Exception as exc:
            self.print_alert_error("FALHA NO AJUSTE", str(exc))
            self.pause()

    def handle_user_management(self) -> None:
        if not self.current_user.is_gerente:
            self.print_alert_error(
                "BLOQUEIO DE SEGURANCA RBAC",
                "Apenas usuarios com perfil GERENTE podem gerenciar contas de colaboradores."
            )
            self.pause()
            return

        self.banner("GESTAO DE USUARIOS E EQUIPE (RBAC)")
        usuarios = self.auth_service.list_users(self.current_user)
        print(f" {'ID':<4} {'NOME':<30} {'EMAIL':<30} {'PERFIL':<12} {'STATUS':<8}")
        print("-" * 88)
        for u in usuarios:
            print(f" {u.id:<4} {u.nome_completo[:28]:<30} {u.email[:28]:<30} {u.perfil_acesso:<12} {u.status:<8}")
        print("-" * 88)

        print(" Acoes:")
        print("  [1] Cadastrar Novo Colaborador")
        print("  [0] Voltar")

        opcao = input("\n Escolha: ").strip()
        if opcao == "1":
            nome = input(" Nome completo: ").strip()
            email = input(" E-mail corporativo: ").strip()
            senha = input(" Senha provisoria: ").strip()
            print(" Perfil: [1] OPERADOR  [2] GERENTE")
            p_opt = input(" Selecione o perfil (1/2): ").strip()
            perfil = "OPERADOR" if p_opt == "1" else ("GERENTE" if p_opt == "2" else "")
            if not perfil:
                self.print_alert_error("ERRO", "Perfil invalido.")
                self.pause()
                return

            try:
                novo_u = self.auth_service.create_user(self.current_user, nome, email, senha, perfil)
                self.print_alert_success(f"Usuario '{novo_u.nome_completo}' [{novo_u.perfil_acesso}] cadastrado com sucesso!")
                self.pause()
            except Exception as exc:
                self.print_alert_error("FALHA NO CADASTRO", str(exc))
                self.pause()
