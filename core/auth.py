import functools
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select, true

from core import main_db, get_module_id, get_permission_bit
from core.utils.async_tools import async_wrap
from core.config import settings

from core.models.user_models import User, RoleModulePermission, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/sys/auth/login")

def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    Create JWT access token.

    Args:
        data: Data to encode in the token
        expires_delta: Token expiration time override

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """
    Verify the JWT token and return the payload if valid.

    Args:
        token: JWT token string

    Returns:
        dict: Decoded token payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token is invalid or expired")

def get_user_info_from_jwt(request: Request) -> dict:
    """
    Extract and verify JWT token from request, return user ID.

    Args:
        request: FastAPI Request object

    Returns:
        dict: User info from token

    Raises:
        HTTPException: If token is missing, invalid, or expired
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    role_id: int = payload.get("role_id")
    if role_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return payload

async def check_permissions(role_id, module_id, permission_bitmask):
    """
    Check if the user has the required permissions for the module.
    """
    try:
        async with main_db.get_session() as session:
            stmt = select(RoleModulePermission.permissions).select_from(Role).join(
                RoleModulePermission,
                Role.id == RoleModulePermission.role_id
            ).where(
                Role.id == role_id,
                RoleModulePermission.module_id == module_id,
                Role.is_active.is_(true())
            )
            permissions = await session.execute(stmt)
            permissions_bit = permissions.scalar_one_or_none()

            permission = RoleModulePermission(permissions=permissions_bit) if permissions_bit else None
            if not permission or not permission.has_permission(permission_bitmask):
                return False
        return True
    except Exception:
        return False

def require_auth(module_name: str = None, permission_names: list = None):
    """
    Unified authentication and permission check decorator.

    Args:
        module_name: Module name for permission check, None for auth only
        permission_names: List of permission names for permission check, None for auth only

    Usage:
        @require_auth()  # Authentication only
        @require_auth(module_name="User", permission_names=["READ", "WRITE"])  # Auth + permission check

    Example:
        @require_auth()
        async def simple_api():
            return {"data": "protected"}

        @require_auth(module_name="User", permission_names=["READ", "WRITE"])
        async def get_users(request: Request):
            user_id = request.state.current_user_id
            return {"users": []}
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Find Request object in arguments
            request: Request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")
            if request is None:
                raise RuntimeError("Request object is required in route parameters")

            # 1. Verify JWT and get user ID
            user_info = get_user_info_from_jwt(request)
            role_id = user_info.get("role_id")
            request.state.current_user_id = user_info.get("user_id")

            # 2. Check permissions if required
            if module_name and permission_names:
                # Resolve module_name to module_id at runtime
                module_id = get_module_id(module_name)
                if module_id == 0:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Module '{module_name}' not found"
                    )

                # Resolve permission_names to permission_bitmask at runtime
                permission_bitmask = 0
                for perm_name in permission_names:
                    perm_bit = get_permission_bit(perm_name)
                    if perm_bit == 0:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Permission '{perm_name}' not found"
                        )
                    permission_bitmask |= perm_bit

                # Perform permission check
                has_perm = await check_permissions(role_id, module_id, permission_bitmask)
                if not has_perm:
                    raise HTTPException(
                        status_code=403,
                        detail="Forbidden: insufficient permissions"
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

async def get_current_user_from_request(request: Request) -> dict:
    """
    Get current user object from request state (requires database query).

    Args:
        request: FastAPI Request object with current_user_id in state

    Returns:
        User: Current user object

    Raises:
        HTTPException: If authentication required or user not found
    """
    if not hasattr(request.state, 'current_user_id'):
        raise HTTPException(status_code=401, detail="Authentication required")

    async with main_db.get_session() as session:
        user = await session.execute(
            select(User).where(User.id == request.state.current_user_id))
        user = user.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user.to_dict()