"""
Database base class implementation.

This module provides the abstract base class for database operations,
defining common interfaces and shared functionality for both sync and async implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union, ContextManager
from contextlib import contextmanager
import logging
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from sqlalchemy import MetaData, Table, select, func, and_, or_


class DatabaseConfigError(Exception):
    """Database configuration error."""
    pass


class DatabaseConnectionError(Exception):
    """Database connection error."""
    pass


class DatabaseBase(ABC):
    """
    Abstract base class for database operations.
    
    This class provides common functionality for database management including:
    - Configuration parsing and validation
    - Engine creation and management
    - Session factory creation
    - Basic error handling and logging
    
    Subclasses must implement specific sync/async functionality.
    """
    
    def __init__(self, config: Dict[str, Any], logger=None):
        """
        Initialize database base instance.
        
        Args:
            config: Database configuration dictionary containing:
                - url: Database connection URL (required)
                - echo: Whether to echo SQL statements (default: False)
                - engine: Engine-specific configuration (optional)
                - session: Session-specific configuration (optional)
            logger: Optional logger instance. If not provided, uses standard logging module.
        
        Raises:
            DatabaseConfigError: If configuration is invalid
        """
        self.config = config
        self._engine: Optional[Engine] = None
        self._session_factory = None
        self._is_initialized = False
        
        # Set up logger instance
        if logger is not None:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__)
        
        # Validate and setup database
        self._validate_config()
        self._setup_database()
        
        self.logger.info(f"Database initialized with URL: {self._get_safe_url()}")
            
        # 设置需要查询表定义时的缓存结构
        self._table_definitions_cache = {}

    def _validate_config(self) -> None:
        """
        Validate database configuration.
        
        Raises:
            DatabaseConfigError: If required configuration is missing or invalid
        """
        if not isinstance(self.config, dict):
            raise DatabaseConfigError("Config must be a dictionary")
        
        if "url" not in self.config:
            raise DatabaseConfigError("Database URL is required in config")
        
        if not self.config["url"]:
            raise DatabaseConfigError("Database URL cannot be empty")
        
        # Set default values
        self.config.setdefault("echo", False)
        self.config.setdefault("engine", {})
        self.config.setdefault("session", {})
        
        self.logger.debug("Database configuration validated successfully")
    
    def _setup_database(self) -> None:
        """Setup database engine and session factory."""
        try:
            self._create_engine()
            self._create_session_factory()
            self._is_initialized = True
            self.logger.info("Database setup completed successfully")
        except Exception as e:
            self.logger.error(f"Database setup failed: {str(e)}")
            raise DatabaseConnectionError(f"Failed to setup database: {str(e)}") from e
    
    def _create_engine(self) -> None:
        """
        Create SQLAlchemy engine based on configuration.
        
        Raises:
            DatabaseConnectionError: If engine creation fails
        """
        try:
            engine_config = self.config["engine"].copy()
            
            # Apply default engine configuration
            default_engine_config = {
                "echo": self.config["echo"],
                "future": True,  # Use SQLAlchemy 2.0 style
            }
            
            # Handle SQLite specific configuration
            if self.config["url"].startswith("sqlite"):
                # For SQLite, use StaticPool for better compatibility
                default_engine_config.update({
                    "poolclass": StaticPool,
                    "connect_args": {"check_same_thread": False}
                })
            else:
                # For other databases, set connection pool defaults
                default_engine_config.update({
                    "pool_size": 10,
                    "max_overflow": 20,
                    "pool_timeout": 30,
                    "pool_recycle": 3600,
                    "pool_pre_ping": True
                })
            
            # Merge with user configuration (user config takes precedence)
            final_config = {**default_engine_config, **engine_config}
            
            self._engine = create_engine(self.config["url"], **final_config)
            self.logger.debug(f"Database engine created with config: {list(final_config.keys())}")
            
        except Exception as e:
            self.logger.error(f"Engine creation failed: {str(e)}")
            raise DatabaseConnectionError(f"Failed to create database engine: {str(e)}") from e
    
    @abstractmethod
    def _create_session_factory(self) -> None:
        """
        Create session factory. Must be implemented by subclasses.
        
        This method should create appropriate session factory for sync/async operations.
        """
        pass
    
    def _get_safe_url(self) -> str:
        """
        Get database URL with password masked for logging.
        
        Returns:
            Safe database URL with password replaced by asterisks
        """
        url = self.config["url"]
        if "://" in url and "@" in url:
            # Format: dialect://username:password@host/database
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                credentials, host_db = rest.split("@", 1)
                if ":" in credentials:
                    username, _ = credentials.split(":", 1)
                    return f"{scheme}://{username}:***@{host_db}"
        return url
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self._engine.connect() as conn:
                test_sql = "SELECT 1 FROM DUAL" if self._engine.dialect.name == "oracle" else "SELECT 1"
                conn.execute(text(test_sql))
            self.logger.info("Database connection test successful")
            return True
        except Exception as e:
            self.logger.error(f"Database connection test failed: {str(e)}")
            return False
    
    def get_conn(self):
        """
        Get database connection with retry mechanism.
        
        Returns:
            SQLAlchemy connection instance
            
        Raises:
            DatabaseConnectionError: If database is not initialized or connection fails after retries
        """
        if not self._is_initialized or self._engine is None:
            raise DatabaseConnectionError("Database not initialized")
        
        import time
        max_retries = 3
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            try:
                # Create and test connection
                conn = self._engine.connect()
                # conn.execute(text("SELECT 1"))
                self.logger.debug(f"Database connection successful on attempt {attempt + 1}")
                return conn
            except Exception as e:
                self.logger.warning(f"Database connection failed on attempt {attempt + 1}/{max_retries}: {str(e)}")
                
                if attempt < max_retries - 1:
                    # Wait before retrying
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Final attempt failed
                    self.logger.error(f"Database connection failed after {max_retries} attempts")
                    raise DatabaseConnectionError(f"Failed to connect to database after {max_retries} attempts: {str(e)}") from e

    def get_engine(self) -> Engine:
        """
        Get database engine.
        
        Returns:
            SQLAlchemy engine instance
            
        Raises:
            DatabaseConnectionError: If database is not initialized
        """
        if not self._is_initialized or self._engine is None:
            raise DatabaseConnectionError("Database not initialized")
        return self._engine
    
    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self._engine:
            self._engine.dispose()
            self.logger.info("Database connections closed")
        
        self._engine = None
        self._session_factory = None
        self._is_initialized = False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    @abstractmethod
    def get_session(self) -> Union[Session, ContextManager[Session]]:
        """
        Get database session. Must be implemented by subclasses.
        
        Returns:
            Database session (sync) or session context manager (async)
        """
        pass
    
    @abstractmethod
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a raw SQL query. Must be implemented by subclasses.
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            
        Returns:
            Query result
        """
        pass
    
    def __repr__(self) -> str:
        """String representation of database instance."""
        return f"{self.__class__.__name__}(url='{self._get_safe_url()}')"
    
    """
    For engine Query
    """

    def make_table(self, table_name: str, metadata: MetaData=None) -> Table:
        """
        创建一个 SQLAlchemy 表对象。

        :param table_name: 表名
        :param metadata: SQLAlchemy MetaData 对象
        :return: SQLAlchemy Table 对象
        """
        if not metadata:
            metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=self._engine)
        return table

    @staticmethod
    def _process_condition(model, key, condition):
        """处理单个查询条件，将字典格式转换为 SQLAlchemy 条件表达式。

        根据条件字典中的操作符和值，生成对应的 SQLAlchemy 查询条件。
        支持常见的比较操作符以及 LIKE、IN、BETWEEN、IS_NULL 等特殊操作。

        Args:
            model (sqlalchemy.sql.schema.ColumnCollection): 表的列集合，通常是 table.c。
            key (str): 要查询的列名。
            condition (dict): 条件字典，包含 operator 和 value 键。
                - operator (str): 操作符，如 "=", ">", "LIKE", "IN" 等。
                - value (Any): 条件值，类型根据操作符而定。

        Returns:
            sqlalchemy.sql.elements.BinaryExpression or sqlalchemy.sql.elements.BooleanClauseList or None:
                生成的 SQLAlchemy 条件表达式，如果操作符不支持则返回 None。

        Example:
            >>> # 等值查询
            >>> condition = {"operator": "=", "value": "John"}
            >>> expr = DatabaseBase._process_condition(table.c, "name", condition)
            
            >>> # LIKE 查询
            >>> condition = {"operator": "LIKE", "value": "John"}
            >>> expr = DatabaseBase._process_condition(table.c, "name", condition)
            
            >>> # IN 查询
            >>> condition = {"operator": "IN", "value": ["active", "pending"]}
            >>> expr = DatabaseBase._process_condition(table.c, "status", condition)

        Note:
            - 对于 LIKE 操作，如果值不包含 % 符号，会自动在末尾添加 %。
            - 对于 LIKE 操作，如果值是列表，会生成多个 LIKE 条件并用 OR 连接。
            - 对于 BETWEEN 操作，值必须是包含两个元素的列表。
            - IS_NULL 操作不需要提供 value，会忽略 value 参数。
        """
        operator = condition["operator"]
        value = condition["value"]

        # 处理 LIKE 查询
        if operator == "LIKE":
            if isinstance(value, list):  # 如果是 list，表示多个 LIKE 查询，默认 OR 连接
                # 默认追加 % 符号
                value = [f"{v}%" if '%' not in v else v for v in value]
                like_conditions = [getattr(model, key).like(val) for val in value]
                return or_(*like_conditions)
            else:
                if '%' not in value:
                    value = f"{value}%"
                return getattr(model, key).like(value)

        # 处理 IN 查询
        elif operator.upper() == "IN":
            return getattr(model, key).in_(value)

        # 处理 BETWEEN 查询
        elif operator.upper() == "BETWEEN":
            return getattr(model, key).between(value[0], value[1])

        # 处理 IS NULL 查询
        elif operator.upper() == "IS_NULL":
            return getattr(model, key).is_(None)

        # 处理其他操作符
        elif operator == "=":
            return getattr(model, key) == value
        elif operator == "!=":
            return getattr(model, key) != value
        elif operator == ">":
            return getattr(model, key) > value
        elif operator == "<":
            return getattr(model, key) < value
        elif operator == ">=":
            return getattr(model, key) >= value
        elif operator == "<=":
            return getattr(model, key) <= value

        return None
    
    @classmethod
    def _handle_logic_conditions(cls, model, conditions_dict, logic_type):
        """处理 AND 或 OR 的复杂逻辑条件，支持递归嵌套。

        该方法递归处理逻辑条件字典，将多个子条件按照指定的逻辑类型（AND/OR）
        组合成一个复合的 SQLAlchemy 查询条件表达式。支持无限层级的嵌套逻辑组合。

        Args:
            model (sqlalchemy.Table): SQLAlchemy 表模型对象。
            conditions_dict (list): 条件字典列表，每个元素可以是：
                - 普通条件字典：{"column": {"operator": "=", "value": "value"}}
                - 嵌套逻辑条件：{"and": [...]} 或 {"or": [...]}
            logic_type (str): 逻辑类型，支持 "and" 或 "or"。

        Returns:
            sqlalchemy.sql.elements.BooleanClauseList or list:
                组合后的逻辑条件表达式。如果 logic_type 是 "and" 或 "or"，
                返回对应的 SQLAlchemy 逻辑表达式；否则返回条件列表。

        Example:
            >>> # AND 逻辑处理
            >>> conditions = [
            ...     {"age": {"operator": ">", "value": 18}},
            ...     {"status": {"operator": "=", "value": "active"}}
            ... ]
            >>> expr = DatabaseBase._handle_logic_conditions(table, conditions, "and")
            
            >>> # 嵌套逻辑处理
            >>> conditions = [
            ...     {"and": [{"age": {"operator": ">", "value": 18}}]},
            ...     {"or": [{"status": {"operator": "=", "value": "active"}}]}
            ... ]
            >>> expr = DatabaseBase._handle_logic_conditions(table, conditions, "and")

        Note:
            - 该方法会递归调用自身来处理嵌套的 "and" 和 "or" 条件。
            - 对于普通条件，会调用 _process_condition 方法进行处理。
            - 如果 logic_type 不是 "and" 或 "or"，会直接返回条件列表。
        """
        logical_conditions = []
        for sub_condition in conditions_dict:
            if "and" in sub_condition:  # 递归处理 and 条件
                logical_conditions.append(
                    cls._handle_logic_conditions(model, sub_condition["and"], "and"))
            elif "or" in sub_condition:  # 递归处理 or 条件
                logical_conditions.append(
                    cls._handle_logic_conditions(model, sub_condition["or"], "or"))
            else:  # 普通条件
                for key, condition in sub_condition.items():
                    logical_conditions.append(cls._process_condition(model.c, key, condition))

        # 根据逻辑类型生成 AND 或 OR
        if logic_type == "and":
            return and_(*logical_conditions)
        elif logic_type == "or":
            return or_(*logical_conditions)
        return logical_conditions
    
    @classmethod
    def build_where_conditions(cls, model, where_conditions):
        """构建 SQLAlchemy 查询条件，支持复杂的逻辑组合和多种操作符。

        该方法能够将字典格式的查询条件转换为 SQLAlchemy 的查询条件表达式，
        支持 AND、OR 逻辑组合，以及 LIKE、IN、BETWEEN、IS_NULL 等多种操作符。
        可以递归处理嵌套的逻辑条件，实现复杂的查询条件构建。

        Args:
            model (sqlalchemy.Table): SQLAlchemy 表模型对象，用于获取列引用。
            where_conditions (dict): 字典格式的查询条件，支持以下结构：
                - 简单条件: {"column": {"operator": "=", "value": "value"}}
                - AND 逻辑: {"and": [condition1, condition2, ...]}
                - OR 逻辑: {"or": [condition1, condition2, ...]}
                - 嵌套逻辑: {"and": [{"or": [...]}, {"column": {...}}]}

        Returns:
            sqlalchemy.sql.elements.BooleanClauseList or sqlalchemy.sql.elements.BinaryExpression or None:
                构建的 SQLAlchemy 查询条件表达式。如果没有有效条件则返回 None。

        Raises:
            KeyError: 当条件字典中缺少必要的键时抛出。
            AttributeError: 当模型中不存在指定的列时抛出。

        Example:
            >>> # 简单条件
            >>> conditions = {"name": {"operator": "=", "value": "John"}}
            >>> where_clause = DatabaseBase.build_where_conditions(table, conditions)
            
            >>> # 复杂逻辑条件
            >>> conditions = {
            ...     "and": [
            ...         {"age": {"operator": ">", "value": 18}},
            ...         {"or": [
            ...             {"status": {"operator": "=", "value": "active"}},
            ...             {"priority": {"operator": "IN", "value": ["high", "urgent"]}}
            ...         ]}
            ...     ]
            ... }
            >>> where_clause = DatabaseBase.build_where_conditions(table, conditions)

        Note:
            支持的操作符包括：=, !=, >, <, >=, <=, LIKE, IN, BETWEEN, IS_NULL。
            对于 LIKE 操作，如果值不包含 % 符号，会自动在末尾添加 %。
            对于 BETWEEN 操作，值应为包含两个元素的列表 [start, end]。
        """
        conditions = []

        # 遍历 where_conditions 中的条件，递归处理 and/or 条件
        for key, condition in where_conditions.items():
            if key == "and":  # 处理 AND 逻辑
                conditions.append(cls._handle_logic_conditions(model, condition, "and"))
            elif key == "or":  # 处理 OR 逻辑
                conditions.append(cls._handle_logic_conditions(model, condition, "or"))
            else:  # 普通条件
                conditions.append(cls._process_condition(model.c, key, condition))

        # 返回最终的查询条件
        return and_(*conditions) if len(conditions) > 1 else conditions[0] if conditions else None

