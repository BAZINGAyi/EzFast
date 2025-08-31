"""
Asynchronous database implementation.

This module provides asynchronous database operations built on top of the base database class.
It's suitable for high-concurrency scenarios using async/await patterns with engine-based operations.
"""

from contextlib import contextmanager
import time
from typing import Any, Dict, Generator, Optional, List
from sqlalchemy import MetaData, Table, delete, select, func
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.expression import text

from .db_base import DatabaseBase
from core.utils.async_tools import async_wrap


class AsyncDB(DatabaseBase):
    """
    Asynchronous database implementation using engine-based operations.
    
    This class provides asynchronous database operations with run_query functionality
    integrated from the reference implementation.
    
    Note: Uses synchronous engine with async_wrap decorator to convert 
    blocking operations to async as per design requirements.
    
    Example:
        # Initialize with configuration
        config = {
            "url": "sqlite:///example.db",
            "echo": False,
            "engine": {"pool_size": 5}
        }
        
        db = AsyncDB(config)
        
        # Use run_query for complex queries
        results = await db.run_query(
            table="users",
            select_columns=["id", "name"],
            where_conditions={
                "and": [
                    {"age": {"operator": ">", "value": 18}},
                    {"status": {"operator": "=", "value": "active"}}
                ]
            },
            order_by_columns=["name"],
            limit=10
        )
    """
    
    # Chunk sizes for batch operations
    chunk_size = 2000  # For bulk insert operations
    
    def _create_session_factory(self) -> None:
        """Create synchronous session factory."""
        
        session_config = self.config["session"].copy()
        
        # Apply default session configuration
        default_session_config = {
            "bind": self._engine,
            "autocommit": False,
            "autoflush": True,
            "expire_on_commit": True
        }
        
        # Merge with user configuration
        final_config = {**default_session_config, **session_config}
        
        self._session_factory = sessionmaker(**final_config)
        self.logger.debug(f"Sync session factory created with config: {list(final_config.keys())}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session with automatic transaction management.
        
        This context manager automatically handles:
        - Session creation and cleanup
        - Transaction commit on success
        - Transaction rollback on exception
        
        Yields:
            Database session
            
        Example:
            with db.get_session() as session:
                user = User(name="John")
                session.add(user)
                # Transaction is automatically committed
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
            self.logger.debug("Session transaction committed successfully")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Session transaction rolled back due to error: {str(e)}")
            raise
        finally:
            session.close()
            self.logger.debug("Session closed")

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None):
        """
        Execute query not implemented for engine-based operations.
        
        Raises:
            NotImplementedError: Execute query functionality not implemented
        """
        raise NotImplementedError("Execute query functionality not implemented for engine-based operations")

    @async_wrap
    def execute_query_stmt(self, stmt, return_clear=False):
        """
        Execute a SQL statement.

        :param stmt: The SQL statement to execute.
        :return: The result of the execution.
        """
        if isinstance(stmt, str):
            stmt = text(stmt)

        with self.get_conn() as conn:
            result = conn.execute(stmt)
            rows = [dict(row._mapping) for row in result] if return_clear else result.fetchall()
            return rows

    async def run_query(
        self,
        table,
        select_columns=None,
        where_conditions=None,
        group_by_columns=None,
        order_by_columns=None,
        limit=None,
        offset=None,
        return_clear=False,
    ):
        """
        执行一个通用查询，支持WHERE、ORDER BY、GROUP BY等操作。
        
        :param table: 表对象或表名字符串
        :param select_columns: 选择的列，可以传入列名字符串列表
        :param where_conditions: WHERE 条件（字典形式）
        :param group_by_columns: GROUP BY 列，可以传列名字符串列表
        :param order_by_columns: ORDER BY 列，可以传列名字符串列表
        :param limit: 限制返回的结果数量
        :param offset: 偏移量
        :param return_clear: 是否返回清晰的结果（字典形式）
        :return: 查询结果
        """
        # 如果传入的是字符串，创建Table对象
        if isinstance(table, str):
            table = self.make_table(table)

        # 转换 select_columns 中的列名字符串为对应的列对象
        if select_columns:
            select_columns = [
                getattr(table.c, col)
                if isinstance(col, str) else col for col in select_columns]
        else:
            select_columns = [table]
            
        # 如果 group_by_columns 存在，则默认添加 COUNT() 作为 select_column
        if group_by_columns:
            # 确保 group_by_columns 中的列对象也被正确转换
            group_by_columns = [
                getattr(table.c, col)
                if isinstance(col, str) else col for col in group_by_columns]
            select_columns.append(func.count().label("count"))
        
        # 基本查询
        stmt = select(*select_columns).select_from(table)

        # 如果 group_by_columns 存在，则应用 GROUP BY
        if group_by_columns:
            stmt = stmt.group_by(*group_by_columns)

        # 如果 order_by_columns 存在，则应用 ORDER BY
        if order_by_columns:
            order_by_columns = [
                getattr(table.c, col)
                if isinstance(col, str) else col for col in order_by_columns]
            stmt = stmt.order_by(*order_by_columns)

        # 添加 WHERE 条件
        if where_conditions:
            conditions = self.build_where_conditions(table, where_conditions)
            stmt = stmt.where(conditions)

        # 添加 LIMIT
        if limit:
            stmt = stmt.limit(limit)
            
        # 添加 OFFSET
        if offset:
            stmt = stmt.offset(offset)

        # 执行查询
        self.logger.debug(f"Executing query: {str(stmt)}")
        rows = await self.execute_query_stmt(stmt, return_clear=return_clear)
        self.logger.info(f"Query completed, returned {len(rows)} rows")
        return rows
    
    async def scroll_query(
        self,
        table,
        select_columns=None,
        where_conditions=None,
        group_by_columns=None,
        order_by_columns=None,
        return_clear=False,
        batch_size=100000,
    ):
        """
        滚动查询功能，先查询总记录数，然后循环遍历整个结果集，每次限制指定数量的记录。
        
        :param table: 表对象或表名字符串
        :param select_columns: 选择的列，可以传入列名字符串列表
        :param where_conditions: WHERE 条件（字典形式）
        :param group_by_columns: GROUP BY 列，可以传列名字符串列表
        :param order_by_columns: ORDER BY 列，可以传列名字符串列表
        :param return_clear: 是否返回清晰的结果（字典形式）
        :param batch_size: 每批次查询的记录数量，默认10万
        :return: 所有查询结果的列表
        """
        # 先查询总记录数
        total_count_results = await self.run_query(
            table=table,
            select_columns=[func.count().label("count")],
            where_conditions=where_conditions,
            group_by_columns=group_by_columns
        )
        
        total_count = total_count_results[0][0] if total_count_results else 0
        self.logger.info(f"Scroll query total count: {total_count}")
        
        if total_count == 0:
            return []
        
        # 计算需要的循环次数
        total_batches = (total_count + batch_size - 1) // batch_size
        self.logger.debug(f"Scroll query will process {total_batches} batches with batch_size {batch_size}")
        
        all_results = []
        for batch_index in range(total_batches):
            offset = batch_index * batch_size
            
            # 调用 run_query 获取当前批次的数据
            batch_results = await self.run_query(
                table=table,
                select_columns=select_columns,
                where_conditions=where_conditions,
                group_by_columns=group_by_columns,
                order_by_columns=order_by_columns,
                limit=batch_size,
                offset=offset,
                return_clear=return_clear,
            )
            
            # 将当前批次的结果添加到总结果中
            if batch_results:
                all_results.extend(batch_results)
                self.logger.debug(f"Batch {batch_index + 1}/{total_batches}: fetched {len(batch_results)} rows")
                
        self.logger.info(f"Scroll query completed, total rows fetched: {len(all_results)}")
        return all_results

    def _prepare_bulk_operation(self, table, operation_type: str, statistics_key: Optional[str] = None):
        """
        准备批量操作的通用初始化。
        
        Args:
            table: 表对象或表名字符串
            operation_type: 操作类型 ('insert', 'update', 'delete')
            statistics_key: 自定义统计键名
            
        Returns:
            (table_obj, statistics_key, statistics, start_time) 元组
        """
        # 准备表对象
        if isinstance(table, str):
            if table not in self._table_definitions_cache:
                self._table_definitions_cache[table] = self.make_table(table)
            table = self._table_definitions_cache[table]

        # 准备统计信息
        if not statistics_key:
            statistics_key = f"{table.name}_{operation_type}"
        # 同一事务针对同一张表多次操作，防止被覆盖
        elif isinstance(statistics_key, int):
            statistics_key = f"{table.name}_{operation_type}_{statistics_key}"

        start_time = time.time()
        statistics = {
            "name": statistics_key,
            "success": 0,
            "total": 0,
            "spent_time": start_time
        }

        return table, statistics

    def _finalize_bulk_operation(self, statistics: dict, operation_type: str, total: int) -> None:
        """
        完成批量操作的通用结束处理。
        
        Args:
            statistics: 统计信息字典 {"total": 0, "success": 0, "spent_time": time.time()}
            operation_type: 操作类型
            total_data: 总数据量
        """
        statistics["spent_time"] = int(time.time() - statistics["spent_time"])
        statistics["total"] = total
        total_count = statistics["total"]
        success_count = statistics["success"]
        spent_time = statistics["spent_time"]
        
        if operation_type == "insert":
            self.logger.info(
                f"Bulk insert completed: {success_count}/{total_count} records, "
                f"time: {spent_time}s")
        elif operation_type == "update":
            self.logger.info(
                f"Bulk update completed: {success_count} rows affected from {total_count} records, "
                f"time: {spent_time}s")
        elif operation_type == "sql_execution":
            self.logger.info(
                f"Bulk SQL execution completed: {success_count} rows affected from {total_count} statements, "
                f"time: {spent_time}s")

    @async_wrap
    def bulk_insert_data(self, table, data: list, statistics_key=None):
        """
        插入数据到数据库。适用于大数据量同一张表操作。
        
        :param data: 要插入的数据列表，每个元素为字典
        :param table: SQLAlchemy 表对象
        :param statistics_key: 统计信息的键名，如果不提供则使用表名_insert
        :return: (status, err_msg, statistics) 元组
            - status: 操作是否成功
            - err_msg: 错误信息列表
            - statistics: 统计信息字典
        """
        # 使用公共方法初始化
        table, statistics = self._prepare_bulk_operation(table, "insert", statistics_key)
        total_count = len(data)
        
        if total_count == 0:
            return True, [], statistics
            
        status, err_msg = True, []
        chunk_size = self.chunk_size
        
        with self.get_conn() as conn:
            for i in range(0, total_count, chunk_size):
                chunk = data[i:i + chunk_size]
                try:
                    conn.execute(table.insert(), chunk)
                    conn.commit()
                    statistics["success"] += len(chunk)
                    self.logger.debug(f"Inserted chunk {i//chunk_size + 1}: {len(chunk)} records")
                except Exception as e:
                    status = False
                    err_msg.append(str(e))
                    self.logger.error(f"Bulk insert failed for chunk {i//chunk_size + 1}: {str(e)}")

        # set log and spent time
        self._finalize_bulk_operation(statistics, "insert", total_count)
        return status, err_msg, statistics

    @async_wrap
    def bulk_update_data(self, table, data: list, where_key: str = "id", statistics_key: Optional[str] = None):
        """
        批量更新数据库中的数据。专用于大数据量、基于单一字段的简单更新场景。
        
        Args:
            table: SQLAlchemy表对象或表名字符串
            data: 要更新的数据列表，每个元素为字典，必须包含where_key字段
            where_key: 用于WHERE条件的字段名，默认为"id"
            statistics_key: 统计信息的键名，如果不提供则使用表名_update
            
        Returns:
            tuple: (status, err_msg, statistics) 元组
                
        Example:
            >>> # 基于ID字段的批量更新
            >>> update_data = [
            ...     {"id": 1, "name": "Alice Updated", "email": "alice.new@test.com"},
            ...     {"id": 2, "name": "Bob Updated", "email": "bob.new@test.com"}
            ... ]
            >>> await db.bulk_update_data("users", update_data, where_key="id")
            
        Note:
            - 每个记录必须包含where_key字段
            - 适用于大数据量的简单更新
            - 如需复杂WHERE条件，请使用begin_bulk_table_operations方法
        """
        table, statistics = self._prepare_bulk_operation(table, "update", statistics_key)
        total_count = len(data)

        if total_count == 0:
            return True, [], statistics
            
        status, err_msg = True, []
        chunk_size = self.chunk_size
        
        with self.get_conn() as conn:
            for i in range(0, total_count, chunk_size):
                chunk = data[i:i + chunk_size]
                try:
                    with conn.begin():
                        chunk_affected_rows = 0
                        for idx, record in enumerate(chunk):
                            # 验证where_key存在
                            if where_key not in record:
                                err_msg.append(f"Missing where_key '{where_key}' in record at index {i + idx}: {record}")
                                continue

                            # 构建WHERE条件, 去除where_key字段
                            condition = getattr(table.c, where_key) == record[where_key]
                            update_data = {k: v for k, v in record.items() if k != where_key}
                            
                            update_stmt = table.update().where(condition).values(update_data)
                            result = conn.execute(update_stmt)
                            chunk_affected_rows += result.rowcount

                        statistics["success"] += chunk_affected_rows
                        self.logger.debug(
                            f"Updated chunk {i//chunk_size + 1}: {chunk_affected_rows} rows"
                            f" affected from {len(chunk)} records")
                except Exception as e:
                    status = False
                    err_msg.append(str(e))
                    self.logger.error(f"Bulk update failed for chunk {i//chunk_size + 1}: {str(e)}")

        # set log and spent time
        self._finalize_bulk_operation(statistics, "update", total_count)
        return status, err_msg, statistics

    @async_wrap
    def bulk_dml_table(self, table_data: list, open_transaction: bool = True) -> tuple:
        """
        在单个事务中执行多表的批量操作（插入、更新、删除）。适用于需要在多个表之间保持数据一致性，数据量不大时。

        Args:
            table_data (list): 表操作数据列表，每个元素包含三个参数的字典：
                - table: SQLAlchemy表对象或表名字符串
                - data: 要操作的数据列表（插入/更新时）或WHERE条件字典（删除时）
                - operation: 操作类型，'insert', 'update', 'delete' 之一
                - where_conditions: WHERE条件字典（仅用于更新操作），可选
            open_transaction (bool): 是否开启事务，默认为True。当为False时，每个操作独立执行，不在事务中包装
            
        Returns:
            tuple: (success, error_messages, statistics) 元组
                
        Example:
            >>> table_operations = [
            ...     {
            ...         "table": "users",
            ...         "data": [{"name": "Alice", "email": "alice@test.com"}],
            ...         "operation": "insert"
            ...     },
            ...     {
            ...         "table": "orders", 
            ...         "data": {"status": "completed"},
            ...         "operation": "update",
            ...         "where_conditions": {"id": {"operator": "=", "value": 1}}
            ...     },
            ...     {
            ...         "table": "logs",
            ...         "operation": "delete",
            ...         "where_conditions": {"id": {"operator": "=", "value": 100}}
            ...     }
            ... ]
            >>> # 使用事务（默认）
            >>> success, errors, stats = await db.bulk_dml_table(table_operations)
            >>> # 不使用事务
            >>> success, errors, stats = await db.bulk_dml_table(table_operations, open_transaction=False)
        """
        # 验证输入参数
        if not isinstance(table_data, list) or not table_data:
            raise ValueError("table_data must be a non-empty list")

        statistics_list, error_messages = [], []
        
        try:
            with self.get_conn() as conn:
                # 根据open_transaction参数决定是否使用事务
                if open_transaction:
                    with conn.begin():  # 开始事务
                        self._execute_bulk_operations(conn, table_data, statistics_list, error_messages)
                else:
                    # 不使用事务，每个操作独立执行
                    self._execute_bulk_operations(conn, table_data, statistics_list, error_messages)
                            
        except Exception as e:
            # 操作失败，记录总体错误
            general_error = f"Bulk operations failed: {str(e)}"
            error_messages.append(general_error)
            self.logger.error(general_error)
        
        transaction_success = len(error_messages) == 0
        return transaction_success, error_messages, statistics_list

    def _execute_bulk_operations(self, conn, table_data: list, statistics_list: list, error_messages: list):
        """
        执行批量操作的核心逻辑。
        
        Args:
            conn: 数据库连接对象
            table_data: 表操作数据列表
            statistics_list: 统计信息列表
            error_messages: 错误信息列表
        """
        for i, operation_data in enumerate(table_data):
            try:
                table = operation_data['table']
                operation = operation_data['operation']
                affected_rows = 0
                
                # 初始化统计
                table, stati_info = self._prepare_bulk_operation(
                    table, operation, i)

                # 执行不同类型的操作
                if operation == 'insert':
                    data = operation_data['data']
                    conn.execute(table.insert(), data)
                    affected_rows = len(data)
                    
                elif operation == 'update':
                    data = operation_data['data']
                    where_conditions = operation_data['where_conditions']
                    condition = self.build_where_conditions(table, where_conditions)

                    # 构建更新语句
                    update_stmt = table.update().where(condition).values(data)
                    print(f"Update statement: {update_stmt}")
                    result = conn.execute(update_stmt)
                    affected_rows += result.rowcount
                        
                elif operation == 'delete':
                    where_conditions = operation_data['where_conditions']
                    condition = self.build_where_conditions(table, where_conditions)
                    delete_stmt = table.delete().where(condition)
                    result = conn.execute(delete_stmt)
                    affected_rows = result.rowcount
                    
                else:
                    raise ValueError(f"Unsupported operation: {operation}")

                stati_info["success"] += affected_rows
                total_count = len(data) if operation == 'insert' else 1
                self._finalize_bulk_operation(stati_info, operation, total_count)
                statistics_list.append(stati_info)

            except Exception as e:
                error_msg = f"Operation {i+1} failed ({operation} on {operation_data['table']}): {str(e)}"
                error_messages.append(error_msg)
                self.logger.error(error_msg)
                raise  # 重新抛出异常

    @async_wrap
    def bulk_dml_table_sql(self, sql_statements: list, open_transaction: bool = True) -> tuple:
        """
        批量执行原生SQL语句（增删改操作）。
        
        Args:
            sql_statements (list): SQL语句字符串列表
            open_transaction (bool): 是否开启事务，默认为True
            statistics_key (str, optional): 统计信息的键名
            
        Returns:
            tuple: (success, error_messages, statistics_list) 元组
                
        Example:
            >>> sql_statements = [
            ...     "INSERT INTO users (name, email) VALUES ('Alice', 'alice@test.com')",
            ...     "UPDATE users SET status = 'active' WHERE id = 1",
            ...     "DELETE FROM logs WHERE created_at < '2023-01-01'"
            ... ]
            >>> # 使用事务执行
            >>> success, errors, stats = await db.bulk_dml_table_sql(sql_statements)
            >>> # 不使用事务
            >>> success, errors, stats = await db.bulk_dml_table_sql(sql_statements, open_transaction=False)
            
        Note:
            - 直接执行SQL语句，请确保SQL安全性
            - 支持事务控制
            - 每个SQL语句都有独立的统计信息
        """
        # 验证输入参数
        if not isinstance(sql_statements, list) or not sql_statements:
            raise ValueError("sql_statements must be a non-empty list")

        total_count = len(sql_statements)
        if total_count == 0:
            return True, [], []
            
        status, error_messages, statistics_list = True, [], []
        
        def execute_sql():
            for i, sql in enumerate(sql_statements):    
                try:
                    # 为每个SQL语句创建独立的统计信息
                    _, statistics = self._prepare_bulk_operation(i, "", "sql_execution_" + str(i))
                    
                    # 执行SQL语句
                    result = conn.execute(text(sql))
                    
                    # 获取影响的行数
                    affected_rows = result.rowcount if hasattr(result, 'rowcount') else 0
                    statistics["success"] = affected_rows
                    
                    # 完成统计
                    self._finalize_bulk_operation(statistics, "sql_execution", 1)
                    statistics_list.append(statistics)
                    
                except Exception as e:
                    error_msg = f"SQL statement {i+1} failed: {str(e)} | SQL: {sql}"
                    raise Exception(error_msg)  # 重新抛出异常，在事务模式下会触发回滚

        try:
            with self.get_conn() as conn:
                # 根据open_transaction参数决定是否使用事务
                if open_transaction:
                    with conn.begin():  # 开始事务
                        execute_sql()
                else:
                    execute_sql()
        except Exception as e:
            # 操作失败，记录总体错误
            general_error = f"Bulk SQL execution failed: {str(e)}"
            error_messages.append(general_error)
            self.logger.error(general_error)
            status = False
        
        return status, error_messages, statistics_list
