"""
Simplified database testing configuration and fixtures.

This module provides shared fixtures for database testing using the existing ethan_db database.
"""

import pytest
import asyncio
from typing import Dict, Any

# Import the AsyncDB class
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from core.utils.database.db_async import AsyncDB
from core.utils.database.raw_db_async import RawAsyncDB


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def ethan_db_config() -> Dict[str, Any]:
    """
    Provide ethan_db database configuration from db_async.py main function.
    
    Returns:
        Database configuration dictionary for ethan_db
    """
    return {
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
    }

@pytest.fixture
def raw_async_ethan_db_config() -> Dict[str, Any]:
    """
    Provide ethan_db database configuration from db_async.py main function.
    
    Returns:
        Database configuration dictionary for ethan_db
    """
    return {
        "url": "mysql+aiomysql://root:MyNewPass1!@10.124.44.192:3306/ethan_db",
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
    }


@pytest.fixture
def db_instance(ethan_db_config):
    """
    Create and configure a database instance using ethan_db.
    
    Args:
        ethan_db_config: Database configuration from ethan_db_config fixture
    """
    # Create database instance
    db = AsyncDB(ethan_db_config)    
    return db

@pytest.fixture
def raw_async_db_instance(raw_async_ethan_db_config):
    """
    Create and configure a database instance using raw_async_ethan_db.
    
    Args:
        raw_async_ethan_db_config: Database configuration from raw_async_ethan_db_config fixture
    """
    # Create database instance
    db = RawAsyncDB(raw_async_ethan_db_config)    
    return db