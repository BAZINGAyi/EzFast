# SQLAlchemy 机制分析，便于回顾和理解


## sessionmaker vs scoped_session 在多线程情境对比

### 正常创建 session 对比

- sessionmaker：用于创建新的 Session 实例，每次调用都会返回一个新的 Session。
- scoped_session：提供了一个线程安全的 Session 共享机制，可以在多个请求之间共享同一个 Session 实例。

```
请求/线程 A
+-------------------------------+
|                               |
|  普通 sessionmaker:           |
|                               |
|  SessionFactory() -> s1       |
|  SessionFactory() -> s2       |
|                               |
|  s1 != s2                     |
|                               |
+-------------------------------+

+-------------------------------+
|                               |
|  scoped_session:              |
|                               |
|  Session() -> s1              |
|  Session() -> s2              |
|                               |
|  s1 == s2                     |
|                               |
+-------------------------------+

请求结束/线程结束：
- scoped_session 调用 Session.remove() 自动清理

- 普通 session 需手动 s1.close(), s2.close()
```

### 加入 with 和 contextmanager 后的对比：

```
请求/线程 A
---------------------------------------------------------------
1️⃣ sessionmaker + contextmanager + with + yield
---------------------------------------------------------------
@contextmanager
def get_session():
    session = SessionFactory()  # 新建 session
    try:
        yield session           # 块内使用
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()         # 自动关闭

with get_session() as s1:
    操作数据库
with get_session() as s2:
    操作数据库

s1 != s2  # 每次新建 session

---------------------------------------------------------------
2️⃣ scoped_session + contextmanager + with + yield
---------------------------------------------------------------
Session = scoped_session(sessionmaker())

@contextmanager
def get_scoped_session():
    s = Session()              # 获取线程绑定 session
    try:
        yield s               # 块内使用
        s.commit()
    except:
        s.rollback()
        raise
    finally:
        pass                  # 仍绑定线程，需要 Session.remove()

with get_scoped_session() as s1:
    操作数据库
with get_scoped_session() as s2:
    操作数据库

s1 == s2  # 同一线程内复用 session
# 最终需调用 Session.remove() 才真正关闭/解绑
---------------------------------------------------------------
```

在 flask 中，使用 `scoped_session` 可以方便地管理数据库会话，确保每个请求都使用独立的会话，然后在请求结束时调用 `Session.remove()` 进行清理。

在 FastAPI 中，通常使用依赖注入来管理数据库会话，确保每个请求都使用独立的会话，而不需要使用 `scoped_session`。这样可以避免多线程环境下的会话共享问题。


## Engine 和 Session 区别


| 特性／职责   | Engine                           | Session                                                                   |
| ------- | -------------------------------- | ------------------------------------------------------------------------- |
| 所属层级    | SQLAlchemy Core                  | ORM 层                                                                     |
| 主要功能    | 管理连接池、执行 SQL                     | 管理 ORM 对象、缓冲、事务与对象状态                                                      |
| 创建方式    | `create_engine(...)`，全局使用        | `sessionmaker(bind=engine)`，每线程/任务独立使用                                    |
| 并发安全    | 线程安全                             | **不是**线程安全（需为每线程/任务单独实例）([SQLAlchemy Documentation][1])                   |
| 使用方式    | `.connect()` 或 `.begin()` 执行 SQL | `.add()` / `.commit()` / `.flush()` 操作模型，也发出查询                            |
| 事务管理    | `.begin()` 提供事务块                 | `Session.begin()` 或手动 commit/rollback 管理事务([SQLAlchemy Documentation][2]) |
| 与数据库的关系 | 管理连接池 / DBAPI                    | 获取连接，发出 SQL（ORM）                                                          |
| 延迟行为    | 延迟建立连接,第一次 connect 才建立连接 | 延迟与 `Engine` 建立连接，等执行时才建立                                                 |

[1]: https://docs.sqlalchemy.org/en/latest/orm/session_basics.html "Session Basics — SQLAlchemy 2.0 Documentation"
[2]: https://docs.sqlalchemy.org/en/latest/orm/session_transaction.html "Transactions and Connection Management — SQLAlchemy 2.0 ..."

## 使用 Engine 构建 statement sql 时，传入表对象，和使用 metadata 构建区别

1. 显示定义表结构对象:
```
from sqlalchemy import Table, Column, Integer, String, MetaData

metadata = MetaData()
user_table = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String),
)
```

2. 使用 metadata 反射表结构
```
from sqlalchemy import MetaData, Table

metadata = MetaData()
user_table = Table("users", metadata, autoload_with=engine) # autoload_with used in new 2.0 + version
```
| 维度        | 显式定义表对象                 | 反射表对象（autoload）      |
| --------- | ----------------------- | -------------------- |
| **表结构来源** | Python 代码（由开发者定义）       | 数据库实际 schema         |
| **依赖性**   | 不依赖现有数据库，可先定义再创建表       | 必须数据库里已有该表           |
| **迁移支持**  | 好，代码即 schema，适合 Alembic | 差，schema 来自 DB，不利于迁移 |
| **适用场景**  | 新项目，ORM 模型驱动开发          | 已有数据库，或者只读查询         |
| **灵活性**   | 代码完全可控，易修改              | 跟随数据库结构，改动必须在 DB 执行  |
| **性能**    | 无需额外查询数据库               | 第一次需要查询数据库元信息（稍慢）    |
