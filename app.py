
from fastapi import FastAPI, HTTPException
from pydantic_core import ValidationError
import uvicorn
from core import lifespan, global_exception_handler, http_exception_handler, pydantic_validation_exception_handler
from core.sys_api import router as sys_api_router
from core.sys_api import user_router, permission_router, module_router, role_router


    
# 创建 FastAPI 应用实例
app = FastAPI(
    title="EzFast API",
    description="一个基于 FastAPI 的快速开发框架",
    version="1.0.0",
    lifespan=lifespan
)

# 注册系统 API 路由，前缀为 /api
app.include_router(sys_api_router, prefix="/api/sys", tags=["系统API"])
app.include_router(user_router, prefix="/api", tags=["User API"])
app.include_router(permission_router, prefix="/api", tags=["Permission API"])
app.include_router(module_router, prefix="/api", tags=["Module API"])
app.include_router(role_router, prefix="/api", tags=["Role API"])

# 根路由
@app.get("/")
async def root():
    """根路由，返回欢迎信息"""
    return {"message": "欢迎使用 EzFast API!"}

# 健康检查路由
@app.get("/health")
async def health_check():
    """健康检查路由"""
    return {"status": "healthy"}

# 注册异常处理器
app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

if __name__ == "__main__":
    # 运行应用
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
    