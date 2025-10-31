# core/schemas/user_schema.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

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