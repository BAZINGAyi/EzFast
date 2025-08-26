"""并发策略模块，提供线程池、进程池、协程等并发执行策略。

Usage:
    from core.utils.concurrency import ThreadPoolStrategy, ProcessPoolStrategy, CoroutineStrategy, ConcurrencyContext
    
    # 使用线程池策略
    thread_strategy = ThreadPoolStrategy(logger=my_logger, timeout=30)
    context = ConcurrencyContext(thread_strategy)
    results = context.execute_tasks(tasks_with_args, worker_count=4)
    
    # 切换到协程策略
    coroutine_strategy = CoroutineStrategy(logger=my_logger, error_handling='raise')
    context.set_strategy(coroutine_strategy)
    results = context.execute_tasks(async_tasks_with_args, worker_count=10)
"""

# from .base_strategy import ConcurrencyStrategy
# from .thread_strategy import ThreadPoolStrategy
# from .process_strategy import ProcessPoolStrategy
# from .coroutine_strategy import CoroutineStrategy
# from .context import ConcurrencyContext

# __all__ = [
#     'ConcurrencyStrategy',
#     'ThreadPoolStrategy', 
#     'ProcessPoolStrategy',
#     'CoroutineStrategy',
#     'ConcurrencyContext'
# ]
