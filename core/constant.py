HTTP_SUCCESS = 200
HTTP_FAILED = 500

# 初始化模块和权限
Init_Modules = [
    {
        "id": 10000,
        "name": "System Management",
        "url": "/system",
        "icon": "system",
        "parent_id": None,
        "path": "/system",
        "sub_modules": [
            {
                "id": 10001,
                "name": "User",
                "url": "/system/user",
                "icon": "user",
                "parent_id": 10000,
                "path": "/system/user"
            },
            {
                "id": 10002,
                "name": "Role",
                "url": "/system/role",
                "icon": "role",
                "parent_id": 10000,
                "path": "/system/role"
            },
            {
                "id": 10003,
                "name": "Permission",
                "url": "/system/permission",
                "icon": "permission",
                "parent_id": 10000,
                "path": "/system/permission"
            },
            {
                "id": 10004,
                "name": "Module",
                "url": "/system/module",
                "icon": "module",
                "parent_id": 10000,
                "path": "/system/module"
            }
        ]
    }
]

Init_Permissions = [
    {
        "id": 1,
        "name": "READ",
        "permission_bit": 1,
        "description": "读取权限",
    },
    {
        "id": 2,
        "name": "WRITE",
        "permission_bit": 2,
        "description": "写入权限",
    },
    {
        "id": 3,
        "name": "DELETE",
        "permission_bit": 4,
        "description": "删除权限",
    },
    {
        "id": 4,
        "name": "UPDATE",
        "permission_bit": 8,
        "description": "更新权限",
    }
]

# 初始化用户
Init_Roles = [
    {
        "name": "admin",
        "description": "管理员",
        "is_active": True
    }
]

Init_Users = [
    {
        "username": "admin",
        "email": "admin@example.com",
        "password": "admin",
        "role_id": 1
    }
]

# 初始化模块具有的权限
Init_Module_Permissions = [
    # User
    {
        "module_id": 10001,
        "permission_id": 1
    },
    {
        "module_id": 10001,
        "permission_id": 2
    },
    {
        "module_id": 10001,
        "permission_id": 3
    },
    {
        "module_id": 10001,
        "permission_id": 4
    },
    # Role
    {
        "module_id": 10002,
        "permission_id": 1
    },
    {
        "module_id": 10002,
        "permission_id": 2
    },
    {
        "module_id": 10002,
        "permission_id": 3
    },
    {
        "module_id": 10002,
        "permission_id": 4
    },
    # Permission
    {
        "module_id": 10003,
        "permission_id": 1
    },
    {
        "module_id": 10003,
        "permission_id": 2
    },
    {
        "module_id": 10003,
        "permission_id": 3
    },
    {
        "module_id": 10003,
        "permission_id": 4
    },
    # Module
    {
        "module_id": 10004,
        "permission_id": 1
    },
    {
        "module_id": 10004,
        "permission_id": 2
    },
    {
        "module_id": 10004,
        "permission_id": 3
    },
    {
        "module_id": 10004,
        "permission_id": 4
    }
]

# 初始化角色具有的模块和权限
Init_Role_Module_Permissions = [
    {
        "role_id": 1,
        "module_id": 10001,
        "permissions": 15
    },
    {
        "role_id": 1,
        "module_id": 10002,
        "permissions": 15
    },
    {
        "role_id": 1,
        "module_id": 10003,
        "permissions": 15
    },
    {
        "role_id": 1,
        "module_id": 10004,
        "permissions": 15
    }
]