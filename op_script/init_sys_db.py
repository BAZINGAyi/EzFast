# append sys.path
import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.database.db_manager import DatabaseManager
from core.config import settings
from core.constant import Init_Modules, Init_Permissions, Init_Module_Permissions, Init_Role_Module_Permissions, Init_Roles, Init_Users
from core.models.base_models import Base
from core.models.user_models import Module, Permission, Role, User, ModulePermission, RoleModulePermission

async def init_db_schema(main_db):
    """
    Initialize the database schema.
    """
    async with main_db.get_conn() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def init_data(main_db):
    """
    Initialize the database data.
    """
    for module in Init_Modules:
        sub_modules = module.pop("sub_modules")
        result = await main_db.add(Module, module)
        print(result)

        sub_result = await main_db.bulk_insert_data(Module, sub_modules)
        print(sub_result)

    permission_result = await main_db.bulk_insert_data(Permission, Init_Permissions)
    print(permission_result)

    role_result = await main_db.bulk_insert_data(Role, Init_Roles)
    print(role_result)

    async with main_db.get_session() as session:
        user = User(**Init_Users[0])
        session.add(user)
        await session.flush()
        await session.refresh(user)
        print(user.to_dict())

    module_permission_result = await main_db.bulk_insert_data(
        ModulePermission, Init_Module_Permissions)
    print(module_permission_result)

    role_module_permission_result = await main_db.bulk_insert_data(
        RoleModulePermission, Init_Role_Module_Permissions)
    print(role_module_permission_result)

async def main():
    manager = DatabaseManager(settings.DB_CONFIG)
    main_db = manager.get_database("default")
    await init_db_schema(main_db)
    await init_data(main_db)
    await manager.close_all()

if __name__ == "__main__":
    asyncio.run(main())