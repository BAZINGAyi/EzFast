from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from core.auth import (
    oauth2_scheme, 
    create_access_token, 
    require_auth,
    get_current_user_from_request
)

from core import (
    main_db,
)
    
from core.models.user_models import User
from core.utils.async_tools import async_wrap
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
    @async_wrap
    def check_pass():
        with main_db.get_session() as session:
            user = session.query(User).filter(User.username == form_data.username).first()
            
            if not user or not user.check_password(form_data.password):
                raise HTTPException(
                    status_code=401,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user.id
        
    user_id = await check_pass()
    access_token = create_access_token(data={"user_id": user_id})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

# =============== 示例业务路由 ===============

# 场景1: 只需要认证，不检查权限,oauth2_scheme的作用是为了 swagger 发送时，带认证头。
@router.get("/simple-data", dependencies=[Depends(oauth2_scheme)])
@require_auth()
async def get_simple_data(request: Request):
    """获取简单数据 - 只验证身份"""
    return {"data": "some protected data", "message": "Authentication successful"}

# 场景3: 需要用户ID的场景
@router.get("/my-data", dependencies=[Depends(oauth2_scheme)])
@require_auth()
async def get_my_data(request: Request):
    """获取用户相关数据 - 使用用户ID"""
    user_id = request.state.current_user_id
    return {"user_id": user_id, "data": f"Data for user {user_id}"}

# 场景4: 需要完整用户信息的场景
@router.get("/profile", dependencies=[Depends(oauth2_scheme)])
@require_auth()
async def get_profile(request: Request):
    """获取用户资料 - 查询完整用户信息"""
    user = await get_current_user_from_request(request)
    return {
        "username": user["username"],
        "email": user["email"],
        "created_at": user["created_at"].isoformat() if user["created_at"] else None
    }

# 场景7: 组合权限示例 - 使用字符串名称
@router.post("/users", dependencies=[Depends(oauth2_scheme)])
@require_auth(module_name="User", permission_names=["WRITE", "READ"])
async def create_user(request: Request):
    """创建用户 - 需要创建和写入权限 (使用字符串名称)"""
    user_id = request.state.current_user_id
    return {
        "message": f"User {user_id} created a new user",
        "created_user": "new_user"
    }
