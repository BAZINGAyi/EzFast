from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from core.auth import (
    oauth2_scheme, 
    create_access_token, 
    require_auth,
    get_current_user_from_request
)

from core import (
    main_db,
)
    
from core.models.user_models import Permission, User
from core.config import settings

# 创建系统 API 路由器
router = APIRouter()

# =============== 认证相关路由 ===============

@router.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    用户登录接口
    
    为 Swagger UI 提供认证功能，返回 JWT token
    """
    user = await main_db.run_query(
        User,
        where_conditions={"username": {"operator": "=", "value": form_data.username}},
        return_clear=True)
    if not user or (user and User(**user[0]).check_password(form_data.password) is False):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = user[0]["id"]
    access_token = create_access_token(data={"user_id": user_id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 * 2
    }

from core.models.user_models import User
from core.dynamic_api_manager import HTTP_FAILED, HTTP_SUCCESS, DynamicApiManager

# User API
class CommonUserSchema(BaseModel):
    username: str
    email: str
    phone_number: Optional[str] = None
    role_id: int
    locale: Optional[str] = None
    
class ListUserSchema(CommonUserSchema):
    id: int
    created_at: Optional[datetime] = None
    
class CreateUserSchema(CommonUserSchema):
    password: str

class UpdateUserSchema(BaseModel):
    password: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role_id: Optional[int] = None
    locale: Optional[str] = None
    username: Optional[str] = None

user_config = {
    'module_name': "User",
    'read_one': {'permission_name': "READ", "validate_schema": ListUserSchema},
    'read_filter': {'permission_name': 'READ', "validate_schema": ListUserSchema},
    'delete': {'permission_name': "DELETE"},
}
user_router = DynamicApiManager(User, user_config).get_router()

# 对于创建和修改用户操作，单独定义 api 以处理密码哈希
@user_router.post("/user", dependencies=[Depends(oauth2_scheme)])
@require_auth(module_name="User", permission_names=["WRITE"])
async def create_user(request: Request, user: CreateUserSchema):
    """创建用户 - 处理密码哈希"""
    user_dict = user.model_dump()
    password = user_dict.pop("password")

    
    # 生成密码哈希，及创建时间等属性
    user = User(**user_dict)
    user.set_password(password)
    user_dict = user.to_dict()
    user_dict["password_hash"] = user.password_hash
    status, data = await main_db.add(User, user_dict)
    code = HTTP_SUCCESS if status else HTTP_FAILED
    if not status:
        raise HTTPException(status_code=HTTP_FAILED, detail="Failed to create user")
    
    return {
        "code": code,
        "msg": "User created successfully" if status else "Failed to create user",
        "data": data
    }
    
@user_router.put("/user/{item_id}", dependencies=[Depends(oauth2_scheme)])
@require_auth(module_name="User", permission_names=["UPDATE"])
async def update_user(request: Request, item_id: int, user: UpdateUserSchema):
    """更新用户 - 处理密码哈希"""
    user_dict = user.model_dump()
    is_all_none = all(value is None for value in user_dict.values())
    if is_all_none:
        raise HTTPException(status_code=HTTP_FAILED, detail="No fields to update")
    
    # check user exists
    existing_user = await main_db.run_query(
        User,
        where_conditions={"id": {"operator": "=", "value": item_id}},
        return_clear=True)
    if not existing_user:
        raise HTTPException(
            status_code=HTTP_FAILED,
            detail="User not found",
        )

    # 生成密码哈希，及创建时间等属性
    user = User(**user_dict)
    password = user_dict.pop("password", None)
    if password:
        user.set_password(password)
    user_dict = user.to_dict()
    user_dict["password_hash"] = user.password_hash
    filtered_data = {k: v for k, v in user_dict.items() if v is not None}
    status, data = await main_db.update(
        User,
        filtered_data,
        main_db.build_where_conditions(User, {"id": {"operator": "=", "value": item_id}}))
    code = HTTP_SUCCESS if status else HTTP_FAILED
    if not status:
        raise HTTPException(status_code=HTTP_FAILED, detail=data)

    return {
        "code": code,
        "msg": "User updated successfully" if status else "Failed to update user",
        "data": data
    }

# Permission API
permission_config = {
    'module_name': "Permission",
    'create': {'permission_name': "WRITE"},
    'read_one': {'permission_name': "READ"},
    'read_filter': {'permission_name': 'READ'},
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
}
permission_router = DynamicApiManager(Permission, permission_config).get_router()
