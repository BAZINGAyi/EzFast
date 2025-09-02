"""
Database Manager for multi-database management.

This module provides a centralized database manager that can handle multiple database
connections with different configurations. It supports both synchronous and asynchronous
database operations through a unified interface.
"""

import logging
from typing import Dict, Any, Union, Optional
from pydantic import BaseModel, Field, field_validator

from .db_async import AsyncDB


class DatabaseConfig(BaseModel):
    """
    Single database configuration model with Pydantic validation.
    
    Attributes:
        url: Database connection URL
        echo: Whether to print SQL statements
        engine: Engine configuration parameters
        session: Session configuration parameters
    """
    url: str = Field(..., description="Database connection URL")
    echo: bool = Field(default=False, description="Whether to print SQL statements")
    engine: Dict[str, Any] = Field(default_factory=dict, description="Engine configuration")
    session: Dict[str, Any] = Field(default_factory=dict, description="Session configuration")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate database URL format."""
        if not v or not isinstance(v, str):
            raise ValueError('Database URL must be a non-empty string')
        
        # Basic URL validation - should contain protocol
        if '://' not in v:
            raise ValueError('Database URL must contain a protocol (e.g., postgresql://, sqlite://)')
        
        return v


class DatabasesConfig(BaseModel):
    """
    Multi-database configuration model with validation.
    
    Ensures that a 'default' database configuration is always present.
    """
    databases: Dict[str, DatabaseConfig]
    
    @field_validator('databases')
    @classmethod
    def must_have_default(cls, v):
        """Ensure that 'default' database configuration exists."""
        if 'default' not in v:
            raise ValueError('Must have a "default" database configuration')
        return v


class DatabaseManager:
    """
    Multi-database manager for centralized database connection management.
    
    This class provides:
    - Multiple database instance management
    - Configuration validation using Pydantic
    - Unified access interface for different database types
    - Instance caching to avoid repeated creation
    - Simple connection status monitoring
    
    Example:
        # Database configuration
        config = {
            "default": {
                "type": "async",
                "url": "postgresql://user:pass@localhost/main_db",
                "engine": {"pool_size": 10}
            },
            "logging": {
                "type": "sync", 
                "url": "sqlite:///logs.db"
            }
        }
        
        # Initialize manager
        db_manager = DatabaseManager(config)
        
        # Get database instances (unified interface)
        main_db = db_manager.get_database("default")
        log_db = db_manager.get_database("logging")
        
        # Use with same interface regardless of sync/async
        results = await main_db.run_query("users")
    """
    
    def __init__(self, databases_config: Dict[str, Dict], logger: Optional[logging.Logger] = None):
        """
        Initialize the database manager.
        
        Args:
            databases_config: Dictionary of database configurations
            logger: Optional logger instance
        """
        self.logger = logger
        
        # Validate configuration using Pydantic
        self._validate_and_store_config(databases_config)
        
        # Instance cache to avoid repeated creation
        self._instances: Dict[str, AsyncDB] = {}
        
        if self.logger:
            self.logger.info(f"DatabaseManager initialized with {len(self.config.databases)} databases")
    
    def _validate_and_store_config(self, databases_config: Dict[str, Dict]) -> None:
        """
        Validate and store database configuration.
        
        Args:
            databases_config: Raw database configuration dictionary
            
        Raises:
            ValueError: If configuration validation fails
        """
        try:
            # Convert dict to Pydantic models for validation
            validated_databases = {
                name: DatabaseConfig(**config) 
                for name, config in databases_config.items()
            }
            
            # Validate the complete configuration
            self.config = DatabasesConfig(databases=validated_databases)
            
            if self.logger:
                self.logger.debug("Database configuration validated successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Database configuration validation failed: {str(e)}")
            raise ValueError(f"Invalid database configuration: {str(e)}")
    
    def add_database(self, name: str, config: Dict[str, Any]) -> None:
        """
        Add a new database configuration dynamically.
        
        Args:
            name: Database name/identifier
            config: Database configuration dictionary
            
        Raises:
            ValueError: If database name already exists or configuration is invalid
        """
        if name in self.config.databases:
            raise ValueError(f"Database '{name}' already exists")
        
        try:
            # Validate new configuration
            validated_config = DatabaseConfig(**config)
            
            # Add to configuration
            self.config.databases[name] = validated_config
            
            if self.logger:
                self.logger.info(f"Added database '{name}' to configuration")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to add database '{name}': {str(e)}")
            raise ValueError(f"Invalid configuration for database '{name}': {str(e)}")
    
    def remove_database(self, name: str) -> None:
        """
        Remove a database configuration and close its instance if exists.
        
        Args:
            name: Database name to remove
            
        Raises:
            ValueError: If trying to remove the 'default' database or non-existent database
        """
        if name == "default":
            raise ValueError("Cannot remove the 'default' database")
        
        if name not in self.config.databases:
            raise ValueError(f"Database '{name}' does not exist")
        
        # Close instance if it exists
        if name in self._instances:
            try:
                # Close the database instance (implementation depends on db type)
                instance = self._instances[name]
                if hasattr(instance, 'close'):
                    instance.close()
                del self._instances[name]
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error closing database instance '{name}': {str(e)}")
        
        # Remove from configuration
        del self.config.databases[name]
        
        if self.logger:
            self.logger.info(f"Removed database '{name}' from configuration")
    
    def get_database(self, name: str = "default") -> Union[AsyncDB]:  # Will include SyncDB when implemented
        """
        Get a database instance by name with unified interface.
        
        This method provides a single access point for all database instances,
        regardless of whether they are synchronous or asynchronous. The usage
        interface remains the same.
        
        Args:
            name: Database name. Defaults to "default"
            
        Returns:
            Database instance (AsyncDB or SyncDB)
            
        Raises:
            ValueError: If database name does not exist
        """
        if name not in self.config.databases:
            raise ValueError(f"Database '{name}' is not configured")
        
        # Return cached instance if exists
        if name in self._instances:
            return self._instances[name]
        
        # Create new instance based on configuration
        db_config = self.config.databases[name]
        
        try:
            # Since we only support async databases now, always create AsyncDB instance
            instance = self._create_async_instance(name, db_config)
            
            # Cache the instance
            self._instances[name] = instance
            
            if self.logger:
                self.logger.debug(f"Created new async database instance for '{name}'")
            
            return instance
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create database instance '{name}': {str(e)}")
            raise
    
    def _create_async_instance(self, name: str, config: DatabaseConfig) -> AsyncDB:
        """
        Create an AsyncDB instance.
        
        Args:
            name: Database name for logging
            config: Validated database configuration
            
        Returns:
            AsyncDB instance
        """
        # Convert Pydantic model back to dict for AsyncDB constructor
        db_config = {
            "url": config.url,
            "echo": config.echo,
            "engine": config.engine,
            "session": config.session
        }
        
        return AsyncDB(db_config, logger=self.logger)
    
    def close_all(self) -> None:
        """
        Close all database instances and clean up resources.
        
        This should be called when shutting down the application.
        """
        closed_count = 0
        
        for name, instance in self._instances.items():
            try:
                if hasattr(instance, 'close'):
                    instance.close()
                closed_count += 1
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Error closing database instance '{name}': {str(e)}")
        
        self._instances.clear()
        
        if self.logger:
            self.logger.info(f"Closed {closed_count} database instances")
    
    def list_databases(self) -> Dict[str, str]:
        """
        List all configured databases with their URLs.
        
        Returns:
            Dictionary mapping database names to their URLs
        """
        return {
            name: config.url 
            for name, config in self.config.databases.items()
        }
    
    def __repr__(self) -> str:
        """String representation of the manager."""
        db_count = len(self.config.databases)
        instance_count = len(self._instances)
        return f"DatabaseManager(databases={db_count}, active_instances={instance_count})"


# Example usage and configuration
if __name__ == "__main__":
    # Example configuration
    example_config = {
        "default": {
            "url": "mysql+pymysql://root:MyNewPass1!@10.124.44.192:3306/ethan_db",
            "echo": False,
            "engine": {
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True
            },
            "session": {
                "autocommit": False,
                "autoflush": True,
                "expire_on_commit": True
            }
        },
        # "read_only": {
        #     "url": "mysql+pymysql://root:MyNewPass1!@10.124.44.192:3306/ethan_db",
        #     "echo": False,
        #     "engine": {
        #         "pool_size": 5,
        #         "max_overflow": 10
        #     }
        # },
        # "logging": {
        #     "url": "sqlite:///./logs.db",
        #     "echo": False,
        #     "engine": {
        #         "pool_size": 3,
        #         "max_overflow": 5
        #     }
        # }
    }
    
    # Example usage
    async def main():
        # Initialize manager
        db_manager = DatabaseManager(example_config)
        
        # Print database list
        print("Database list:", db_manager.list_databases())
        
        # Get database instances
        main_db = db_manager.get_database("default")
        
        print(f"Main DB: {type(main_db).__name__}")
        
        # Example unified usage
        results = await main_db.run_query("user", limit=5)
        print(f"Query results: {len(results) if results else 0} rows")
        
        # task asyncio.gather
        tasks = [
            main_db.run_query("user", limit=5),
            main_db.run_query("user", limit=1)
        ]
        res = await asyncio.gather(*tasks)
        print(res[0])
        print(res[1])
        
        # Clean up
        db_manager.close_all()
        print("All databases closed")
    
    import asyncio
    asyncio.run(main())
