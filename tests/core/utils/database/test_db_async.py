"""
Simplified test cases for AsyncDB class.

This module contains test cases based on the main function examples in db_async.py,
testing against the existing ethan_db database with user table (id, username, email).
"""

import pytest
import asyncio
from typing import List, Dict, Any

# Import the AsyncDB class
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../../'))

from core.utils.database.db_async import AsyncDB


class TestAsyncDBBasic:
    """Test basic AsyncDB functionality based on main function examples."""
    
    @pytest.mark.asyncio
    async def test_db_initialization(self, ethan_db_config):
        """Test AsyncDB initialization with ethan_db configuration."""
        db = AsyncDB(ethan_db_config)
        assert db is not None
        assert db._engine is not None
        
        # Test connection
        with db.get_conn() as conn:
            assert conn is not None
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_run_query_basic(self, db_instance):
        """Test basic run_query functionality like in main function."""
        try:
            # Test similar to the commented query in main function
            where_conditions = {
                "and": [
                    {"username": {"operator": "=", "value": "admin"}}
                ]
            }
            
            # This should run without error even if no admin user exists
            result = await db_instance.run_query(
                "user",
                where_conditions=where_conditions,
            )
            
            assert isinstance(result, list)
            # Result might be empty if no admin user exists, that's OK
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.asyncio
    async def test_bulk_insert_data(self, db_instance):
        """Test bulk_insert_data functionality based on main function example."""
        try:
            # Create test data similar to main function
            insert_data = []
            for data in range(3):  # Reduced from 10 to 3 for testing
                insert_data.append({
                    "username": f"test_user_{data}", 
                    "email": f"test_user_{data}@example.com"
                })
            
            # Execute bulk insert
            status, errors, stats = await db_instance.bulk_insert_data(
                "user",
                insert_data
            )
            
            # Verify results
            assert status is True
            assert len(errors) == 0
            assert stats["success"] == 3
            assert stats["total"] == 3
            
            # Cleanup: Remove test data
            await self._cleanup_test_users(db_instance, ["test_user_0", "test_user_1", "test_user_2"])
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.asyncio
    async def test_bulk_update_data(self, db_instance):
        """Test bulk_update_data functionality based on main function example."""
        try:
            # First insert some test data
            insert_data = [
                {"username": "update_test_1", "email": "original1@example.com"},
                {"username": "update_test_2", "email": "original2@example.com"}
            ]
            
            await db_instance.bulk_insert_data("user", insert_data)
            
            # Get the inserted user IDs
            where_conditions = {
                "and": [
                    {"username": {"operator": "IN", "value": ["update_test_1", "update_test_2"]}}
                ]
            }
            users = await db_instance.run_query(
                "user",
                select_columns=["id", "username"],
                where_conditions=where_conditions,
                return_clear=True
            )
            
            # Prepare update data similar to main function example
            update_data = []
            for user in users:
                update_data.append({
                    "id": user["id"], 
                    "email": f"changed_{user['username']}@example.com"
                })
            
            # Execute bulk update using ID as where_key (like main function)
            status, errors, stats = await db_instance.bulk_update_data(
                "user",
                update_data,
                where_key="id"
            )
            
            # Verify results
            assert status is True
            assert len(errors) == 0
            assert stats["success"] >= 1  # At least one row updated
            
            # Cleanup
            await self._cleanup_test_users(db_instance, ["update_test_1", "update_test_2"])
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.asyncio
    async def test_bulk_dml_table(self, db_instance):
        """Test bulk_dml_table functionality based on main function example."""
        try:
            # Test operations similar to main function table_operations
            table_operations = [
                {
                    "table": "user",
                    "data": [{"username": "transaction_user", "email": "transaction@test.com"}],
                    "operation": "insert"
                },
                {
                    "table": "user", 
                    "data": {"email": "updated_in_transaction@test.com"},
                    "operation": "update",
                    "where_conditions": {"username": {"operator": "=", "value": "transaction_user"}}
                }
            ]
            
            # Execute multi-table transaction
            success, errors, stats_list = await db_instance.bulk_dml_table(table_operations)
            
            # Verify results
            assert success is True
            assert len(errors) == 0
            assert len(stats_list) == 2  # Two operations
            
            # Verify the data was inserted and updated
            where_conditions = {
                "and": [
                    {"username": {"operator": "=", "value": "transaction_user"}}
                ]
            }
            results = await db_instance.run_query(
                "user",
                where_conditions=where_conditions,
                return_clear=True
            )
            
            assert len(results) == 1
            assert results[0]["email"] == "updated_in_transaction@test.com"
            
            # Cleanup
            await self._cleanup_test_users(db_instance, ["transaction_user"])
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.asyncio
    async def test_bulk_dml_table_sql(self, db_instance):
        """Test bulk_dml_table_sql functionality based on main function example."""
        try:
            # Test SQL statements similar to main function
            sql_statements = [
                "INSERT INTO user (username, email) VALUES ('sql_user_1', 'sql1@test.com')",
                "INSERT INTO user (username, email) VALUES ('sql_user_2', 'sql2@test.com')",
                "UPDATE user SET email = 'updated_sql1@test.com' WHERE username = 'sql_user_1'"
            ]
            
            # Execute bulk SQL (like main function, but actually execute for testing)
            success, errors, stats_list = await db_instance.bulk_dml_table_sql(sql_statements)
            
            # Verify results
            assert success is True
            assert len(errors) == 0
            assert len(stats_list) == 3  # Three SQL statements
            
            # Verify the data was inserted and updated
            where_conditions = {
                "and": [
                    {"username": {"operator": "in", "value": ["sql_user_1", "sql_user_2"]}}
                ]
            }
            results = await db_instance.run_query(
                "user",
                where_conditions=where_conditions,
                return_clear=True
            )
            
            assert len(results) == 2
            
            # Find sql_user_1 and verify email was updated
            sql_user_1 = next((user for user in results if user["username"] == "sql_user_1"), None)
            assert sql_user_1 is not None
            assert sql_user_1["email"] == "updated_sql1@test.com"
            
            # Cleanup
            await self._cleanup_test_users(db_instance, ["sql_user_1", "sql_user_2"])
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors
    
    async def _cleanup_test_users(self, db_instance, usernames: List[str]):
        """Helper method to cleanup test users after testing."""
        # Delete test users
        where_conditions = {
            "and": [
                {"username": {"operator": "IN", "value": usernames}}
            ]
        }
        
        delete_operations = [{
            "table": "user",
            "operation": "delete",
            "where_conditions": where_conditions
        }]
        
        await db_instance.bulk_dml_table(delete_operations)


class TestAsyncDBErrorHandling:
    """Test AsyncDB error handling."""
    
    @pytest.mark.asyncio
    async def test_bulk_insert_empty_data(self, db_instance):
        """Test bulk_insert_data with empty data."""
        try:
            status, errors, stats = await db_instance.bulk_insert_data("user", [])
            
            assert status is True
            assert len(errors) == 0
            assert stats["success"] == 0
            assert stats["total"] == 0
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.asyncio
    async def test_bulk_dml_table_sql_invalid_sql(self, db_instance):
        """Test bulk_dml_table_sql with invalid SQL."""
        try:
            sql_statements = [
                "INVALID SQL STATEMENT"
            ]
            
            success, errors, stats_list = await db_instance.bulk_dml_table_sql(sql_statements)
            
            assert success is False
            assert len(errors) > 0
        finally:
            # Ensure database connection is closed
            try:
                db_instance.close()
            except Exception:
                pass  # Ignore cleanup errors


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
