import asyncio
from functools import wraps


def async_wrap(func):
    """
    装饰器：将阻塞的方法封装为异步方法
    
    Args:
        func: 要包装的同步函数
        
    Returns:
        异步包装后的函数
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper