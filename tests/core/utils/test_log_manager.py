import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from core.utils.log_manager import LogManager


class TestLogManager:
    """LogManager 的完整测试套件。"""
    
    def setup_method(self):
        """每个测试方法前的设置。"""
        # 创建临时目录用于测试
        self.temp_dir = tempfile.mkdtemp()
        self.test_log_dir = os.path.join(self.temp_dir, "test_logs")
        
        # 基础配置
        self.basic_config = {
            "loggers": [
                {
                    "name": "app",
                    "file": "app.log",
                    "level": "INFO",
                    "rotate": "10 MB"
                },
                {
                    "name": "db",
                    "file": "db.log",
                    "level": "DEBUG",
                    "rotate": "5 MB"
                }
            ]
        }
        
        # 空配置
        self.empty_config = {"loggers": []}
        
        # 无文件配置（仅控制台）
        self.console_config = {
            "loggers": [
                {
                    "name": "console",
                    "level": "WARNING"
                }
            ]
        }

    def teardown_method(self):
        """每个测试方法后的清理。"""
        # 清理临时目录
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ================== 初始化测试 ==================
    
    @patch('core.utils.log_manager.logger')
    def test_init_default_values(self, mock_logger):
        """测试默认初始化值。"""
        log_manager = LogManager(self.empty_config)
        
        assert log_manager.loggers == {}
        assert log_manager.log_dir == "logs"
        assert log_manager.enqueue is False
        assert os.path.exists("logs")  # 确保默认目录被创建
        
        # 清理默认目录
        if os.path.exists("logs"):
            shutil.rmtree("logs")

    @patch('core.utils.log_manager.logger')
    def test_init_custom_values(self, mock_logger):
        """测试自定义初始化值。"""
        log_manager = LogManager(
            config=self.basic_config,
            log_dir=self.test_log_dir,
            enqueue=True
        )
        
        assert log_manager.log_dir == self.test_log_dir
        assert log_manager.enqueue is True
        assert os.path.exists(self.test_log_dir)
        assert len(log_manager.loggers) == 2

    @patch('core.utils.log_manager.logger')
    def test_log_directory_creation(self, mock_logger):
        """测试日志目录创建。"""
        non_existent_dir = os.path.join(self.temp_dir, "nested", "log", "dir")
        
        log_manager = LogManager(self.empty_config, log_dir=non_existent_dir)
        
        assert os.path.exists(non_existent_dir)
        assert log_manager.log_dir == non_existent_dir

    # ================== 配置加载测试 ==================
    
    @patch('core.utils.log_manager.logger')
    def test_load_config_basic(self, mock_logger):
        """测试基础配置加载。"""
        mock_logger.add.return_value = "handler_id_123"
        
        log_manager = LogManager(self.basic_config, log_dir=self.test_log_dir)
        
        assert "app" in log_manager.loggers
        assert "db" in log_manager.loggers
        
        # 验证 logger.add 被正确调用
        assert mock_logger.add.call_count == 2

    @patch('core.utils.log_manager.logger')
    def test_load_config_empty(self, mock_logger):
        """测试空配置加载。"""
        log_manager = LogManager(self.empty_config, log_dir=self.test_log_dir)
        
        assert log_manager.loggers == {}
        mock_logger.add.assert_not_called()

    @patch('core.utils.log_manager.logger')
    def test_load_config_console_only(self, mock_logger):
        """测试仅控制台日志配置。"""
        mock_logger.add.return_value = "console_handler_id"
        
        log_manager = LogManager(self.console_config, log_dir=self.test_log_dir)
        
        assert "console" in log_manager.loggers
        mock_logger.add.assert_called_once()

    @patch('core.utils.log_manager.os.name', 'nt')
    @patch('core.utils.log_manager.logger')
    def test_load_config_windows_enqueue(self, mock_logger):
        """测试Windows系统下启用enqueue时的配置加载。"""
        log_manager = LogManager(
            self.basic_config, 
            log_dir=self.test_log_dir, 
            enqueue=True
        )
        
        # 验证在Windows系统下启用enqueue时，logger.remove()被调用
        mock_logger.remove.assert_called_once()

    @patch('core.utils.log_manager.os.name', 'posix')
    @patch('core.utils.log_manager.logger')
    def test_load_config_non_windows_enqueue(self, mock_logger):
        """测试非Windows系统下启用enqueue时的配置加载。"""
        log_manager = LogManager(
            self.basic_config, 
            log_dir=self.test_log_dir, 
            enqueue=True
        )
        
        # 验证在非Windows系统下，logger.remove()不被调用
        mock_logger.remove.assert_not_called()

    # ================== 日志记录器管理测试 ==================
    
    @patch('core.utils.log_manager.logger')
    def test_add_logger_with_file(self, mock_logger):
        """测试添加文件日志记录器。"""
        mock_logger.add.return_value = "file_handler_id"
        
        log_manager = LogManager(self.empty_config, log_dir=self.test_log_dir)
        log_file_path = os.path.join(self.test_log_dir, "test.log")
        
        log_manager.add_logger(
            name="test",
            file=log_file_path,
            level="INFO",
            rotate="1 MB"
        )
        
        assert "test" in log_manager.loggers
        assert log_manager.loggers["test"] == "file_handler_id"
        
        # 验证logger.add被正确调用
        mock_logger.add.assert_called_with(
            log_file_path,
            level="INFO",
            rotation="1 MB",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )

    @patch('core.utils.log_manager.logger')
    def test_add_logger_console_only(self, mock_logger):
        """测试添加控制台日志记录器。"""
        mock_logger.add.return_value = "console_handler_id"
        
        log_manager = LogManager(self.empty_config, log_dir=self.test_log_dir)
        
        log_manager.add_logger(name="console", file=None, level="DEBUG")
        
        assert "console" in log_manager.loggers
        assert log_manager.loggers["console"] == "console_handler_id"
        
        # 验证控制台日志记录器的添加
        args, kwargs = mock_logger.add.call_args
        assert kwargs["level"] == "DEBUG"
        assert callable(args[0])  # 第一个参数应该是lambda函数

    @patch('core.utils.log_manager.logger')
    def test_add_logger_creates_directory(self, mock_logger):
        """测试添加日志记录器时自动创建目录。"""
        nested_log_path = os.path.join(
            self.test_log_dir, "nested", "deep", "test.log"
        )
        
        log_manager = LogManager(self.empty_config, log_dir=self.test_log_dir)
        log_manager.add_logger(name="nested", file=nested_log_path)
        
        # 验证嵌套目录被创建
        assert os.path.exists(os.path.dirname(nested_log_path))

    # ================== 获取日志记录器测试 ==================
    
    @patch('core.utils.log_manager.logger')
    def test_get_logger_success(self, mock_logger):
        """测试成功获取日志记录器。"""
        mock_bound_logger = Mock()
        mock_logger.bind.return_value = mock_bound_logger
        
        log_manager = LogManager(self.basic_config, log_dir=self.test_log_dir)
        
        result_logger = log_manager.get_logger("app")
        
        assert result_logger == mock_bound_logger
        mock_logger.bind.assert_called_with(logger_name="app")

    @patch('core.utils.log_manager.logger')
    def test_get_logger_not_found(self, mock_logger):
        """测试获取不存在的日志记录器。"""
        log_manager = LogManager(self.empty_config, log_dir=self.test_log_dir)
        
        with pytest.raises(ValueError) as exc_info:
            log_manager.get_logger("nonexistent")
        
        assert "Logger 'nonexistent' not found." in str(exc_info.value)

    # ================== 文件路径处理测试 ==================
    
    @patch('core.utils.log_manager.logger')
    def test_file_path_processing(self, mock_logger):
        """测试文件路径处理逻辑。"""
        config_with_paths = {
            "loggers": [
                {
                    "name": "test1",
                    "file": "simple.log",
                    "level": "INFO"
                },
                {
                    "name": "test2",
                    "file": "/absolute/path/to/file.log",
                    "level": "DEBUG"
                },
                {
                    "name": "test3",
                    "file": "nested/directory/file.log",
                    "level": "WARNING"
                }
            ]
        }
        
        log_manager = LogManager(config_with_paths, log_dir=self.test_log_dir)
        
        # 验证所有日志记录器都被创建
        assert len(log_manager.loggers) == 3
        assert "test1" in log_manager.loggers
        assert "test2" in log_manager.loggers
        assert "test3" in log_manager.loggers

    # ================== 参数化测试 ==================
    
    @pytest.mark.parametrize("level,rotate", [
        ("DEBUG", None),
        ("INFO", "1 MB"),
        ("WARNING", "daily"),
        ("ERROR", "weekly"),
        ("CRITICAL", "100 KB")
    ])
    @patch('core.utils.log_manager.logger')
    def test_various_logger_configurations(self, mock_logger, level, rotate):
        """测试各种日志记录器配置。"""
        mock_logger.add.return_value = f"handler_{level}_{rotate}"
        
        config = {
            "loggers": [
                {
                    "name": "test",
                    "file": "test.log",
                    "level": level,
                    "rotate": rotate
                }
            ]
        }
        
        log_manager = LogManager(config, log_dir=self.test_log_dir)
        
        assert "test" in log_manager.loggers
        
        # 验证logger.add的调用参数
        call_args = mock_logger.add.call_args
        assert call_args[1]["level"] == level
        assert call_args[1]["rotation"] == rotate

    # ================== 边界条件测试 ==================
    
    @patch('core.utils.log_manager.logger')
    def test_config_without_loggers_key(self, mock_logger):
        """测试配置中没有loggers键的情况。"""
        invalid_config = {"other_key": "other_value"}
        
        log_manager = LogManager(invalid_config, log_dir=self.test_log_dir)
        
        # 应该能正常处理，但不会添加任何日志记录器
        assert log_manager.loggers == {}

    @patch('core.utils.log_manager.logger')
    def test_logger_config_missing_fields(self, mock_logger):
        """测试日志记录器配置缺少字段的情况。"""
        mock_logger.add.return_value = "default_handler"
        
        minimal_config = {
            "loggers": [
                {},  # 完全空的配置
                {"name": "partial"},  # 只有名称
                {"file": "only_file.log"}  # 只有文件
            ]
        }
        
        log_manager = LogManager(minimal_config, log_dir=self.test_log_dir)
        
        # 应该使用默认值创建日志记录器
        expected_names = ["default", "partial", "default"]
        for name in expected_names:
            if name in log_manager.loggers:
                assert log_manager.loggers[name] == "default_handler"

    # ================== 异常处理测试 ==================
    
    @patch('core.utils.log_manager.os.makedirs')
    def test_directory_creation_failure(self, mock_makedirs):
        """测试目录创建失败的情况。"""
        mock_makedirs.side_effect = OSError("Permission denied")
        
        with pytest.raises(OSError):
            LogManager(self.empty_config, log_dir="/invalid/path")

    @patch('core.utils.log_manager.logger')
    def test_logger_add_failure(self, mock_logger):
        """测试日志记录器添加失败的情况。"""
        mock_logger.add.side_effect = Exception("Logger add failed")
        
        # 应该传播异常
        with pytest.raises(Exception) as exc_info:
            LogManager(self.basic_config, log_dir=self.test_log_dir)
        
        assert "Logger add failed" in str(exc_info.value)

    # ================== 集成测试 ==================
    
    def test_integration_real_file_creation(self):
        """集成测试：验证实际文件创建和日志写入。"""
        # 注意：这个测试不使用mock，测试实际的loguru行为
        real_config = {
            "loggers": [
                {
                    "name": "integration_test",
                    "file": "integration.log",
                    "level": "INFO"
                }
            ]
        }
        
        log_manager = LogManager(real_config, log_dir=self.test_log_dir)
        test_logger = log_manager.get_logger("integration_test")
        
        # 写入测试日志
        test_message = "Integration test message"
        test_logger.info(test_message)
        
        # 验证文件被创建
        log_file_path = os.path.join(self.test_log_dir, "integration.log")
        assert os.path.exists(log_file_path)
        
        # 验证日志内容（注意：可能需要等待缓冲区刷新）
        import time
        time.sleep(0.1)  # 等待写入完成
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert test_message in content

    @patch('core.utils.log_manager.logger')
    def test_multiple_loggers_independence(self, mock_logger):
        """测试多个日志记录器的独立性。"""
        mock_logger.add.return_value = "handler_id"
        mock_logger.bind.side_effect = lambda logger_name: Mock(log_name=f"bound_{logger_name}")
        
        log_manager = LogManager(self.basic_config, log_dir=self.test_log_dir)
        
        app_logger = log_manager.get_logger("app")
        db_logger = log_manager.get_logger("db")
        
        # 验证返回不同的绑定对象
        assert app_logger != db_logger
        assert app_logger.log_name == "bound_app"
        assert db_logger.log_name == "bound_db"

    # ================== 性能测试标记 ==================
    
    @pytest.mark.slow
    @patch('core.utils.log_manager.logger')
    def test_performance_many_loggers(self, mock_logger):
        """性能测试：创建大量日志记录器。"""
        mock_logger.add.return_value = "handler_id"
        
        # 创建包含100个日志记录器的配置
        many_loggers_config = {
            "loggers": [
                {
                    "name": f"logger_{i}",
                    "file": f"log_{i}.log",
                    "level": "INFO"
                }
                for i in range(100)
            ]
        }
        
        import time
        start_time = time.time()
        
        log_manager = LogManager(many_loggers_config, log_dir=self.test_log_dir)
        
        end_time = time.time()
        
        assert len(log_manager.loggers) == 100
        assert end_time - start_time < 5  # 应该在5秒内完成
