"""
FastAPI dependencies for dependency injection
"""
from sqlalchemy.orm import Session
from repositories import (
    AlertRepository,
    CandleRepository,
    SymbolRepository,
    ConfigRepository,
    SymbolFilterRepository
)
from services import (
    AlertService,
    CandleService,
    SymbolService,
    ConfigService,
    SymbolFilterService
)


def get_alert_service_from_db(db: Session) -> AlertService:
    """Get alert service from existing session"""
    return AlertService(AlertRepository(db))


def get_candle_service_from_db(db: Session) -> CandleService:
    """Get candle service from existing session"""
    return CandleService(CandleRepository(db))


def get_symbol_service_from_db(db: Session) -> SymbolService:
    """Get symbol service from existing session"""
    return SymbolService(SymbolRepository(db))


def get_config_service_from_db(db: Session) -> ConfigService:
    """Get config service from existing session"""
    return ConfigService(ConfigRepository(db))


def get_symbol_filter_service_from_db(db: Session) -> SymbolFilterService:
    """Get symbol filter service from existing session"""
    return SymbolFilterService(SymbolFilterRepository(db))

