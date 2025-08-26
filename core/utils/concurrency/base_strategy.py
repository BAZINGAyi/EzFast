import traceback

class ConcurrencyStrategy:
    """并发策略基类，定义统一接口和通用属性。"""
    
    def __init__(self, logger=None, error_handling='log', timeout=None):
        """初始化并发策略基类。
        
        Args:
            logger (Logger, optional): 日志对象，用于记录执行过程。
            error_handling (str): 错误处理策略，'log'记录错误继续执行，'raise'遇错即停。
            timeout (float, optional): 任务超时时间（秒）。
        """
        self.logger = logger
        self.error_handling = error_handling
        self.timeout = timeout
    
    def execute(self, tasks_with_args, worker_count, **kwargs):
        """执行并发任务的抽象方法。
        
        Args:
            tasks_with_args (list): [(func, args), ...] 任务及参数列表。
            worker_count (int): 工作单元数（线程/进程/协程数）。
            **kwargs: 其他扩展参数。
            
        Returns:
            list: [(success, result_or_error), ...] 执行结果列表。
        """
        raise NotImplementedError("Strategy must implement execute method.")
    
    def _log_info(self, message):
        """统一的信息日志记录。"""
        if self.logger:
            self.logger.info(message)
        else:
            print(f"[INFO] {message}")
    
    def _log_error(self, message):
        """统一的错误日志记录。"""
        if self.logger:
            self.logger.error(message)
        else:
            print(f"[ERROR] {message}")
    
    def _handle_error(self, error, context="Task execution"):
        """统一的错误处理。"""
        error_str = str(error).strip() or f"<{error.__class__.__name__}>"
        error_msg = f"{context} failed: {error_str}"
        self._log_error(error_msg)
        # 记录完整堆栈
        self._log_error("".join(traceback.format_exception(type(error), error, error.__traceback__)))
        
        if self.error_handling == 'raise':
            raise error
        
        return (False, error_msg)