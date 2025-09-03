"""
Dynamic API Manager

为 SQLAlchemy 模型自动生成 CRUD API 的管理器
"""

from datetime import datetime
from typing import Type, Dict, Any, Optional
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, create_model
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect

from core.auth import require_auth, oauth2_scheme

from core import main_db
from core.constant import HTTP_FAILED, HTTP_SUCCESS


class DynamicApiManager:
    """
    动态 API 管理器
    
    根据 SQLAlchemy 模型和配置自动生成 CRUD API
    """
    
    def __init__(self, model: Type[DeclarativeBase], config: Dict[str, Any]):
        """
        初始化动态 API 管理器
        
        Args:
            model: SQLAlchemy 模型类
            config: API 配置字典
        """
        self.model = model
        self.config = config
        self.router = APIRouter()
        
        # 获取模型信息
        self.table_name = model.__tablename__
        self.model_name = model.__name__
        self.module_name = config.get('module_name', self.model_name)
        
        # 生成 Pydantic 模型
        self._generate_schemas()
        
        # 注册路由
        self._register_routes()
    
    def _generate_schemas(self):
        """生成 Pydantic 模型用于请求和响应"""
        # 获取 SQLAlchemy 模型的字段信息
        mapper = inspect(self.model)
        
        # 构建字段字典
        fields = {}
        response_fields = {}
        
        for column in mapper.columns:
            column_name = column.name
            python_type = column.type.python_type
            
            # 处理可选字段
            if column.nullable:
                python_type = Optional[python_type]
            
            # 响应模型包含所有字段
            response_fields[column_name] = (python_type, ...)
            
            # 创建和更新模型排除自动生成的字段
            if column_name not in ['id', 'created_at', 'updated_at']:
                if column.nullable or column.default is not None:
                    fields[column_name] = (python_type, None)
                else:
                    fields[column_name] = (python_type, ...)
        
        # 创建 Pydantic 模型
        self.CreateSchema = create_model(
            f"{self.model_name}Create",
            **fields
        )
        
        self.UpdateSchema = create_model(
            f"{self.model_name}Update",
            **{k: (v[0], None) for k, v in fields.items()}  # 更新时所有字段都是可选的
        )
        
        self.ResponseSchema = create_model(
            f"{self.model_name}Response",
            **response_fields
        )
    
    def _register_routes(self):
        """注册所有 CRUD 路由"""
        prefix = f"/{self.table_name}"
        
        # 注册各种操作
        if 'create' in self.config:
            self._register_create_route(prefix)
        
        if 'read_all' in self.config:
            self._register_read_all_route(prefix)
        
        if 'read_one' in self.config:
            self._register_read_one_route(prefix)
        
        if 'update' in self.config:
            self._register_update_route(prefix)
        
        if 'delete' in self.config:
            self._register_delete_route(prefix)
    
    def _register_create_route(self, prefix: str):
        """注册创建路由"""
        permission_name = self.config['create']['permission_name']
        
        @self.router.post(
            prefix,
            summary=f"Create {self.model_name}",
            description=f"Create a new {self.model_name} record",
            dependencies=[Depends(oauth2_scheme)]
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def create_handler(request: Request, data: self.CreateSchema): # type: ignore
            """创建新记录"""

            data = data.dict()
            data["created_at"] = datetime.now()
            insert_data = [
                {
                    "table": self.model.__table__,
                    "data": [data],
                    "operation": "insert"
                }
            ]
            status, msg, _ = await main_db.bulk_dml_table(insert_data)
            code = HTTP_SUCCESS
            if not status:
                code = HTTP_FAILED

            return {
                "code": code,
                "msg": msg,
                "data": data
            }
    
    def _register_read_all_route(self, prefix: str):
        """注册查询所有记录路由"""
        permission_name = self.config['read_all']['permission_name']
        
        @self.router.get(
            prefix,
            summary=f"Get all {self.model_name} records",
            description=f"Retrieve all {self.model_name} records",
            dependencies=[Depends(oauth2_scheme)]
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def read_all_handler(request: Request):
            """查询所有记录"""
            # TODO: 实现数据库操作
            return [{
                "message": f"Get all {self.model_name} records",
                "operation": "read_all",
                "model": self.model_name
            }]
    
    def _register_read_one_route(self, prefix: str):
        """注册查询单个记录路由"""
        permission_name = self.config['read_one']['permission_name']
        
        @self.router.get(
            f"{prefix}/{{item_id}}",
            summary=f"Get {self.model_name} by ID",
            description=f"Retrieve a specific {self.model_name} record by ID",
            dependencies=[Depends(oauth2_scheme)]
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def read_one_handler(request: Request, item_id: int):
            """查询单个记录"""
            # TODO: 实现数据库操作
            return {
                "message": f"Get {self.model_name} with ID: {item_id}",
                "operation": "read_one",
                "model": self.model_name,
                "id": item_id
            }
    
    def _register_update_route(self, prefix: str):
        """注册更新路由"""
        permission_name = self.config['update']['permission_name']
        
        @self.router.put(
            f"{prefix}/{{item_id}}",
            summary=f"Update {self.model_name}",
            description=f"Update a specific {self.model_name} record",
            dependencies=[Depends(oauth2_scheme)]
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def update_handler(request: Request, item_id: int, data: self.UpdateSchema): # type: ignore
            """更新记录"""
            # TODO: 实现数据库操作
            return {
                "message": f"Update {self.model_name} ID: {item_id} with data: {data}",
                "operation": "update",
                "model": self.model_name,
                "id": item_id
            }
    
    def _register_delete_route(self, prefix: str):
        """注册删除路由"""
        permission_name = self.config['delete']['permission_name']
        
        @self.router.delete(
            f"{prefix}/{{item_id}}",
            summary=f"Delete {self.model_name}",
            description=f"Delete a specific {self.model_name} record",
            dependencies=[Depends(oauth2_scheme)]
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def delete_handler(request: Request, item_id: int):
            """删除记录"""
            # TODO: 实现数据库操作
            return {
                "message": f"Delete {self.model_name} with ID: {item_id}",
                "operation": "delete",
                "model": self.model_name,
                "id": item_id
            }
    
    def get_router(self) -> APIRouter:
        """获取生成的路由器"""
        return self.router


# 使用示例
"""
from core.models.user_models import User
from core.dynamic_api_manager import DynamicApiManager

user_config = {
    'module_name': "User",
    'create': {'permission_name': "CREATE"},
    'read_all': {'permission_name': "READ"},
    'read_one': {'permission_name': "READ"},
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
}

user_api = DynamicApiManager(User, user_config)
app.include_router(user_api.get_router(), prefix="/api/dynamic", tags=["Dynamic User API"])
"""
