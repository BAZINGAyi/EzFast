from concurrent.futures import ThreadPoolExecutor, as_completed
from .base_strategy import ConcurrencyStrategy

class ThreadPoolStrategy(ConcurrencyStrategy):
    """线程池并发策略，适用于 I/O 密集型任务。"""
    
    def __init__(self, logger=None, error_handling='log', timeout=None, 
                 thread_name_prefix='EZ-ThreadPool', **thread_kwargs):
        """初始化线程池策略。
        
        Args:
            logger (Logger, optional): 日志对象。
            error_handling (str): 错误处理策略。
            timeout (float, optional): 任务超时时间。
            thread_name_prefix (str): 线程名称前缀。
            **thread_kwargs: 传递给 ThreadPoolExecutor 的其他参数。
        """
        super().__init__(logger, error_handling, timeout)
        self.thread_name_prefix = thread_name_prefix
        self.thread_kwargs = thread_kwargs
    
    def execute(self, tasks_with_args, worker_count, **kwargs):
        """使用线程池并发执行任务。
        
        Args:
            tasks_with_args (list): [(func, args), ...] 任务及参数列表。
            worker_count (int): 线程数。
            **kwargs: 其他扩展参数。
            
        Returns:
            list: [(success, result_or_error), ...] 执行结果列表。
        """
        self._log_info(f"Starting thread pool execution with {worker_count} workers")
        
        executor_kwargs = {
            'max_workers': worker_count if worker_count > 0 else 5,
            'thread_name_prefix': self.thread_name_prefix,
            **self.thread_kwargs
        }
        
        with ThreadPoolExecutor(**executor_kwargs) as executor:
            futures = []
            
            # 提交任务
            for i, (task, args) in enumerate(tasks_with_args):
                try:
                    # 使用闭包避免 lambda 延迟绑定问题
                    def create_task_wrapper(func, task_args):
                        def wrapper():
                            return func(*task_args)
                        return wrapper
                    
                    future = executor.submit(create_task_wrapper(task, args))
                    
                    # 设置 task name
                    task_name = getattr(task, '__name__', None)
                    if not task_name or task_name in ("<lambda>", "lambda"):
                        task_name = f"task_{i}"
                        
                    futures.append((future, i, task_name))
                except Exception as e:
                    error_result = self._handle_error(e, f"Task {i} submission")
                    futures.append((None, i, error_result))
            
            # 收集结果
            results = [None] * len(tasks_with_args)
            
            for future, task_index, task_name in futures:
                if future is None:  # 提交失败的任务
                    results[task_index] = task_name  # 这里 task_name 实际是错误结果
                    continue
                
                try:
                    result = future.result(timeout=self.timeout)
                    results[task_index] = (True, result)
                    self._log_info(f"Task {task_name} completed successfully")
                except Exception as e:
                    error_result = self._handle_error(e, f"Task {task_name}")
                    results[task_index] = error_result
        
        self._log_info(f"Thread pool execution completed. {len([r for r in results if r[0]])} successful, {len([r for r in results if not r[0]])} failed")
        return results