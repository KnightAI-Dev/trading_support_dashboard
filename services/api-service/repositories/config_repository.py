"""
Repository for configuration data
"""
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from .base_repository import BaseRepository


class ConfigRepository(BaseRepository):
    """Repository for configuration data access"""
    
    def get_strategy_config(self, config_key: Optional[str] = None) -> Dict:
        """Get strategy configuration"""
        if config_key:
            query = """
                SELECT config_key, config_value, config_type
                FROM strategy_config
                WHERE config_key = :config_key
            """
            rows = self.execute_query(query, {"config_key": config_key})
            if not rows:
                return {}
            row = rows[0]
            return {row[0]: self._parse_value(row[1], row[2])}
        else:
            query = """
                SELECT config_key, config_value, config_type
                FROM strategy_config
                ORDER BY config_key
            """
            rows = self.execute_query(query)
            return {row[0]: self._parse_value(row[1], row[2]) for row in rows}
    
    def update_strategy_config(
        self,
        config_key: str,
        config_value: str,
        updated_by: Optional[str] = None
    ) -> bool:
        """Update strategy configuration"""
        try:
            # Check if exists
            existing = self.execute_query(
                "SELECT config_type FROM strategy_config WHERE config_key = :config_key",
                {"config_key": config_key}
            )
            
            config_type = existing[0][0] if existing else 'string'
            
            query = text("""
                INSERT INTO strategy_config (config_key, config_value, config_type, updated_at, updated_by)
                VALUES (:config_key, :config_value, :config_type, NOW(), :updated_by)
                ON CONFLICT (config_key) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
            """)
            
            self.db.execute(query, {
                "config_key": config_key,
                "config_value": str(config_value),
                "config_type": config_type,
                "updated_by": updated_by or "api-service"
            })
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
    
    def update_strategy_configs(
        self,
        configs: Dict[str, str],
        updated_by: Optional[str] = None
    ) -> bool:
        """Update multiple strategy configurations"""
        try:
            for config_key, config_value in configs.items():
                existing = self.execute_query(
                    "SELECT config_type FROM strategy_config WHERE config_key = :config_key",
                    {"config_key": config_key}
                )
                config_type = existing[0][0] if existing else 'string'
                
                query = text("""
                    INSERT INTO strategy_config (config_key, config_value, config_type, updated_at, updated_by)
                    VALUES (:config_key, :config_value, :config_type, NOW(), :updated_by)
                    ON CONFLICT (config_key) DO UPDATE SET
                        config_value = EXCLUDED.config_value,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """)
                
                self.db.execute(query, {
                    "config_key": config_key,
                    "config_value": str(config_value),
                    "config_type": config_type,
                    "updated_by": updated_by or "api-service"
                })
            
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
    
    def get_ingestion_config(self, config_key: Optional[str] = None) -> Dict:
        """Get ingestion configuration"""
        if config_key:
            query = """
                SELECT config_key, config_value, config_type
                FROM ingestion_config
                WHERE config_key = :config_key
            """
            rows = self.execute_query(query, {"config_key": config_key})
            if not rows:
                return {}
            row = rows[0]
            return {row[0]: self._parse_value(row[1], row[2])}
        else:
            query = """
                SELECT config_key, config_value, config_type
                FROM ingestion_config
                ORDER BY config_key
            """
            rows = self.execute_query(query)
            return {row[0]: self._parse_value(row[1], row[2]) for row in rows}
    
    def update_ingestion_config(
        self,
        config_key: str,
        config_value: str,
        updated_by: Optional[str] = None
    ) -> bool:
        """Update ingestion configuration"""
        try:
            existing = self.execute_query(
                "SELECT config_type FROM ingestion_config WHERE config_key = :config_key",
                {"config_key": config_key}
            )
            config_type = existing[0][0] if existing else 'string'
            
            query = text("""
                INSERT INTO ingestion_config (config_key, config_value, config_type, updated_at, updated_by)
                VALUES (:config_key, :config_value, :config_type, NOW(), :updated_by)
                ON CONFLICT (config_key) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
            """)
            
            self.db.execute(query, {
                "config_key": config_key,
                "config_value": str(config_value),
                "config_type": config_type,
                "updated_by": updated_by or "api-service"
            })
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
    
    def update_ingestion_configs(
        self,
        configs: Dict[str, str],
        updated_by: Optional[str] = None
    ) -> bool:
        """Update multiple ingestion configurations"""
        try:
            for config_key, config_value in configs.items():
                existing = self.execute_query(
                    "SELECT config_type FROM ingestion_config WHERE config_key = :config_key",
                    {"config_key": config_key}
                )
                config_type = existing[0][0] if existing else 'string'
                
                query = text("""
                    INSERT INTO ingestion_config (config_key, config_value, config_type, updated_at, updated_by)
                    VALUES (:config_key, :config_value, :config_type, NOW(), :updated_by)
                    ON CONFLICT (config_key) DO UPDATE SET
                        config_value = EXCLUDED.config_value,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """)
                
                self.db.execute(query, {
                    "config_key": config_key,
                    "config_value": str(config_value),
                    "config_type": config_type,
                    "updated_by": updated_by or "api-service"
                })
            
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            raise
    
    @staticmethod
    def _parse_value(value: str, config_type: str):
        """Parse config value based on type"""
        if config_type == 'number':
            try:
                return float(value) if '.' in value else int(value)
            except ValueError:
                return value
        elif config_type == 'json':
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

