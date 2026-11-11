class TechStoreException(Exception):
    pass

class AuthenticationError(TechStoreException):
    pass

class PermissionDeniedError(TechStoreException):
    pass

class InsufficientStockError(TechStoreException):
    pass

class SaleNotFoundError(TechStoreException):
    pass

class ValidationError(TechStoreException):
    pass
