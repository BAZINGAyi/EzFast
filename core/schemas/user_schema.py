# core/schemas/user_schema.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# common schema

class CommonResponseSchema(BaseModel):
    code: int = Field(..., description="状态码")
    msg: str = Field(..., description="消息")

# user schema

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
    is_active: Optional[bool] = None

# role schema

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

class RolePermissionsResponse(BaseModel):
    code: int = Field(..., description="状态码")
    msg: str = Field(..., description="消息")
    data: Optional[List[RolePermissionSchema]] = Field(None, description="角色权限配置")


# 新的嵌套模块权限结构
class SubModulePermissionSchema(BaseModel):
    """子模块权限配置 Schema"""
    module: str = Field(..., description="子模块名称")
    description: Optional[str] = Field(None, description="子模块描述")
    permissions: List[str] = Field(..., description="该子模块的权限列表")

    class Config:
        json_schema_extra = {
            "example": {
                "module": "user",
                "description": "用户管理",
                "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]
            }
        }


class ParentModulePermissionSchema(BaseModel):
    """父模块权限配置 Schema（包含子模块）"""
    module: str = Field(..., description="父模块名称")
    description: Optional[str] = Field(None, description="父模块描述")
    sub_modules: List[SubModulePermissionSchema] = Field(..., description="子模块列表")

    class Config:
        json_schema_extra = {
            "example": {
                "module": "System Management",
                "description": "系统管理",
                "sub_modules": [
                    {
                        "module": "user",
                        "description": "用户管理",
                        "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]
                    }
                ]
            }
        }


class RoleModulePermissionsSchema(BaseModel):
    """角色的模块权限配置 Schema（层级结构）"""
    role_id: int = Field(..., description="角色 ID")
    module_permissions: List[ParentModulePermissionSchema] = Field(
        ..., description="父模块及其子模块权限列表"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "role_id": 1,
                "module_permissions": [
                    {
                        "module": "System Management",
                        "description": "系统管理",
                        "sub_modules": [
                            {
                                "module": "user",
                                "description": "用户管理",
                                "permissions": ["READ", "WRITE", "UPDATE", "DELETE"]
                            }
                        ]
                    }
                ]
            }
        }


class RoleModulePermissionsResponse(CommonResponseSchema):
    """角色模块权限响应 Schema（层级结构）"""
    data: Optional[RoleModulePermissionsSchema] = Field(None, description="角色模块权限配置（层级结构）")