# 文档记录了在使用如 copilot AI 这样的工具时的经验和教训


## Case1: 在提供历史代码时，写新代码。

1. 使用设计文档，编写职责功能说明，明确要实现的功能，并且随时修改和增加。

如：
```
**db_async.py** 职责：
1. 实现异步数据库操作，适用 fastapi 异步场景
2. 考虑到使用底层的数据库 driver 场景，在初始化 engine 和 session 时使用 sqlalchemy 同步的方式。
注意先不要实现 session 的功能。先去实现和 engine 相关的功能。
通过装饰器将阻塞的方法，变为异步。
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
```

2. 为避免 AI 突然生成很多关联内容，明确指定本次要实现功能，哪些部分可以先忽略掉
如：
```
3. 由于我想实现通过 engine 和 session，两种实现方式。
所以目前先考虑 engine 的实现，我在其他项目中已经实现了通过 engine 实现异步 sql 执行的代码 - database/db_helper_reference.py，帮我集成到当前 db_async.py 中。
但并不所有的功能都要集成。需要按照步骤，我告诉你，集成哪个功能。你再去做。
需要集成的功能：
- 1. run_query
- 2. scroll_query
- 3. 将 bulk_insert_data, bulk_update_data 集成
- 4. 参考 bulk_update_data 的实现，构建 bulk_delete_data 的实现
4. 不要额外增加一些的功能，只增加我让你集成的功能。
5. 不要自己增加测试文件，在我让你增加时，再去增加。
```

3. 最终完成后，为代码在设计文档中重新总结和归纳，保留好设计文档。