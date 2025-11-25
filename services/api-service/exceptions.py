"""
Domain exceptions for API service
"""


class DomainException(Exception):
    """Base exception for domain errors"""
    pass


class NotFoundError(DomainException):
    """Resource not found"""
    pass


class ValidationError(DomainException):
    """Validation error"""
    pass


class ConfigurationError(DomainException):
    """Configuration error"""
    pass

