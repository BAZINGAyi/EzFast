# Architecture Overview

## Python Version

The project is developed using Python 3.10 or later. Ensure that your environment is set up with the correct Python version to avoid compatibility issues.

## System Architecture

该系统采用 FastAPI (0.115.14)框架构建，利用其高性能和易用性来实现 RESTful API, 以及页面功能的管理。目的是实现一个基于 Fastapi 的脚手架，以便于快速开发和部署应用程序。

## System 功能


## 权限管理

### 表结构说明

1. 表定义于 `core/models/user_models.py` 文件中，主要包括以下几个模型：
   - `User`: 用户模型，包含用户基本信息和权限相关字段.
     - 提供 set_password 和 check_password 方法用于密码管理。
   - `Role`: 角色模型，定义用户角色。
   - `Module`: 模块模型，定义系统的模块。
   - `Permission`: 权限模型，定义系统的权限。注意这里使用 `permission_bit` 列，唯一表示权限，进行位运算。
   - `ModulePermission`: 模块与权限关联模型，定义模块所拥有的权限。用于前端展示和操作，一个模块具有哪些权限。
   - `RoleModulePermission`: 角色与模块，权限关联模型，定义角色在特定模块上的权限。这里 permissions 是一个位掩码，表示角色在该模块下的所有权限。
     - 提供 set_permission 和 remove_permission, has_permission 方法用于权限管理。
   - `OperationLog`: 操作日志模型，记录用户在系统中的操作行为。


### 权限设计说明

系统采用基于 JWT Token 的认证机制和位掩码（Bitmask）的权限控制体系，提供灵活且高效的访问控制解决方案。

#### 1. 认证机制

JWT Token 获取
```http
POST /api/sys/auth/login
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

返回响应：
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
}
```

Token 使用
在后续 API 请求中，需要在 Header 中携带 Token：
```http
Authorization: Bearer <access_token>
```

#### 2. 权限校验装饰器

系统提供 `@require_auth` 装饰器，支持多种认证和权限校验场景：

场景1：只需要认证，不检查权限,oauth2_scheme的作用是为了 swagger 发送时，带认证头。
```python
@router.get("/simple-data", dependencies=[Depends(oauth2_scheme)])
@require_auth()
async def get_simple_data(request: Request):
    """只验证 JWT Token 有效性，不检查具体权限"""
    return {"data": "some protected data"}
```

场景2：认证 + 权限校验
```python
@router.post("/users", dependencies=[Depends(oauth2_scheme)])
@require_auth(module_name="User", permission_names=["WRITE", "READ"])
async def create_user(request: Request):
    """需要在 User 模块具有 WRITE 和 READ 权限"""
    user_id = request.state.current_user_id
    return {"message": f"User {user_id} created a new user"}
```

#### 3. 用户信息获取

获取当前用户 ID
```python
@router.get("/my-data", dependencies=[Depends(oauth2_scheme)])
@require_auth()
async def get_my_data(request: Request):
    user_id = request.state.current_user_id  # 从请求状态中获取
    return {"user_id": user_id}
```

获取完整用户信息
```python
@router.get("/profile", dependencies=[Depends(oauth2_scheme)])
@require_auth()
async def get_profile(request: Request):
    user = await get_current_user_from_request(request)  # 查询数据库获取完整信息
    return {"username": user["username"], "email": user["email"]}
```

#### 4. 权限系统架构

权限位运算机制
- `Permission` 表中的 `permission_bit` 字段使用位运算表示权限
- `RoleModulePermission` 表中的 `permissions` 字段是位掩码，存储角色在特定模块的所有权限
- 权限检查通过位运算 `&` 操作高效完成

权限检查流程
1. **Token 解析**：提取 JWT Token 中的 `user_id`
2. **模块解析**：将模块名称转换为 `module_id`
3. **权限转换**：将权限名称列表转换为位掩码
4. **数据库查询**：查询用户在指定模块的权限位掩码
5. **位运算校验**：使用 `has_permission()` 方法进行权限验证

权限管理方法
```python
# RoleModulePermission 模型提供的权限操作方法
role_permission.set_permission(permission_bitmask)     # 设置权限
role_permission.remove_permission(permission_bitmask) # 移除权限
role_permission.has_permission(permission_bitmask)    # 检查权限
```

#### 5. API 权限配置指南

基本配置步骤
1. **添加依赖项**：`dependencies=[Depends(oauth2_scheme)]` 用于 Swagger UI 认证
2. **使用装饰器**：根据业务需求选择合适的 `@require_auth` 配置，注意 request 参数必须设置，会从 request 读取 token，进行验证。
3. **权限参数**：
   - `module_name`：字符串形式的模块名称
   - `permission_names`：权限名称列表，支持组合权限

权限配置示例
```python
# 只需认证
@require_auth()

# 需要单个权限
@require_auth(module_name="User", permission_names=["READ"])

# 需要多个权限（AND 逻辑）
@require_auth(module_name="User", permission_names=["READ", "WRITE"])

# 不同模块的权限配置
@require_auth(module_name="Order", permission_names=["WRITE", "UPDATE"])
```

#### 6. 错误处理

系统采用分层异常处理机制，提供统一的错误响应格式：

HTTP 异常处理 (`http_exception_handler`)
处理认证和权限相关的 HTTP 异常：
- `401 Unauthorized`：Token 无效、过期或缺失
- `403 Forbidden`：权限不足
- `500 Internal Server Error`：模块或权限配置错误

全局异常处理 (`global_exception_handler`)
捕获所有未处理的异常，记录详细错误日志并返回通用错误响应。

统一响应格式
```json
{
    "code": 401,
    "msg": "Token is invalid or expired"
}
```

## 动态 API 注册功能

系统提供了基于 SQLAlchemy 模型的动态 API 生成功能，通过 `DynamicApiManager` 类自动为数据库表生成标准的 CRUD API，极大减少了重复代码的编写。

### 1. 核心组件

#### DynamicApiManager 类
位于 `core/dynamic_api_manager.py`，是动态 API 生成的核心组件：

**主要功能：**
- 自动生成 Pydantic Schema（CreateSchema、UpdateSchema、ResponseSchema）
- 基于配置自动注册 CRUD 路由
- 集成权限验证和 JWT 认证
- 支持自定义 Schema 过滤返回字段
- 提供统一的响应格式
- 基于 SQLAlchemy 模型自动生成 Pydantic Schema

#### FilterRequest 模型
提供强大的过滤查询功能，支持：
- **复杂条件查询**：支持 AND/OR 逻辑组合、多种操作符（=, !=, >, <, >=, <=, LIKE, IN, BETWEEN, IS_NULL）
- **字段选择**：指定查询列名优化性能
- **排序分组**：支持多列排序和 GROUP BY 聚合
- **分页功能**：通过 limit 和 offset 实现分页

### 2. 配置格式

```python
user_config = {
    'module_name': "User",  # 权限模块名称
    'create': {'permission_name': "WRITE"},
    'read_one': {
        'permission_name': "READ",
        'validate_schema': UserPublicSchema  # 可选：自定义返回Schema
    },
    'read_filter': {
        'permission_name': "READ",
        'validate_schema': UserPublicSchema  # 可选：过滤返回字段
    },
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
}

# 创建并注册动态 API
user_api = DynamicApiManager(User, user_config)
app.include_router(user_api.get_router(), prefix="/api", tags=["User API"])
```

### 3. 生成的 API 端点

| 操作 | HTTP方法 | 路径 | 说明 |
|-----|---------|------|------|
| 创建 | POST | `/{table_name}` | 创建新记录，使用动态生成的 CreateSchema |
| 查询单个 | GET | `/{table_name}/{id}` | 根据 ID 查询单条记录 |
| 过滤查询 | POST | `/{table_name}/filter` | 使用 FilterRequest 进行复杂查询 |
| 更新 | PUT | `/{table_name}/{id}` | 更新指定记录，使用 UpdateSchema |
| 删除 | DELETE | `/{table_name}/{id}` | 删除指定记录 |

### 4. 权限集成

每个 API 端点都自动集成权限验证：
```python
@require_auth(module_name="User", permission_names=["READ"])
```
- 支持基于模块和权限名称的细粒度访问控制
- 自动验证 JWT Token 有效性
- 权限不足时返回 403 错误

### 5. Schema 自动生成

**CreateSchema**：基于表结构自动生成，排除自动字段（id、created_at、updated_at）
**UpdateSchema**：所有字段均为可选，支持部分更新
**ResponseSchema**：包含所有表字段用于响应

### 6. 实际应用示例

#### 系统API模块（sys_api.py）
提供了完整的用户管理和权限管理 API：

**用户管理 API**：
```python
# 标准 CRUD + 自定义密码处理
user_config = {
    'module_name': "User",
    'read_one': {'permission_name': "READ", "validate_schema": ListUserSchema},
    'read_filter': {'permission_name': 'READ', "validate_schema": ListUserSchema},
    'delete': {'permission_name': "DELETE"},
}

# 自定义创建和更新 API 处理密码哈希
@user_router.post("/user")
@require_auth(module_name="User", permission_names=["WRITE"])
async def create_user(request: Request, user: CreateUserSchema):
    # 处理密码哈希逻辑
```

**权限管理 API**：
```python
permission_config = {
    'module_name': "Permission",
    'create': {'permission_name': "WRITE"},
    'read_one': {'permission_name': "READ"},
    'read_filter': {'permission_name': 'READ'},
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
}
```

### 7. 高级特性

#### 自定义 Schema 过滤
支持通过 `validate_schema` 参数过滤返回字段：
```python
class UserPublicSchema(BaseModel):
    id: int
    username: str
    email: str  # 只返回公开字段，隐藏敏感信息

'read_one': {
    'permission_name': "READ",
    'validate_schema': UserPublicSchema
}
```

#### 复杂查询示例
```python
filter_request = {
    "where_conditions": {
        "and": [
            {"is_active": {"operator": "=", "value": True}},
            {"or": [
                {"username": {"operator": "LIKE", "value": "%admin%"}},
                {"email": {"operator": "LIKE", "value": "%@admin.com"}}
            ]}
        ]
    },
    "select_columns": ["id", "username", "email"],
    "order_by_columns": ["created_at DESC"],
    "limit": 50,
    "offset": 0
}
```
