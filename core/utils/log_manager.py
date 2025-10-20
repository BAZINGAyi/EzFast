from loguru import logger
import os
from functools import partial

# 模块级函数，可以被 pickle
def _logger_name_filter(record, target_name):
    """过滤器函数：只接收指定 logger_name 的日志"""
    return record["extra"].get("logger_name") == target_name

class LogManager:
    def __init__(self, config: dict, log_dir: str = "logs", enqueue: bool = False):
        """初始化日志管理器。

        根据配置初始化多个日志记录器，并确保日志目录存在。

        Args:
            config (dict): 日志配置字典，包含各日志记录器的参数。
            log_dir (str, optional): 日志统一存放目录，默认 "logs"。
            enqueue (bool, optional): 是否启用异步队列，适用于多进程场景，默认 False。

        Raises:
            OSError: 当日志目录创建失败时抛出。

        Example:
            >>> log_config = {
            ...     "loggers": [
            ...         {"name": "app", "file": "app.log", "level": "INFO", "rotate": "10 MB"},
            ...         {"name": "db", "file": "db.log", "level": "DEBUG", "rotate": "5 MB"}
            ...     ]
            ... }
            >>> log_manager = LogManager(log_config, log_dir="my_logs")
            >>> app_logger = log_manager.get_logger("app")
            >>> app_logger.info("App started.")
        """
        self.loggers = {}
        self.log_dir = log_dir
        self.enqueue = enqueue
        os.makedirs(self.log_dir, exist_ok=True)  # 确保目录存在
        self.load_config(config)

    def load_config(self, config: dict):
        # if Windows and using queue in multiprocessing
        if os.name == 'nt' and self.enqueue:
            logger.remove() # "sys.stderr" sink is not picklable

        loggers_config = config.get("loggers", [])
        for lg_conf in loggers_config:
            file_name = lg_conf.get("file")
            if file_name:
                # 拼接到指定目录
                file_path = os.path.join(self.log_dir, os.path.basename(file_name))
            else:
                file_path = None

            self.add_logger(
                name=lg_conf.get("name", "default"),
                file=file_path,
                level=lg_conf.get("level", "INFO"),
                rotate=lg_conf.get("rotate", None)
            )

    def add_logger(self, name: str, file: str, level: str = "INFO", rotate=None):
        # 使用 functools.partial 创建可 pickle 的过滤器
        logger_filter = partial(_logger_name_filter, target_name=name)

        if file:
            os.makedirs(os.path.dirname(file), exist_ok=True)
            handler_id = logger.add(
                file,
                level=level,
                rotation=rotate,
                enqueue=self.enqueue,
                backtrace=True,
                diagnose=True,
                filter=logger_filter  # 添加过滤器
            )
        else:
            handler_id = logger.add(
                lambda msg: print(msg, end=''),
                level=level,
                filter=logger_filter  # 添加过滤器
            )
        self.loggers[name] = handler_id

    def get_logger(self, name: str):
        if name in self.loggers:
            return logger.bind(logger_name=name)
        else:
            raise ValueError(f"Logger '{name}' not found.")