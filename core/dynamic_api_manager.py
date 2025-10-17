"""
Dynamic API Manager

为 SQLAlchemy 模型自动生成 CRUD API 的管理器
"""

from datetime import datetime
from typing import Type, Dict, Any, Optional, List
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, create_model, Field
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import inspect

from core.auth import require_auth, oauth2_scheme

from core import load_permissions, main_db
from core.constant import HTTP_FAILED, HTTP_SUCCESS


class FilterRequest(BaseModel):
    """
    过滤查询请求模型
    
    用于动态API的过滤查询功能，支持复杂的条件查询、排序、分组和分页。
    """
    
    where_conditions: Optional[Dict[str, Any]] = Field(
        None,
        title="WHERE查询条件",
        description=(
            "支持复杂WHERE条件查询。\n\n"
            "**操作符：** =, !=, >, <, >=, <=, LIKE, IN, BETWEEN, IS_NULL\n\n"
            "**逻辑：** 支持 AND/OR 嵌套组合\n\n"
            "**格式：** `{\"field\": {\"operator\": \"=\", \"value\": \"data\"}}`"),
        example={
            "and": [
                {"is_active": {"operator": "=", "value": True}},
                {"or": [
                    {"username": {"operator": "LIKE", "value": "%admin%"}},
                    {"email": {"operator": "LIKE", "value": "%@admin.com"}}
                ]}
            ]
        }
    )
    
    select_columns: Optional[List[str]] = Field(
        None,
        title="查询列名",
        description=(
            "指定要查询的列名列表。\n\n"
            "**功能说明：**\n"
            "- 如果为空或None，则查询所有列\n"
            "- 可以指定具体的列名来优化查询性能\n"
            "- 列名必须是模型中实际存在的字段\n\n"
            "**性能提示：** 只查询需要的列可以显著提升查询性能"
        ),
        example=["id", "username", "email", "created_at"]
    )
    
    order_by_columns: Optional[List[str]] = Field(
        None,
        title="排序列名",
        description=(
            "排序列名列表，支持多列排序。\n\n"
            "**排序规则：**\n"
            "- 默认为升序(ASC)排序\n"
            "- 支持多列组合排序\n\n"
            "**示例格式：** `[\"created_at DESC\", \"username\", \"id\"]`"
        ),
        example=["created_at DESC", "username", "id"]
    )
    
    group_by_columns: Optional[List[str]] = Field(
        None,
        title="分组列名",
        description=(
            "分组列名列表，用于GROUP BY查询。\n\n"
            "**功能特性：**\n"
            "- 用于GROUP BY查询和数据聚合\n"
            "- 当指定分组列时，会自动添加COUNT()聚合函数\n"
            "- 通常与聚合查询一起使用\n\n"
            "**注意事项：** 使用分组查询时，select_columns应该只包含分组字段或聚合函数"
        ),
        example=["department", "status"]
    )
    
    limit: Optional[int] = Field(
        50,
        title="查询限制",
        description=(
            "限制返回的记录数量，用于分页和性能优化。\n\n"
            "**参数说明：**\n"
            "- 默认值：50\n"
            "- 取值范围：1-100000\n"
            "- 用于控制单次查询的数据量\n\n"
            "**性能建议：** 设置合理的上限以避免查询过多数据影响性能"
        ),
        ge=1,
        le=100000,
        example=100
    )
    
    offset: Optional[int] = Field(
        0,
        title="查询偏移量",
        description=(
            "查询偏移量（跳过的记录数），与limit配合实现分页功能。\n\n"
            "**参数说明：**\n"
            "- 默认值：0（从第一条记录开始）\n"
            "- 计算公式：`offset = (page_number - 1) * limit`\n\n"
            "**分页示例：**\n"
            "- 第1页：`offset=0, limit=10`\n"
            "- 第2页：`offset=10, limit=10`\n"
            "- 第3页：`offset=20, limit=10`"
        ),
        ge=0,
        example=0
    )
    
class ReponseModel(BaseModel):
    code: int
    msg: str
    data: Optional[Any] = None

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
    
    def _apply_schema_filter(self, data: Any, validate_schema: Optional[Type[BaseModel]]) -> Any:
        """
        应用Schema过滤，只返回Schema定义的字段
        
        Args:
            data: 原始数据（单个字典或字典列表）
            validate_schema: 可选的Pydantic模型类
            
        Returns:
            过滤后的数据
        """
        if not validate_schema or not data:
            return data 
        
        # 处理单个字典
        if isinstance(data, dict):
            schema_instance = validate_schema(**data)
            return schema_instance.model_dump()
        
        # 处理字典列表
        elif isinstance(data, list):
            filtered_data = []
            for item in data:
                if isinstance(item, dict):
                    schema_instance = validate_schema(**item)
                    filtered_data.append(schema_instance.model_dump())
                else:
                    filtered_data.append(item)
            return filtered_data
        
        return data
            
    
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
        
        if 'read_one' in self.config:
            self._register_read_one_route(prefix)
        
        if 'read_filter' in self.config:
            self._register_read_filter_route(prefix)
        
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
            dependencies=[Depends(oauth2_scheme)],
            response_model=ReponseModel
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def create_handler(request: Request, data: self.CreateSchema): # type: ignore
            """创建新记录"""

            data = data.model_dump()
            status, data = await main_db.add(self.model, data)
            code = HTTP_SUCCESS if status else HTTP_FAILED
            
            await self.refresh_permissions_cache(status)

            return {
                "code": code,
                "msg": "Success to create" if status else "Failed to create",
                "data": data
            }
    
    def _register_read_one_route(self, prefix: str):
        """注册查询单个记录路由"""
        permission_name = self.config['read_one']['permission_name']
        validate_schema = self.config['read_one'].get('validate_schema', None)
        
        @self.router.get(
            f"{prefix}/{{item_id}}",
            summary=f"Get {self.model_name} by ID",
            description=f"Retrieve a specific {self.model_name} record by ID",
            dependencies=[Depends(oauth2_scheme)],
            response_model=ReponseModel
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def read_one_handler(request: Request, item_id: int):
            """查询单个记录"""
            result = await main_db.run_query(
                table=self.model,
                where_conditions={"id": {"operator": "=", "value": item_id}},
                return_clear=True
            )
            
            code = HTTP_SUCCESS if result else HTTP_FAILED
            data = None
            
            if result and code == HTTP_SUCCESS:
                # 应用Schema过滤
                data = self._apply_schema_filter(result[0], validate_schema)
                    
            return {
                "code": code,
                "msg": "Query successful" if code == HTTP_SUCCESS else "Query failed",
                "data": data
            }

    def _register_read_filter_route(self, prefix: str):
        """注册过滤查询路由"""
        permission_name = self.config['read_filter']['permission_name']
        validate_schema = self.config['read_filter'].get('validate_schema', None)
        
        @self.router.post(
            f"{prefix}/filter",
            summary=f"灵活过滤查询 {self.model_name} 记录",
            description=f"""对 {self.model_name} 表进行灵活的过滤查询。""",
            dependencies=[Depends(oauth2_scheme)],
            response_model=ReponseModel
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def read_filter_handler(request: Request, filter_request: FilterRequest):
            """过滤查询记录"""
        
            # 调用 run_query 方法，固定 return_clear=True
            result = await main_db.run_query(
                table=self.model,
                select_columns=filter_request.select_columns,
                where_conditions=filter_request.where_conditions,
                group_by_columns=filter_request.group_by_columns,
                order_by_columns=filter_request.order_by_columns,
                limit=filter_request.limit,
                offset=filter_request.offset,
                return_clear=True
            )
            
            # 应用Schema过滤
            processed_data = self._apply_schema_filter(result, validate_schema)
            data = {
                "data": processed_data,
                "total": len(processed_data) if processed_data else 0
            }
             
            return {
                "code": HTTP_SUCCESS,
                "msg": "Query successful",
                "data": data
            }
    
    def _register_update_route(self, prefix: str):
        """注册更新路由"""
        permission_name = self.config['update']['permission_name']
        
        @self.router.put(
            f"{prefix}/{{item_id}}",
            summary=f"Update {self.model_name}",
            description=f"Update a specific {self.model_name} record",
            dependencies=[Depends(oauth2_scheme)],
            response_model=ReponseModel
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def update_handler(request: Request, item_id: int, data: self.UpdateSchema): # type: ignore
            """更新记录"""
            data = data.dict()
            
            # check if record exists
            result = await main_db.run_query(
                table=self.model,
                where_conditions={"id": {"operator": "=", "value": item_id}},
                return_clear=True
            )
            if not result:
                return {
                    "code": HTTP_FAILED,
                    "msg": f"{self.model_name} with ID {item_id} does not exist",
                    "data": None
                }
            
            # update date
            filtered_data = {k: v for k, v in data.items() if v is not None}
            if not filtered_data:
                return {
                    "code": HTTP_FAILED,
                    "msg": "No fields to update",
                    "data": None
                }
            
            status, data = await main_db.update(
                self.model,
                filtered_data,
                main_db.build_where_conditions(self.model, {"id": {"operator": "=", "value": item_id}})
            )
            code = HTTP_SUCCESS if status else HTTP_FAILED
            msg = "Update successful" if status else "Update failed"

            await self.refresh_permissions_cache(status)

            return {
                "code": code,
                "msg": msg,
                "data": data
            }
    
    def _register_delete_route(self, prefix: str):
        """注册删除路由"""
        permission_name = self.config['delete']['permission_name']
        
        @self.router.delete(
            f"{prefix}/{{item_id}}",
            summary=f"Delete {self.model_name}",
            description=f"Delete a specific {self.model_name} record",
            dependencies=[Depends(oauth2_scheme)],
            response_model=ReponseModel
        )
        @require_auth(
            module_name=self.module_name, 
            permission_names=[permission_name]
        )
        async def delete_handler(request: Request, item_id: int):
            """删除记录"""
            # check if record exists
            result = await main_db.run_query(
                table=self.model,
                where_conditions={"id": {"operator": "=", "value": item_id}},
                return_clear=True
            )
            if not result:
                return {
                    "code": HTTP_FAILED,
                    "msg": f"{self.model_name} with ID {item_id} does not exist",
                    "data": None
                }
            
            status, affected = await main_db.delete(
                self.model,
                main_db.build_where_conditions(self.model, {"id": {"operator": "=", "value": item_id}})
            )

            await self.refresh_permissions_cache(status)

            return {
                "code": HTTP_SUCCESS if status else HTTP_FAILED,
                "msg": "Delete successful" if status else "Delete failed",
                "data": {"id": item_id}
            }

    def get_router(self) -> APIRouter:
        """获取生成的路由器"""
        return self.router

    async def refresh_permissions_cache(self, code):
        """刷新权限缓存"""
        # 如果 module_name 是 Permission 或者 Module，对应 update/create/delete 操作需要刷新权限缓存
        if code == HTTP_SUCCESS and self.module_name in ['Permission', 'Module']:
            await load_permissions()


# 使用示例
"""
from core.models.user_models import User
from core.dynamic_api_manager import DynamicApiManager
from pydantic import BaseModel

# 定义自定义返回 Schema (可选)
class UserPublicSchema(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

# 配置动态API
user_config = {
    'module_name': "User",
    'create': {'permission_name': "CREATE"},
    'read_one': {
        'permission_name': "READ",
        'validate_schema': UserPublicSchema  # 可选：指定返回数据的Schema
    },
    'read_filter': {
        'permission_name': "READ",
        'validate_schema': UserPublicSchema  # 可选：对列表查询也应用Schema过滤
    },
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
}

user_api = DynamicApiManager(User, user_config)
app.include_router(user_api.get_router(), prefix="/api/dynamic", tags=["Dynamic User API"])
"""
