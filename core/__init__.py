

import asyncio
from contextlib import asynccontextmanager
import traceback

from fastapi import HTTPException, Request

from fastapi.responses import JSONResponse
from pydantic_core import ValidationError
from core.utils.database.db_manager import DatabaseManager
from core.config import settings

from core.models.user_models import User, Permission, Module, RoleModulePermission
from core.utils.log_manager import LogManager

"""
load db service for global access
"""
main_db = DatabaseManager(settings.DB_CONFIG).get_database("default")
__PermissionsConstant = {}
__ModulesConstant = {}
def get_module_id(module_name: str) -> int:
    """Get module ID by name from constants."""
    return __ModulesConstant.get(module_name.lower(), 0)

def get_module_name(module_id: int) -> str:
    """Get module name by ID from constants."""
    for name, mid in __ModulesConstant.items():
        if mid == module_id:
            return name
    return ""

def get_permission_bit(permission_name: str) -> int:
    """Get permission bit by name from constants."""
    return __PermissionsConstant.get(permission_name.lower(), 0)

def get_permissions_names_from_bitmask(bitmask: int) -> list[str]:
    """Get permission names from a bitmask."""
    names = []
    for name, bit in __PermissionsConstant.items():
        if bitmask & bit:
            names.append(name)
    return names

async def load_permissions():
    """
    Load permissions and modules from the database.
    """
    tasks = [
        main_db.run_query(Permission, return_clear=True),
        main_db.run_query(Module, return_clear=True)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for permission in results[0]:
        __PermissionsConstant[permission["name"].lower()] = permission["permission_bit"]

    for module in results[1]:
        __ModulesConstant[module["name"].lower()] = module["id"]

    if settings.DEBUG:
        print("Loaded Permissions:", __PermissionsConstant)
        print("Loaded Modules:", __ModulesConstant)

# async def __init_admin_user():
#     """
#     Initialize the admin user with the necessary permissions.
#     """
#     admin_user = User(
#         username="admin",
#         email="admin@example.com",
#         role_id=1,  # Assuming role_id 1 is for admin
#     )
#     admin_user.set_password("admin")
#     user_dict = admin_user.to_dict()
#     user_dict["password_hash"] = admin_user.password
    
#     insert_data = [
#         {
#             "table": User.__table__,
#             "data": [user_dict],
#             "operation": "insert"
#         }
#     ]

#     print("Initialized admin user:", user_dict)

#     status = await main_db.bulk_dml_table(insert_data)
#     print("Admin user initialization status:")

"""
global lifespan management
"""
logger_mger = LogManager(
    config=settings.LOG_CONFIG, log_dir=settings.LOG_BASE_PATH, enqueue=True)
sys_logger = logger_mger.get_logger("sys")

@asynccontextmanager
async def lifespan(app):
    # 应用启动逻辑
    await load_permissions()
    print("🚀 应用启动完成！")
    
    yield
    
    # 应用关闭逻辑
    print("🛑 应用关闭完成！")
    

async def pydantic_validation_exception_handler(request, exc: ValidationError):
    """
    Pydantic验证异常处理器
    处理 Pydantic 的 ValidationError，提供统一的错误响应格式
    """
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    sys_logger.error(f"Validation exception traceback: {tb_str}")
    
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "msg": "数据验证时发生错误，请联系管理员，查看日志获取详细信息"
        },
    )
    
    
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    HTTP异常处理器
    处理 FastAPI 的 HTTPException，提供统一的错误响应格式
    """
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    sys_logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail} - URL: {request.url}")
    sys_logger.error(f"HTTP Exception traceback: {tb_str}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "msg": exc.detail,
        },
    )

async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器
    处理未捕获的异常，记录详细错误信息并返回统一的错误响应
    """
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    sys_logger.error(f"Unhandled exception: {exc}\n{tb_str}")

    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "msg": "服务器内部错误，请联系管理员",
        },
    )