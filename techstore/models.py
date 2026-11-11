from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    nome_completo: str
    email: str
    perfil_acesso: str
    status: str

    @property
    def is_gerente(self) -> bool:
        return self.perfil_acesso == "GERENTE"

    @property
    def is_operador(self) -> bool:
        return self.perfil_acesso == "OPERADOR"

    @property
    def is_ativo(self) -> bool:
        return self.status == "ATIVO"

@dataclass
class Product:
    id: int
    categoria_id: int
    fornecedor_id: int
    nome: str
    tipo: str
    preco: float
    estoque_atual: int
    estoque_minimo: int = 5
    categoria_nome: Optional[str] = None
    fornecedor_nome: Optional[str] = None

    @property
    def tipo_badge(self) -> str:
        if self.tipo == "LICENCA_DIGITAL":
            return "[LICENÇA DIGITAL]"
        return "[COMPONENTE FÍSICO]"

@dataclass
class CartItem:
    product_id: int
    nome: str
    tipo: str
    preco_unitario: float
    quantidade: int

    @property
    def subtotal(self) -> float:
        return round(self.preco_unitario * self.quantidade, 2)

    @property
    def tipo_badge(self) -> str:
        if self.tipo == "LICENCA_DIGITAL":
            return "[LICENÇA DIGITAL]"
        return "[COMPONENTE FÍSICO]"

@dataclass
class Sale:
    id: int
    numero_pedido: str
    data_hora: str
    cliente_nome: str
    cliente_documento: str
    forma_pagamento: str
    valor_total: float
    status_venda: str
    usuario_id: int
    usuario_nome: Optional[str] = None

@dataclass
class SaleItem:
    id: int
    venda_id: int
    produto_id: int
    quantidade_vendida: int
    preco_unitario_praticado: float
    subtotal_item: float
    produto_nome: Optional[str] = None
    tipo: Optional[str] = None

    @property
    def tipo_badge(self) -> str:
        if self.tipo == "LICENCA_DIGITAL":
            return "[LICENÇA DIGITAL]"
        return "[COMPONENTE FÍSICO]"

@dataclass
class MovementAudit:
    id: int
    produto_id: int
    tipo_movimentacao: str
    quantidade: int
    motivo: str
    data_hora: str
    usuario_id: Optional[int]
    produto_nome: Optional[str] = None
    usuario_nome: Optional[str] = None
