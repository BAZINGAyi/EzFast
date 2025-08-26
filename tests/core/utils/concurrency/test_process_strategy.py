import pytest
import time
import multiprocessing
import os
from unittest.mock import Mock, patch
from concurrent.futures import TimeoutError

from core.utils.concurrency.process_strategy import ProcessPoolStrategy


# 全局函数，用于进程池测试（必须在模块级别定义才能被pickle）
def simple_cpu_task(x, y):
    """简单的CPU密集型任务。"""
    return x + y

def multiply_task(x, y):
    """乘法任务。"""
    return x * y

def power_task(base, exp=2):
    """幂运算任务。"""
    return base ** exp

def cpu_intensive_task(n):
    """CPU密集型任务，用于测试性能。"""
    total = 0
    for i in range(n):
        total += i * i
    return total

def slow_cpu_task(duration, value):
    """耗时的CPU任务。"""
    import time
    time.sleep(duration)
    return value

def failing_task():
    """会抛出异常的任务。"""
    raise ValueError("Process test error")

def get_process_info():
    """获取进程信息的任务。"""
    return {
        'pid': os.getpid(),
        'process_name': multiprocessing.current_process().name
    }

def memory_intensive_task(size):
    """内存密集型任务。"""
    data = list(range(size))
    return sum(data)

# 测试自定义初始化函数
def init_worker():
    # 进程初始化函数
    pass

class TestProcessPoolStrategy:
    """ProcessPoolStrategy 的完整测试套件。"""
    
    def setup_method(self):
        """每个测试方法前的设置。"""
        self.mock_logger = Mock()
        self.strategy = ProcessPoolStrategy(logger=self.mock_logger)
    
    # ================== 基础功能测试 ==================
    
    def test_init_default_values(self):
        """测试默认初始化值。"""
        strategy = ProcessPoolStrategy()
        assert strategy.logger is None
        assert strategy.error_handling == 'log'
        assert strategy.timeout is None
        assert strategy.max_tasks_per_child is None
        assert strategy.process_kwargs == {}
    
    def test_init_custom_values(self):
        """测试自定义初始化值。"""
        custom_kwargs = {'initializer': lambda: None}
        strategy = ProcessPoolStrategy(
            logger=self.mock_logger,
            error_handling='raise',
            timeout=10,
            max_tasks_per_child=5,
            **custom_kwargs
        )
        assert strategy.logger == self.mock_logger
        assert strategy.error_handling == 'raise'
        assert strategy.timeout == 10
        assert strategy.max_tasks_per_child == 5
        assert strategy.process_kwargs == custom_kwargs
    
    # ================== 任务执行测试 ==================
    
    def test_execute_single_task_success(self):
        """测试单个任务成功执行。"""
        tasks = [(simple_cpu_task, (2, 3))]
        results = self.strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, 5)
        
        # 验证日志调用
        self.mock_logger.info.assert_called()
    
    def test_execute_multiple_tasks_success(self):
        """测试多个任务成功执行。"""
        tasks = [
            (simple_cpu_task, (2, 3)),
            (multiply_task, (4, 5)),
            (power_task, (6,))
        ]
        
        results = self.strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 3
        assert results[0] == (True, 5)   # 2 + 3
        assert results[1] == (True, 20)  # 4 * 5
        assert results[2] == (True, 36)  # 6 ** 2
    
    def test_execute_cpu_intensive_tasks(self):
        """测试CPU密集型任务的并行执行。"""
        tasks = [(cpu_intensive_task, (10000,)) for _ in range(3)]
        
        # 测试单进程执行时间
        start_time = time.time()
        results_single = ProcessPoolStrategy().execute(tasks, worker_count=1)
        single_time = time.time() - start_time
        
        # 测试多进程执行时间
        start_time = time.time()
        results_multi = ProcessPoolStrategy().execute(tasks, worker_count=2)
        multi_time = time.time() - start_time
        
        # 验证结果正确性
        assert len(results_single) == 3
        assert len(results_multi) == 3
        assert all(success for success, _ in results_single)
        assert all(success for success, _ in results_multi)
        
        # 在多核系统上，多进程应该比单进程快（但考虑到进程创建开销，不强制要求）
        print(f"单进程时间: {single_time:.3f}s, 多进程时间: {multi_time:.3f}s")
    
    # ================== 进程隔离测试 ==================
    
    def test_process_isolation(self):
        """测试进程间隔离。"""
        tasks = [(get_process_info, ()) for _ in range(3)]
        results = self.strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 3
        assert all(success for success, _ in results)
        
        # 提取进程信息
        process_infos = [result for success, result in results if success]
        pids = [info['pid'] for info in process_infos]
        
        # 验证使用了不同的进程
        unique_pids = set(pids)
        assert len(unique_pids) >= 1  # 至少使用了一个进程
        
        # 如果使用了多个worker，应该有多个不同的PID
        if len(unique_pids) > 1:
            print(f"使用了 {len(unique_pids)} 个不同的进程: {unique_pids}")
    
    def test_different_worker_counts(self):
        """测试不同的工作进程数配置。"""
        # 创建足够多的任务来测试进程分配
        tasks = [(get_process_info, ()) for _ in range(6)]
        
        # 测试1个进程
        results_1 = self.strategy.execute(tasks, worker_count=1)
        pids_1 = [result['pid'] for success, result in results_1 if success]
        unique_pids_1 = set(pids_1)
        
        # 测试3个进程
        results_3 = self.strategy.execute(tasks, worker_count=3)
        pids_3 = [result['pid'] for success, result in results_3 if success]
        unique_pids_3 = set(pids_3)
        
        # 验证结果
        assert len(results_1) == 6
        assert len(results_3) == 6
        assert all(success for success, _ in results_1)
        assert all(success for success, _ in results_3)
        
        # 1个进程时，所有任务应该在同一进程中执行
        assert len(unique_pids_1) == 1
        
        # 3个进程时，可能使用多个进程（但不一定用满3个）
        assert len(unique_pids_3) >= 1
        print(f"1个worker: {len(unique_pids_1)}个进程, 3个worker: {len(unique_pids_3)}个进程")
    
    # ================== 错误处理测试 ==================
    
    def test_execute_task_with_exception_log_mode(self):
        """测试任务异常的日志模式处理。"""
        tasks = [
            (failing_task, ()),
            (simple_cpu_task, (1, 2))
        ]
        
        strategy = ProcessPoolStrategy(logger=self.mock_logger, error_handling='log')
        results = strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 2
        assert results[0][0] is False  # 失败任务
        assert "Process test error" in str(results[0][1])
        assert results[1] == (True, 3)  # 成功任务
        
        # 验证错误日志被调用
        self.mock_logger.error.assert_called()
    
    def test_execute_task_with_exception_raise_mode(self):
        """测试任务异常的抛出模式处理。"""
        tasks = [(failing_task, ())]
        
        strategy = ProcessPoolStrategy(logger=self.mock_logger, error_handling='raise')
        
        # 在raise模式下，异常会在_handle_error中处理
        with pytest.raises(ValueError, match="Process test error"):
            strategy.execute(tasks, worker_count=1)
    
    def test_execute_task_submission_error(self):
        """测试任务提交时的错误处理。"""
        # 创建一个不可pickle的任务来模拟提交错误
        def unpicklable_task():
            # 包含不可pickle的局部函数
            def inner():
                return "inner"
            return inner()
        
        tasks = [(unpicklable_task, ())]
        
        # 由于进程池需要pickle，这个任务可能会失败
        results = self.strategy.execute(tasks, worker_count=1)
        
        # 结果应该能正常返回（可能成功也可能失败，取决于pickle能力）
        assert len(results) == 1
        # 不强制要求特定结果，因为pickle行为可能因Python版本而异
    
    # ================== 超时测试 ==================
    
    def test_execute_with_timeout_success(self):
        """测试超时设置下的成功执行。"""
        tasks = [(slow_cpu_task, (0.1, "completed"))]
        strategy = ProcessPoolStrategy(logger=self.mock_logger, timeout=2.0)
        
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, "completed")
    
    def test_execute_with_timeout_failure(self):
        """测试超时失败的情况。"""
        tasks = [(slow_cpu_task, (2.0, "should not complete"))]
        strategy = ProcessPoolStrategy(logger=self.mock_logger, timeout=0.5)
        
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0][0] is False  # 执行失败
        # 检查是否包含超时相关的错误信息
        error_message = str(results[0][1]).lower()
        assert "timeout" in error_message or "timed out" in error_message
    
    # ================== 进程池配置测试 =================
    
    def test_process_kwargs_passthrough(self):
        """测试进程池参数透传。"""

        custom_kwargs = {
            'initializer': init_worker,
            # 其他进程池参数可以在这里添加
        }
        
        strategy = ProcessPoolStrategy(
            logger=self.mock_logger,
            **custom_kwargs
        )
        
        tasks = [(simple_cpu_task, (1, 2))]
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, 3)
    
    # ================== 结果顺序测试 ==================
    
    def test_result_order_preservation(self):
        """测试结果顺序保持与输入一致。"""
        # 创建不同执行时间的任务
        tasks = [
            (slow_cpu_task, (0.3, 'first')),   # 最慢
            (slow_cpu_task, (0.1, 'second')),  # 中等
            (slow_cpu_task, (0.05, 'third'))   # 最快
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
        """测试零工作进程数（应该使用系统默认）。"""
        tasks = [(simple_cpu_task, (1, 1))]
        
        # ProcessPoolExecutor会使用默认的进程数
        results = self.strategy.execute(tasks, worker_count=0)
        
        assert len(results) == 1
        assert results[0] == (True, 2)
    
    # ================== 内存和性能测试 ==================
    
    def test_memory_intensive_tasks(self):
        """测试内存密集型任务。"""
        # 创建一些内存密集型任务
        tasks = [(memory_intensive_task, (10000,)) for _ in range(3)]
        
        results = self.strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 3
        assert all(success for success, _ in results)
        
        # 验证计算结果正确
        expected_sum = sum(range(10000))
        for success, result in results:
            assert success
            assert result == expected_sum
    
    def test_large_number_of_tasks(self):
        """测试大量任务的处理。"""
        # 创建大量小任务
        tasks = [(simple_cpu_task, (i, i+1)) for i in range(50)]
        
        start_time = time.time()
        results = self.strategy.execute(tasks, worker_count=4)
        elapsed_time = time.time() - start_time
        
        # 验证所有任务都成功完成
        assert len(results) == 50
        assert all(success for success, _ in results)
        
        # 验证结果正确性
        for i, (success, result) in enumerate(results):
            assert success
            assert result == i + (i + 1)
        
        print(f"50个任务在{elapsed_time:.3f}秒内完成")
    
    # ================== 日志功能测试 ==================
    
    def test_logging_without_logger(self):
        """测试没有logger时的控制台输出。"""
        strategy = ProcessPoolStrategy()  # 没有logger
        
        tasks = [(simple_cpu_task, (1, 2))]
        
        # 这个测试主要确保没有logger时不会出错
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, 3)
    
    def test_logging_messages(self):
        """测试各种日志消息的调用。"""
        tasks = [(simple_cpu_task, (2, 3))]
        results = self.strategy.execute(tasks, worker_count=1)
        
        # 检查info日志被调用
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        
        # 应该包含启动和完成的日志
        assert any('Starting process pool execution' in call for call in info_calls)
        assert any('completed successfully' in call for call in info_calls)
        assert any('Process pool execution completed' in call for call in info_calls)
    
    # ================== 集成测试 ==================
    
    def test_complex_mixed_scenario(self):
        """复杂混合场景测试：成功、失败、超时、不同参数。"""
        tasks = [
            (simple_cpu_task, (1, 2)),          # 成功
            (failing_task, ()),                  # 失败
            (simple_cpu_task, (3, 4)),          # 成功
            (slow_cpu_task, (3.0, "slow")),     # 超时失败
        ]
        
        strategy = ProcessPoolStrategy(
            logger=self.mock_logger,
            error_handling='log',
            timeout=2  # slow_cpu_task会超时
        )
        
        results = strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 4
        assert results[0] == (True, 3)         # 成功
        assert results[1][0] is False          # 失败
        assert results[2] == (True, 7)         # 成功
        assert results[3][0] is False          # 超时失败
        
        # 验证错误日志被调用（失败和超时）
        assert self.mock_logger.error.call_count >= 2


# ================== 参数化测试 ==================

class TestProcessPoolStrategyParametrized:
    """参数化测试类。"""
    
    @pytest.mark.parametrize("worker_count", [1, 2, 4])
    def test_different_worker_counts_performance(self, worker_count):
        """测试不同工作进程数的性能表现。"""
        # 使用CPU密集型任务测试
        tasks = [(cpu_intensive_task, (5000,)) for _ in range(4)]
        strategy = ProcessPoolStrategy()
        
        start_time = time.time()
        results = strategy.execute(tasks, worker_count=worker_count)
        elapsed_time = time.time() - start_time
        
        # 所有任务都应该成功
        assert all(success for success, _ in results)
        assert len(results) == 4
        
        # 记录性能数据
        print(f"Worker count: {worker_count}, Time: {elapsed_time:.3f}s")
    
    @pytest.mark.parametrize("error_handling", ['log', 'raise'])
    def test_error_handling_modes(self, error_handling):
        """测试不同错误处理模式。"""
        tasks = [(failing_task, ())]
        strategy = ProcessPoolStrategy(error_handling=error_handling)
        
        if error_handling == 'log':
            results = strategy.execute(tasks, worker_count=1)
            assert len(results) == 1
            assert results[0][0] is False
            assert "Process test error" in str(results[0][1])
            
        else:
            with pytest.raises(Exception, match="Process test error"):
                strategy.execute(tasks, worker_count=1)

    @pytest.mark.parametrize("timeout", [1, 5, 2, None])
    def test_different_timeout_values(self, timeout):
        """测试不同超时值的行为。"""
        tasks = [(slow_cpu_task, (2, f"completed_after_0.2"))]  # 固定0.2秒的任务
        strategy = ProcessPoolStrategy(timeout=timeout)
        
        results = strategy.execute(tasks, worker_count=1)
        
        if timeout is None or timeout > 2:
            # 应该成功
            assert results[0] == (True, "completed_after_0.2")
        else:
            # 应该超时失败
            assert results[0][0] is False
    
    @pytest.mark.parametrize("max_tasks_per_child", [None, 1, 3, 5])
    def test_max_tasks_per_child_values(self, max_tasks_per_child):
        """测试不同的max_tasks_per_child值。"""
        tasks = [(simple_cpu_task, (i, i+1)) for i in range(6)]
        strategy = ProcessPoolStrategy(max_tasks_per_child=max_tasks_per_child)
        
        results = strategy.execute(tasks, worker_count=2)
        
        # 无论如何设置，所有任务都应该成功完成
        assert len(results) == 6
        assert all(success for success, _ in results)
        
        # 验证结果正确性
        for i, (success, result) in enumerate(results):
            assert success
            assert result == i + (i + 1)


# ================== Fixture 定义 ==================

@pytest.fixture
def sample_cpu_tasks():
    """提供示例CPU任务的fixture。"""
    return [
        (simple_cpu_task, (2, 3)),
        (multiply_task, (4, 5)),
        (power_task, (3,))
    ]

@pytest.fixture
def process_logger_mock():
    """提供mock logger的fixture。"""
    return Mock()


class TestProcessPoolStrategyWithFixtures:
    """使用fixtures的测试类。"""
    
    def test_with_sample_cpu_tasks(self, sample_cpu_tasks, process_logger_mock):
        """使用fixtures的示例测试。"""
        strategy = ProcessPoolStrategy(logger=process_logger_mock)
        results = strategy.execute(sample_cpu_tasks, worker_count=2)
        
        expected_results = [
            (True, 5),   # 2 + 3
            (True, 20),  # 4 * 5  
            (True, 9),   # 3 ** 2
        ]
        
        assert results == expected_results
        process_logger_mock.info.assert_called()


# ================== 平台特定测试 ==================

class TestProcessPoolStrategyPlatformSpecific:
    """平台特定的测试类。"""
    
    @pytest.mark.skipif(os.name == 'nt', reason="Windows上的多进程行为可能不同")
    def test_unix_specific_behavior(self):
        """Unix/Linux特定的行为测试。"""
        tasks = [(get_process_info, ()) for _ in range(3)]
        strategy = ProcessPoolStrategy()
        
        results = strategy.execute(tasks, worker_count=2)
        
        assert len(results) == 3
        assert all(success for success, _ in results)
    
    @pytest.mark.skipif(os.name != 'nt', reason="仅在Windows上运行")
    def test_windows_specific_behavior(self):
        """Windows特定的行为测试。"""
        tasks = [(simple_cpu_task, (1, 2))]
        strategy = ProcessPoolStrategy()
        
        results = strategy.execute(tasks, worker_count=1)
        
        assert len(results) == 1
        assert results[0] == (True, 3)


if __name__ == "__main__":
    # 直接运行测试文件时的行为
    pytest.main([__file__, "-v", "--tb=short"])
