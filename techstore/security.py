import hashlib

def hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()

def verify_password(raw_password: str, hashed_password: str) -> bool:
    return hash_password(raw_password) == hashed_password

def generate_receipt_signature(numero_pedido: str, data_hora: str, valor_total: float, cliente_doc: str) -> str:
    raw_payload = f"{numero_pedido}|{data_hora}|{valor_total:.2f}|{cliente_doc}|TECHSTORE-AUTH-KEY-2026"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest().upper()
