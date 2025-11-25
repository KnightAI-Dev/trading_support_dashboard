"""
Service for configuration business logic
"""
from typing import Dict, Optional
from repositories.config_repository import ConfigRepository
from exceptions import ConfigurationError


class ConfigService:
    """Service for configuration operations"""
    
    def __init__(self, config_repo: ConfigRepository):
        self.config_repo = config_repo
    
    def get_strategy_config(self, config_key: Optional[str] = None) -> Dict:
        """Get strategy configuration"""
        return self.config_repo.get_strategy_config(config_key)
    
    def update_strategy_config(
        self,
        config_key: str,
        config_value: str,
        updated_by: Optional[str] = None
    ) -> bool:
        """Update strategy configuration"""
        try:
            return self.config_repo.update_strategy_config(
                config_key=config_key,
                config_value=config_value,
                updated_by=updated_by
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to update config: {e}") from e
    
    def update_strategy_configs(
        self,
        configs: Dict[str, str],
        updated_by: Optional[str] = None
    ) -> bool:
        """Update multiple strategy configurations"""
        try:
            return self.config_repo.update_strategy_configs(
                configs=configs,
                updated_by=updated_by
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to update configs: {e}") from e
    
    def get_ingestion_config(self, config_key: Optional[str] = None) -> Dict:
        """Get ingestion configuration"""
        return self.config_repo.get_ingestion_config(config_key)
    
    def update_ingestion_config(
        self,
        config_key: str,
        config_value: str,
        updated_by: Optional[str] = None
    ) -> bool:
        """Update ingestion configuration"""
        try:
            return self.config_repo.update_ingestion_config(
                config_key=config_key,
                config_value=config_value,
                updated_by=updated_by
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to update config: {e}") from e
    
    def update_ingestion_configs(
        self,
        configs: Dict[str, str],
        updated_by: Optional[str] = None
    ) -> bool:
        """Update multiple ingestion configurations"""
        try:
            return self.config_repo.update_ingestion_configs(
                configs=configs,
                updated_by=updated_by
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to update configs: {e}") from e

