import pytest
import time
import threading
from unittest.mock import Mock, patch
from concurrent.futures import TimeoutError

from core.utils.concurrency.thread_strategy import ThreadPoolStrategy


class TestThreadPoolStrategy:
    """ThreadPoolStrategy 的完整测试套件。"""
    
    def setup_method(self):
        """每个测试方法前的设置。"""
        self.mock_logger = Mock()
        self.strategy = ThreadPoolStrategy(logger=self.mock_logger)
    
    # ================== 基础功能测试 ==================
    
    def test_init_default_values(self):
        """测试默认初始化值。"""
        strategy = ThreadPoolStrategy()
        assert strategy.logger is None
        assert strategy.error_handling == 'log'
        assert strategy.timeout is None
        assert strategy.thread_name_prefix == 'EZ-ThreadPool'
        assert strategy.thread_kwargs == {}
    
    def test_init_custom_values(self):
        """测试自定义初始化值。"""
        custom_kwargs = {'initializer': lambda: None}
        strategy = ThreadPoolStrategy(
            logger=self.mock_logger,
            error_handling='raise',
            timeout=10,
            thread_name_prefix='CustomThread',
            **custom_kwargs
        )
        assert strategy.logger == self.mock_logger
        assert strategy.error_handling == 'raise'
        assert strategy.timeout == 10
        assert strategy.thread_name_prefix == 'CustomThread'
        assert strategy.thread_kwargs == custom_kwargs
    
    # ================== 任务执行测试 ==================
    
    def test_execute_single_task_success(self):
        """测试单个任务成功执行。"""
        def simple_task(x, y):
            return x + y
        
        tasks = [(simple_task, (2, 3))]
        results = self.strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, 5)
        
        # 验证日志调用
        self.mock_logger.info.assert_called()
    
    def test_execute_multiple_tasks_success(self):
        """测试多个任务成功执行。"""
        def add_task(x, y):
            return x + y
        
        def multiply_task(x, y):
            return x * y
        
        def power_task(base):
            return base ** 2
        
        tasks = [
            (add_task, (2, 3)),
            (multiply_task, (4, 5)),
            (power_task, (6,))
        ]
        
        results = self.strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 3
        assert results[0] == (True, 5)   # 2 + 3
        assert results[1] == (True, 20)  # 4 * 5
        assert results[2] == (True, 36)  # 6 ** 2
    
    def test_execute_task_with_sleep(self):
        """测试包含延迟的任务执行。"""
        def slow_task(duration, value):
            time.sleep(duration)
            return value
        
        tasks = [
            (slow_task, (0.1, 'task1')),
            (slow_task, (0.1, 'task2'))
        ]
        
        start_time = time.time()
        results = self.strategy.execute(tasks, worker_count=2)
        elapsed_time = time.time() - start_time
        
        # 并发执行，总时间应该小于串行执行时间
        assert elapsed_time < 0.3  # 比串行执行的0.2s留有余量
        assert len(results) == 2
        assert results[0] == (True, 'task1')
        assert results[1] == (True, 'task2')
    
    # ================== 错误处理测试 ==================
    
    def test_execute_task_with_exception_log_mode(self):
        """测试任务异常的日志模式处理。"""
        def failing_task():
            raise ValueError("Test error")
        
        def success_task():
            return "success"
        
        tasks = [
            (failing_task, ()),
            (success_task, ())
        ]
        
        strategy = ThreadPoolStrategy(logger=self.mock_logger, error_handling='log')
        results = strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 2
        assert results[0][0] is False  # 失败任务
        assert "Test error" in str(results[0][1])
        assert results[1] == (True, "success")  # 成功任务
        
        # 验证错误日志被调用
        self.mock_logger.error.assert_called()
    
    def test_execute_task_with_exception_raise_mode(self):
        """测试任务异常的抛出模式处理。"""
        def failing_task():
            raise ValueError("Test error")
        
        tasks = [(failing_task, ())]
        
        strategy = ThreadPoolStrategy(logger=self.mock_logger, error_handling='raise')
        
        # 注意：在raise模式下，异常会在_handle_error中被重新抛出
        with pytest.raises(ValueError, match="Test error"):
            strategy.execute(tasks, worker_count=1)
    
    def test_execute_task_submission_error(self):
        """测试任务提交时的错误处理。"""
        # 模拟一个无法序列化的任务（通过patch模拟提交失败）
        def normal_task():
            return "success"
        
        tasks = [(normal_task, ())]
        
        with patch.object(ThreadPoolStrategy, '_handle_error') as mock_handle_error:
            mock_handle_error.return_value = (False, "Submission failed")
            
            # 通过patch模拟executor.submit抛出异常
            with patch('concurrent.futures.ThreadPoolExecutor.submit', side_effect=Exception("Submit error")):
                results = self.strategy.execute(tasks, worker_count=1)
                
                assert len(results) == 1
                assert results[0] == (False, "Submission failed")
                mock_handle_error.assert_called()
    
    # ================== 超时测试 ==================
    
    def test_execute_with_timeout_success(self):
        """测试超时设置下的成功执行。"""
        def quick_task():
            time.sleep(0.1)
            return "completed"
        
        tasks = [(quick_task, ())]
        strategy = ThreadPoolStrategy(logger=self.mock_logger, timeout=1.0)
        
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, "completed")
    
    def test_execute_with_timeout_failure(self):
        """测试超时失败的情况。"""
        def slow_task():
            time.sleep(2.0)  # 超过超时时间
            return "should not complete"
        
        tasks = [(slow_task, ())]
        strategy = ThreadPoolStrategy(logger=self.mock_logger, timeout=0.5)
        
        results = strategy.execute(tasks, worker_count=1)
        assert len(results) == 1
        assert results[0][0] is False  # 执行失败
        # 检查是否包含超时相关的错误信息
        assert "timeout" in str(results[0][1]).lower() or "timed out" in str(results[0][1]).lower()
    
    # ================== 线程池配置测试 ==================
    
    def test_thread_name_prefix(self):
        """测试线程名称前缀配置。"""
        def get_thread_name():
            return threading.current_thread().name
        
        tasks = [(get_thread_name, ())]
        strategy = ThreadPoolStrategy(thread_name_prefix='TestThread')
        
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0][0] is True
        thread_name = results[0][1]
        assert 'TestThread' in thread_name
    
    def test_different_worker_counts(self):
        """测试不同的工作线程数配置。"""
        def get_thread_id():
            return threading.get_ident()
        
        # 创建多个任务
        tasks = [(get_thread_id, ()) for _ in range(5)]
        
        # 使用1个线程
        results_1 = self.strategy.execute(tasks, worker_count=1)
        thread_ids_1 = [result for success, result in results_1 if success]
        
        # 使用3个线程
        results_3 = self.strategy.execute(tasks, worker_count=3)
        thread_ids_3 = [result for success, result in results_3 if success]
        
        # 1个线程时，所有任务应该在同一个线程中执行
        assert len(set(thread_ids_1)) == 1
        
        # 3个线程时，可能使用多个线程（但不一定用满3个）
        assert len(set(thread_ids_3)) >= 1
    
    # ================== 结果顺序测试 ==================
    
    def test_result_order_preservation(self):
        """测试结果顺序保持与输入一致。"""
        def delayed_task(delay, value):
            time.sleep(delay)
            return value
        
        # 创建不同延迟的任务，第一个任务最慢
        tasks = [
            (delayed_task, (0.3, 'first')),   # 最慢
            (delayed_task, (0.1, 'second')),  # 中等
            (delayed_task, (0.05, 'third'))   # 最快
        ]
        
        results = self.strategy.execute(tasks, worker_count=3)
        
        # 尽管执行顺序不同，结果应该按输入顺序返回
        assert len(results) == 3
        assert results[0] == (True, 'first')
        assert results[1] == (True, 'second')
        assert results[2] == (True, 'third')
    
    # ================== 边界条件测试 ==================
    
    def test_execute_empty_tasks(self):
        """测试空任务列表。"""
        tasks = []
        results = self.strategy.execute(tasks, worker_count=1)
        
        assert results == []
    
    def test_execute_with_zero_workers(self):
        """测试零工作线程数（应该使用系统默认）。"""
        def simple_task():
            return "done"
        
        tasks = [(simple_task, ())]
        
        # ThreadPoolExecutor会使用默认的线程数
        results = self.strategy.execute(tasks, worker_count=0)
        
        assert len(results) == 1
        assert results[0] == (True, "done")
    
    def test_task_without_name_attribute(self):
        """测试没有__name__属性的可调用对象。"""
        # 使用lambda创建没有__name__的任务
        task = lambda x: x * 2
        tasks = [(task, (5,))]
        
        results = self.strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, 10)
        
        # 验证日志中使用了索引命名
        logged_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        task_complete_logs = [log for log in logged_calls if 'completed successfully' in log]
        assert any('task_0' in log for log in task_complete_logs)
    
    # ================== 日志功能测试 ==================
    
    def test_logging_without_logger(self):
        """测试没有logger时的控制台输出。"""
        strategy = ThreadPoolStrategy()  # 没有logger
        
        def simple_task():
            return "test"
        
        tasks = [(simple_task, ())]
        
        # 这个测试主要确保没有logger时不会出错
        # 实际的print输出比较难测试，但至少确保代码运行正常
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, "test")
    
    def test_logging_messages(self):
        """测试各种日志消息的调用。"""
        def simple_task():
            return "success"
        
        tasks = [(simple_task, ())]
        results = self.strategy.execute(tasks, worker_count=1)
        
        # 检查info日志被调用
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        
        # 应该包含启动和完成的日志
        assert any('Starting thread pool execution' in call for call in info_calls)
        assert any('completed successfully' in call for call in info_calls)
        assert any('Thread pool execution completed' in call for call in info_calls)
    
    # ================== 集成测试 ==================
    
    def test_complex_mixed_scenario(self):
        """复杂混合场景测试：成功、失败、超时、不同参数。"""
        def success_task(value):
            return f"success_{value}"
        
        def failing_task():
            raise RuntimeError("Expected failure")
        
        def slow_task():
            time.sleep(1)
            return "slow_success"
        
        tasks = [
            (success_task, ("A",)),
            (failing_task, ()),
            (success_task, ("B",)),
            (slow_task, ()),
        ]
        
        strategy = ThreadPoolStrategy(
            logger=self.mock_logger,
            error_handling='log',
            timeout=0.5  # slow_task会超时
        )
        
        results = strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 4
        assert results[0] == (True, "success_A")   # 成功
        assert results[1][0] is False              # 失败
        assert results[2] == (True, "success_B")   # 成功
        assert results[3][0] is False              # 超时失败
        
        # 验证错误日志被调用（失败和超时）
        assert self.mock_logger.error.call_count >= 2


# ================== 参数化测试 ==================

class TestThreadPoolStrategyParametrized:
    """参数化测试类。"""
    
    @pytest.mark.parametrize("worker_count", [1, 2, 4, 8])
    def test_different_worker_counts_performance(self, worker_count):
        """测试不同工作线程数的性能表现。"""
        def cpu_task(n):
            # 简单的CPU密集型任务
            total = 0
            for i in range(n):
                total += i
            return total
        
        tasks = [(cpu_task, (1000,)) for _ in range(4)]
        strategy = ThreadPoolStrategy()
        
        start_time = time.time()
        results = strategy.execute(tasks, worker_count=worker_count)
        elapsed_time = time.time() - start_time
        
        # 所有任务都应该成功
        assert all(success for success, _ in results)
        assert len(results) == 4
        
        # 记录性能数据（实际项目中可能会保存到文件或数据库）
        print(f"Worker count: {worker_count}, Time: {elapsed_time:.3f}s")
    
    @pytest.mark.parametrize("error_handling", ['log', 'raise'])
    def test_error_handling_modes(self, error_handling):
        """测试不同错误处理模式。"""
        def failing_task():
            raise ValueError("Test error")
        
        tasks = [(failing_task, ())]
        strategy = ThreadPoolStrategy(error_handling=error_handling)
        
        if error_handling == 'log':
            results = strategy.execute(tasks, worker_count=1)
            assert len(results) == 1
            assert results[0][0] is False
            assert "Test error" in str(results[0][1])
        else:
            with pytest.raises(ValueError, match="Test error"):
                results = strategy.execute(tasks, worker_count=1)
    
    @pytest.mark.parametrize("timeout", [0.1, 0.5, 1.0, None])
    def test_different_timeout_values(self, timeout):
        """测试不同超时值的行为。"""
        def variable_delay_task(delay):
            time.sleep(delay)
            return f"completed_after_{delay}"
        
        tasks = [(variable_delay_task, (0.2,))]  # 固定0.2秒的任务
        strategy = ThreadPoolStrategy(timeout=timeout)
        
        results = strategy.execute(tasks, worker_count=1)
        
        if timeout is None or timeout > 0.2:
            # 应该成功
            assert results[0] == (True, "completed_after_0.2")
        else:
            # 应该超时失败
            assert results[0][0] is False


# ================== Fixture 定义 ==================

@pytest.fixture
def sample_tasks():
    """提供示例任务的fixture。"""
    def add(a, b):
        return a + b
    
    def multiply(a, b):
        return a * b
    
    def power(base, exp=2):
        return base ** exp
    
    return [
        (add, (2, 3)),
        (multiply, (4, 5)),
        (power, (3,))
    ]

@pytest.fixture
def logger_mock():
    """提供mock logger的fixture。"""
    return Mock()


class TestThreadPoolStrategyWithFixtures:
    """使用fixtures的测试类。"""
    
    def test_with_sample_tasks(self, sample_tasks, logger_mock):
        """使用fixtures的示例测试。"""
        strategy = ThreadPoolStrategy(logger=logger_mock)
        results = strategy.execute(sample_tasks, worker_count=2)
        
        expected_results = [
            (True, 5),   # 2 + 3
            (True, 20),  # 4 * 5  
            (True, 9),   # 3 ** 2
        ]
        
        assert results == expected_results
        logger_mock.info.assert_called()


if __name__ == "__main__":
    # 直接运行测试文件时的行为
    pytest.main([__file__, "-v"])
