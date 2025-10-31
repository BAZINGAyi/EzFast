from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
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
from core.dynamic_api_manager import HTTP_FAILED, HTTP_SUCCESS, DynamicApiManager

from core.schemas.user_schema import (
    ListUserSchema,
    CreateUserSchema,
    UpdateUserSchema,
    RolePermissionsResponse,
    RolePermissionSchema,
    ModulePermissionSchema,
    SetRolePermissionsRequest,
    RoleModulePermissionsResponse,
    RoleModulePermissionsSchema,
    ParentModulePermissionSchema,
    SubModulePermissionSchema,
    ModulePermissionsTemplateSchema,
    ModulePermissionsTemplateResponse
)

from datetime import timedelta, datetime
import asyncio

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

    # 更新用户最后登录时间
    await main_db.update(
        User, {"last_login_time": datetime.now()}, User.id == user[0]["id"])

    user_id = user[0]["id"]
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 * 10
    access_token = create_access_token(
        data={"user_id": user_id, "role_id": user[0]["role_id"]}, expires_delta=timedelta(seconds=expires_in))
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in
    }

# 事先创建，避免路由冲突问题
user_router = APIRouter()

async def _get_role_permissions(role_id: int):
    # 1. 查询角色的模块权限
    role_module_perms = await main_db.run_query(
        RoleModulePermission,
        where_conditions={"role_id": {"operator": "=", "value": role_id}},
        return_clear=True
    )

    # 2. 查询所有模块信息（包含父子关系）
    all_modules = await main_db.run_query(
        Module,
        return_clear=True
    )

    # 4. 构建权限映射表（module_id -> permissions）
    permission_map = {}
    for perm in role_module_perms:
        module_id = perm["module_id"]
        permissions = get_permissions_names_from_bitmask(perm["permissions"])
        permission_map[module_id] = permissions

    # 5. 找出所有父模块（parent_id 为 None 的模块）
    parent_modules = [m for m in all_modules if m.get("parent_id") is None]

    # 6. 构建层级结构
    parent_module_permissions = []
    for parent in parent_modules:
        parent_id = parent["id"]

        # 查找该父模块下的所有子模块
        child_modules = [m for m in all_modules if m.get("parent_id") == parent_id]

        # 只处理有子模块的父模块
        if not child_modules:
            continue

        # 构建子模块权限列表（只有子模块才有权限）
        sub_modules = []
        for child in child_modules:
            child_id = child["id"]
            # 只有在权限映射表中的子模块才添加到结果中
            if child_id in permission_map:
                sub_module = SubModulePermissionSchema(
                    module=child["name"],
                    description=child.get("description"),
                    permissions=permission_map[child_id]
                )
                sub_modules.append(sub_module)

        # 只有当存在有权限的子模块时，才添加父模块
        if sub_modules:
            parent_module = ParentModulePermissionSchema(
                module=parent["name"],
                description=parent.get("description"),
                sub_modules=sub_modules
            )
            parent_module_permissions.append(parent_module)

    # 7. 构建响应
    role_module_perms_schema = RoleModulePermissionsSchema(
        role_id=role_id,
        module_permissions=parent_module_permissions
    )
    return role_module_perms_schema

@user_router.get("/sys_user/permissions", dependencies=[Depends(oauth2_scheme)], response_model=RoleModulePermissionsResponse)
@require_auth(module_name="User", permission_names=["READ"])
async def get_user_permissions(request: Request):
    """获取当前用户权限"""
    # 根据 token 获取当前用户
    current_user = await get_current_user_from_request(request)
    role_id = current_user.get("role_id")
    role_module_perms_schema = await _get_role_permissions(role_id)
    return RoleModulePermissionsResponse(
        code=HTTP_SUCCESS,
        msg="Success",
        data=role_module_perms_schema
    )

@user_router.get("/sys_user/permissions/template", dependencies=[Depends(oauth2_scheme)], response_model=ModulePermissionsTemplateResponse)
@require_auth(module_name="Role", permission_names=["READ"])
async def get_role_module_permissions_template(request: Request):
    """
    获取角色模块权限模板

    返回所有模块及其所有可用权限的完整模板，用于权限配置参考。
    每个子模块默认包含所有系统权限。
    """

    tasks = [
        main_db.run_query(Permission, return_clear=True),
        main_db.run_query(Module, return_clear=True)
    ]

    all_permissions, all_modules = await asyncio.gather(*tasks, return_exceptions=True)

    # 1. 查询所有权限
    all_permission_names = [perm["name"] for perm in all_permissions]

    # 2. 查询所有模块信息（包含父子关系）
    # 3. 找出所有父模块（parent_id 为 None 的模块）
    parent_modules = [m for m in all_modules if m.get("parent_id") is None]

    # 4. 构建层级结构
    parent_module_permissions = []
    for parent in parent_modules:
        parent_id = parent["id"]

        # 查找该父模块下的所有子模块
        child_modules = [m for m in all_modules if m.get("parent_id") == parent_id]

        # 只处理有子模块的父模块
        if not child_modules:
            continue

        # 构建子模块权限列表（每个子模块都分配所有权限）
        sub_modules = []
        for child in child_modules:
            sub_module = SubModulePermissionSchema(
                module=child["name"],
                description=child.get("description"),
                permissions=all_permission_names  # 所有权限
            )
            sub_modules.append(sub_module)

        # 添加父模块
        parent_module = ParentModulePermissionSchema(
            module=parent["name"],
            description=parent.get("description"),
            sub_modules=sub_modules
        )
        parent_module_permissions.append(parent_module)

    # 5. 构建响应
    template_schema = ModulePermissionsTemplateSchema(
        module_permissions=parent_module_permissions
    )

    return ModulePermissionsTemplateResponse(
        code=HTTP_SUCCESS,
        msg="Success",
        data=template_schema
    )

user_config = {
    'module_name': "User",
    'read_one': {'permission_name': "READ", "validate_schema": ListUserSchema},
    'read_filter': {'permission_name': 'READ', "validate_schema": ListUserSchema},
    'delete': {'permission_name': "DELETE"},
    "ignore_fields": {"response": ["password_hash"]},
}
user_router = DynamicApiManager(User, user_config, user_router).get_router()

# 对于创建和修改用户操作，单独定义 api 以处理密码哈希
@user_router.post("/sys_user", dependencies=[Depends(oauth2_scheme)])
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

@user_router.put("/sys_user/{item_id}", dependencies=[Depends(oauth2_scheme)])
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

@role_router.post("/sys_role/permissions", dependencies=[Depends(oauth2_scheme)], response_model=RolePermissionsResponse)
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

    return RolePermissionsResponse(
        code=HTTP_SUCCESS,
        msg="Success",
        data=role_permissions.roles
    )


@role_router.get("/sys_role/{role_id}/permissions", dependencies=[Depends(oauth2_scheme)], response_model=RoleModulePermissionsResponse)
@require_auth(module_name="Role", permission_names=["READ"])
async def get_role_permissions(request: Request, role_id: int):
    """
    获取指定角色的权限（层级结构）

    返回父模块-子模块的层级结构，只有子模块才有权限。
    """

    role_module_perms_schema = await _get_role_permissions(role_id)

    return RoleModulePermissionsResponse(
        code=HTTP_SUCCESS,
        msg="Success",
        data=role_module_perms_schema
    )