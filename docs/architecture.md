# Architecture Overview

## Python Version

The project is developed using Python 3.10 or later. Ensure that your environment is set up with the correct Python version to avoid compatibility issues.

## System Architecture

该系统采用 FastAPI (0.115.14)框架构建，利用其高性能和易用性来实现 RESTful API, 以及页面功能的管理。目的是实现一个基于 Fastapi 的脚手架，以便于快速开发和部署应用程序。

## System 功能


### 权限管理

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

场景1：仅认证，无权限校验
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
@require_auth(module_name="Order", permission_names=["CREATE", "UPDATE"])
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