import asyncio
from .base_strategy import ConcurrencyStrategy

class CoroutineStrategy(ConcurrencyStrategy):
    """协程并发策略，适用于异步 I/O 密集型任务。"""
    
    def __init__(self, logger=None, error_handling='log', timeout=None, 
                 return_exceptions=True, **asyncio_kwargs):
        """初始化协程策略。
        
        Args:
            logger (Logger, optional): 日志对象。
            error_handling (str): 错误处理策略。
            timeout (float, optional): 任务超时时间。
            return_exceptions (bool): asyncio.gather 是否返回异常而非抛出。
            **asyncio_kwargs: 传递给 asyncio 的其他参数。
        """
        super().__init__(logger, error_handling, timeout)
        self.return_exceptions = return_exceptions
        self.asyncio_kwargs = asyncio_kwargs
    
    async def async_execute(self, tasks_with_args, worker_count=None):
        """异步执行协程任务。
        
        Args:
            tasks_with_args (list): [(async_func, args), ...] 协程任务及参数列表。
            worker_count (int, optional): 最大并发数，通过信号量控制。
            
        Returns:
            list: [(success, result_or_error), ...] 执行结果列表。
        """
        self._log_info(f"Starting coroutine execution with {worker_count or 'unlimited'} concurrent tasks")
        
        # 设置并发控制信号量
        semaphore = asyncio.Semaphore(worker_count) if worker_count else None
        
        async def run_single_task(task, args, task_index):
            """运行单个协程任务的包装器。"""
            task_name = task.__name__ if hasattr(task, '__name__') else f'task_{task_index}'
            
            async def _execute():
                try:
                    if semaphore:
                        async with semaphore:
                            result = await asyncio.wait_for(task(*args), timeout=self.timeout)
                    else:
                        result = await asyncio.wait_for(task(*args), timeout=self.timeout)
                    
                    self._log_info(f"Task {task_name} completed successfully")
                    return (True, result)
                    
                except asyncio.TimeoutError as e:
                    error_result = self._handle_error(
                        e, 
                        f"Task {task_name} timed out after {self.timeout}s"
                    )
                    return error_result
                    
                except Exception as e:
                    error_result = self._handle_error(e, f"Task {task_name}")
                    return error_result
            
            return await _execute()
        
        # 创建所有协程任务
        coroutines = [
            run_single_task(task, args, i) 
            for i, (task, args) in enumerate(tasks_with_args)
        ]
        
        # 并发执行所有任务
        results = await asyncio.gather(*coroutines, return_exceptions=self.return_exceptions)
        
        # 如果启用了 return_exceptions，需要处理异常结果
        if self.return_exceptions:
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_result = self._handle_error(result, f"Task {i}")
                    processed_results.append(error_result)
                else:
                    processed_results.append(result)
            results = processed_results
        
        successful = len([r for r in results if r[0]])
        failed = len([r for r in results if not r[0]])
        self._log_info(f"Coroutine execution completed. {successful} successful, {failed} failed")
        
        return results
    
    def execute(self, tasks_with_args, worker_count=None, **kwargs):
        """
        execute，自动适配同步或异步环境。
        - 同步环境直接返回结果
        - 异步环境返回 awaitable
        
        Args:
            tasks_with_args (list): [(async_func, args), ...] 协程任务及参数列表。
            worker_count (int, optional): 最大并发数。
            **kwargs: 其他扩展参数。
            
        Returns:
            list: [(success, result_or_error), ...] 执行结果列表。
        """
        try:
            loop = asyncio.get_running_loop()
            # 如果能获取 loop，说明在异步环境，返回 awaitable
            return self.async_execute(tasks_with_args, worker_count)
        except RuntimeError:
            print("No running event loop found, executing synchronously.")
            # 没有事件循环，直接运行异步任务并返回结果
            return asyncio.run(self.async_execute(tasks_with_args, worker_count))