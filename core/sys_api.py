from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select

from core.auth import (
    oauth2_scheme,
    create_access_token,
    require_auth,
    get_current_user_from_request
)

from core import (
    main_db,
    get_module_id,
    get_permission_bit,
    get_permissions_names_from_bitmask,
    get_module_name
)

from core.models.user_models import Permission, User, Role, Module, RoleModulePermission
from core.config import settings
from core.models.user_models import User
from core.dynamic_api_manager import HTTP_FAILED, HTTP_SUCCESS, DynamicApiManager
from core.models.user_models import Module

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
    updated_at: Optional[datetime] = None
    is_active: bool = None
    description: Optional[str] = None
    last_login_time: Optional[datetime] = None

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
    "ignore_fields": {"response": ["password_hash"]},
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
    user_dict = user.model_dump(exclude_none=True)
    is_all_none = all(value is None for value in user_dict.values())
    if is_all_none:
        raise HTTPException(status_code=HTTP_FAILED, detail="No fields to update")

    data = None
    async with main_db.get_session() as session:
        existing_user = await session.execute(select(User).where(User.id == item_id))
        existing_user = existing_user.scalars().first()
        if not existing_user:
            raise HTTPException(
                status_code=HTTP_FAILED,
                detail="User not found",
            )

        for key, value in user_dict.items():
            setattr(existing_user, key, value)

        await session.commit()
        await session.flush()
        await session.refresh(existing_user)

        data = existing_user.to_dict()

    return {
        "code": HTTP_SUCCESS,
        "msg": "User updated successfully",
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

# Module API
module_config = {
    'module_name': "Module",
    'create': {'permission_name': "WRITE"},
    'read_one': {'permission_name': "READ"},
    'read_filter': {'permission_name': 'READ'},
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
}
module_router = DynamicApiManager(Module, module_config).get_router()

# Role API
role_config = {
    'module_name': "Role",
    'create': {'permission_name': "WRITE"},
    'update': {'permission_name': "UPDATE"},
    'delete': {'permission_name': "DELETE"},
    'read_filter': {'permission_name': 'READ'},
}
role_router = DynamicApiManager(Role, role_config).get_router()

# =============== 角色权限设置 API ===============

class ModulePermissionSchema(BaseModel):
    """模块权限配置 Schema"""
    module: str = Field(..., description="模块名称，例如 'User' 或 'Permission'")
    permissions: List[str] = Field(..., description="该模块下的权限名称列表，例如 ['READ', 'WRITE', 'DELETE']")

    class Config:
        json_schema_extra = {
            "example": {
                "module": "User",
                "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]
            }
        }

class RolePermissionSchema(BaseModel):
    """角色权限配置 Schema"""
    role_id: int = Field(..., description="角色 ID")
    module_permissions: List[ModulePermissionSchema] = Field(
        ..., description="角色拥有的模块权限列表"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role_id": 2,
                "module_permissions": [
                    {"module": "User", "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]},
                    {"module": "Permission", "permissions": ["READ", "WRITE"]},
                ]
            }
        }

class SetRolePermissionsRequest(BaseModel):
    """设置角色权限请求 Schema"""
    roles: List[RolePermissionSchema] = Field(
        ..., description="需要设置权限的角色列表"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "roles": [
                    {
                        "role_id": 2,
                        "module_permissions": [
                            {"module": "User", "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]},
                            {"module": "Permission", "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]},
                            {"module": "Module", "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]},
                        ],
                    }
                ]
            }
        }

@role_router.post("/sys_role/permissions", dependencies=[Depends(oauth2_scheme)])
@require_auth(module_name="Role", permission_names=["WRITE"])
async def set_role_permissions(request: Request, role_permissions: SetRolePermissionsRequest):
    """
    为角色设置模块权限

    Args:
        role_permissions: 角色权限配置
    """
    # 获取管理员 role_id, 管理员的权限不可更改和删除。
    role = await main_db.run_query(
        Role,
        where_conditions={"name": {"operator": "=", "value": "admin"}},
        return_clear=True
    )
    role_id = role[0]['id']

    # 汇总 role_id , 以及 module 和 permission 名称，
    # 通过 get_module_id 和 get_permission_bit 转换为 ID 和位. 如果校验失败，直接报错。
    update_role_ids = []
    role_module_permissions = []
    for role in role_permissions.roles:
        if role.role_id == role_id:
            continue

        update_role_ids.append(role.role_id)
        for module_perm in role.module_permissions:
            permission_dict = {
                "role_id": role.role_id,
                "module_id": None,
                "permissions": 0
            }
            module_id = get_module_id(module_perm.module)
            if module_id == 0:
                raise HTTPException(status_code=HTTP_FAILED, detail=f"Invalid module name: {module_perm.module}")
            permission_dict["module_id"] = module_id

            for perm_name in module_perm.permissions:
                perm_bit = get_permission_bit(perm_name)
                if perm_bit == 0:
                    raise HTTPException(status_code=HTTP_FAILED, detail=f"Invalid permission name: {perm_name}")
                permission_dict["permissions"] |= perm_bit
            role_module_permissions.append(permission_dict)

    if not update_role_ids:
        raise HTTPException(
            status_code=HTTP_FAILED,
            detail="The admin permissions cannot be modified, or the permissions to be updated are empty.")

    # check all role_id exist
    update_role_ids = list(set(update_role_ids))
    roles_in_db = await main_db.run_query(
        Role,
        where_conditions={"id": {"operator": "IN", "value": update_role_ids}},
        return_clear=True)
    if len(roles_in_db) != len(update_role_ids):
        existing_role_ids = {role["id"] for role in roles_in_db}
        missing_roles = set(update_role_ids) - existing_role_ids
        raise HTTPException(status_code=HTTP_FAILED, detail=f"Roles not found: {missing_roles}")

    # 删除已有的角色模块权限关联, 再批量插入新的关联
    dml_data =[
        {
            "table": RoleModulePermission,
            "operation": "delete",
            "where_conditions": {"role_id": {"operator": "IN", "value": update_role_ids}}
        },
        {
            "table": RoleModulePermission,
            "data": role_module_permissions,
            "operation": "insert"
        }
    ]

    success, errors, _ = await main_db.bulk_dml_table(dml_data)
    if not success:
        raise HTTPException(status_code=HTTP_FAILED, detail=f"Failed to set role permissions: {errors}")

    return {
        "code": HTTP_SUCCESS,
        "data": role_permissions.model_dump()
    }


@role_router.get("/sys_role/permissions", dependencies=[Depends(oauth2_scheme)])
@require_auth(module_name="Role", permission_names=["READ"])
async def get_role_permissions(request: Request):
    """获取角色权限"""
    # 根据 token 获取当前用户
    current_user = await get_current_user_from_request(request)
    role_id = current_user.get("role_id")

    role_module_perms = await main_db.run_query(
        RoleModulePermission,
        where_conditions={"role_id": {"operator": "=", "value": role_id}},
        return_clear=True
    )


    # 遍历结果，转换 module_id 和 permissions
    role_permissions = []
    for perm in role_module_perms:
        module_perms = ModulePermissionSchema(
            module=get_module_name(perm["module_id"]),
            permissions=get_permissions_names_from_bitmask(perm["permissions"])
        )

        role_perms = RolePermissionSchema(
            role_id=perm["role_id"],
            module_permissions=[module_perms]
        )
        role_permissions.append(role_perms.model_dump())

    return {
        "code": HTTP_SUCCESS,
        "data": role_permissions
    }