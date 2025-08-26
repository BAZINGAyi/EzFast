from concurrent.futures import ProcessPoolExecutor, as_completed
from .base_strategy import ConcurrencyStrategy

class ProcessPoolStrategy(ConcurrencyStrategy):
    """进程池并发策略，适用于 CPU 密集型任务。"""
    
    def __init__(self, logger=None, error_handling='log', timeout=None, 
                 max_tasks_per_child=None, **process_kwargs):
        """初始化进程池策略。
        
        Args:
            logger (Logger, optional): 日志对象。
            error_handling (str): 错误处理策略。
            timeout (float, optional): 任务超时时间。
            max_tasks_per_child (int, optional): 每个子进程最大任务数。
            **process_kwargs: 传递给 ProcessPoolExecutor 的其他参数。
        """
        super().__init__(logger, error_handling, timeout)
        self.max_tasks_per_child = max_tasks_per_child
        self.process_kwargs = process_kwargs
    
    def execute(self, tasks_with_args, worker_count, **kwargs):
        """使用进程池并发执行任务。
        
        Args:
            tasks_with_args (list): [(func, args), ...] 任务及参数列表。
            worker_count (int): 进程数。
            **kwargs: 其他扩展参数。
            
        Returns:
            list: [(success, result_or_error), ...] 执行结果列表。
        """
        self._log_info(f"Starting process pool execution with {worker_count} workers")
        
        executor_kwargs = {
            'max_workers': worker_count if worker_count > 0 else 1,
            **self.process_kwargs
        }
        
        with ProcessPoolExecutor(**executor_kwargs) as executor:
            futures = []
            
            # 提交任务
            for i, (task, args) in enumerate(tasks_with_args):
                try:
                    future = executor.submit(task, *args)
                    futures.append((future, i, task.__name__ if hasattr(task, '__name__') else f'task_{i}'))
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
        
        self._log_info(f"Process pool execution completed. {len([r for r in results if r[0]])} successful, {len([r for r in results if not r[0]])} failed")
        return results