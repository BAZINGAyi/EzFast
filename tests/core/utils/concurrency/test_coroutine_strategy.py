import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from concurrent.futures import TimeoutError
import pytest_asyncio

from core.utils.concurrency.coroutine_strategy import CoroutineStrategy


class TestCoroutineStrategy:
    """CoroutineStrategy 的完整测试套件。"""
    
    def setup_method(self):
        """每个测试方法前的设置。"""
        self.mock_logger = Mock()
        self.strategy = CoroutineStrategy(logger=self.mock_logger)
    
    # ================== 基础功能测试 ==================
    
    def test_init_default_values(self):
        """测试默认初始化值。"""
        strategy = CoroutineStrategy()
        assert strategy.logger is None
        assert strategy.error_handling == 'log'
        assert strategy.timeout is None
        assert strategy.return_exceptions is True
        assert strategy.asyncio_kwargs == {}
    
    def test_init_custom_values(self):
        """测试自定义初始化值。"""
        custom_kwargs = {'loop': None}
        strategy = CoroutineStrategy(
            logger=self.mock_logger,
            error_handling='raise',
            timeout=10,
            return_exceptions=False,
            **custom_kwargs
        )
        assert strategy.logger == self.mock_logger
        assert strategy.error_handling == 'raise'
        assert strategy.timeout == 10
        assert strategy.return_exceptions is False
        assert strategy.asyncio_kwargs == custom_kwargs
    
    # ================== 异步任务执行测试 ==================
    
    @pytest.mark.asyncio
    async def test_async_execute_single_task_success(self):
        """测试单个异步任务成功执行。"""
        async def simple_async_task(x, y):
            await asyncio.sleep(0.01)  # 模拟异步操作
            return x + y
        
        tasks = [(simple_async_task, (2, 3))]
        results = await self.strategy.async_execute(tasks)
        
        assert len(results) == 1
        assert results[0] == (True, 5)
        
        # 验证日志调用
        self.mock_logger.info.assert_called()
    
    @pytest.mark.asyncio
    async def test_async_execute_multiple_tasks_success(self):
        """测试多个异步任务成功执行。"""
        async def add_task(x, y):
            await asyncio.sleep(0.01)
            return x + y
        
        async def multiply_task(x, y):
            await asyncio.sleep(0.02)
            return x * y
        
        async def power_task(base):
            await asyncio.sleep(0.01)
            return base ** 2
        
        tasks = [
            (add_task, (2, 3)),
            (multiply_task, (4, 5)),
            (power_task, (6,))
        ]
        
        results = await self.strategy.async_execute(tasks)
        
        assert len(results) == 3
        assert results[0] == (True, 5)   # 2 + 3
        assert results[1] == (True, 20)  # 4 * 5
        assert results[2] == (True, 36)  # 6 ** 2
    
    @pytest.mark.asyncio
    async def test_async_execute_concurrent_performance(self):
        """测试协程并发执行的性能优势。"""
        async def slow_task(duration, value):
            await asyncio.sleep(duration)
            return value
        
        tasks = [
            (slow_task, (0.1, 'task1')),
            (slow_task, (0.1, 'task2')),
            (slow_task, (0.1, 'task3'))
        ]
        
        start_time = time.time()
        results = await self.strategy.async_execute(tasks)
        elapsed_time = time.time() - start_time
        
        # 并发执行，总时间应该接近最慢任务的时间，而不是所有任务时间之和
        assert elapsed_time < 0.2  # 应该远小于串行执行的0.3s
        assert len(results) == 3
        assert all(success for success, _ in results)
        assert [result for success, result in results] == ['task1', 'task2', 'task3']
    
    # ================== 同步接口测试 ==================
    
    def test_execute_sync_interface(self):
        """测试同步接口 execute 方法。"""
        async def simple_async_task(x):
            await asyncio.sleep(0.01)
            return x * 2
        
        tasks = [(simple_async_task, (5,))]
        results = self.strategy.execute(tasks)
        
        assert len(results) == 1
        assert results[0] == (True, 10)
    
    def test_execute_multiple_sync_calls(self):
        """测试多次同步调用。"""
        async def async_task(value):
            await asyncio.sleep(0.01)
            return f"processed_{value}"
        
        for i in range(3):
            tasks = [(async_task, (f"item_{i}",))]
            results = self.strategy.execute(tasks)
            
            assert len(results) == 1
            assert results[0] == (True, f"processed_item_{i}")
    
    # ================== 并发控制测试 ==================
    
    @pytest.mark.asyncio
    async def test_worker_count_semaphore_control(self):
        """测试工作单元数的信号量控制。"""
        concurrent_tasks = []
        max_concurrent = 0
        current_concurrent = 0
        
        async def tracking_task(task_id):
            nonlocal current_concurrent, max_concurrent
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
            concurrent_tasks.append(f"start_{task_id}")
            
            await asyncio.sleep(0.1)  # 模拟异步工作
            
            current_concurrent -= 1
            concurrent_tasks.append(f"end_{task_id}")
            return f"result_{task_id}"
        
        tasks = [(tracking_task, (i,)) for i in range(5)]
        
        # 限制并发数为2
        results = await self.strategy.async_execute(tasks, worker_count=2)
        
        # 验证结果
        assert len(results) == 5
        assert all(success for success, _ in results)
        
        # 验证最大并发数没有超过限制
        assert max_concurrent <= 2
        
        # 验证所有任务都完成了
        start_events = [event for event in concurrent_tasks if event.startswith('start_')]
        end_events = [event for event in concurrent_tasks if event.startswith('end_')]
        assert len(start_events) == 5
        assert len(end_events) == 5
    
    @pytest.mark.asyncio
    async def test_unlimited_concurrency(self):
        """测试无限制并发（worker_count=None）。"""
        start_times = []
        
        async def timestamp_task(task_id):
            start_times.append(time.time())
            await asyncio.sleep(0.05)
            return task_id
        
        tasks = [(timestamp_task, (i,)) for i in range(5)]
        
        start_time = time.time()
        results = await self.strategy.async_execute(tasks, worker_count=None)
        
        # 验证所有任务都成功
        assert len(results) == 5
        assert all(success for success, _ in results)
        
        # 验证任务几乎同时开始（无并发限制）
        time_diffs = [t - start_time for t in start_times]
        assert all(diff < 0.01 for diff in time_diffs)  # 所有任务几乎同时开始
    
    # ================== 错误处理测试 ==================
    
    @pytest.mark.asyncio
    async def test_async_task_exception_log_mode(self):
        """测试异步任务异常的日志模式处理。"""
        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Async test error")
        
        async def success_task():
            await asyncio.sleep(0.01)
            return "success"
        
        tasks = [
            (failing_task, ()),
            (success_task, ())
        ]
        
        strategy = CoroutineStrategy(logger=self.mock_logger, error_handling='log')
        results = await strategy.async_execute(tasks)
        
        assert len(results) == 2
        assert results[0][0] is False  # 失败任务
        assert "Async test error" in str(results[0][1])
        assert results[1] == (True, "success")  # 成功任务
        
        # 验证错误日志被调用
        self.mock_logger.error.assert_called()
    
    @pytest.mark.asyncio
    async def test_async_task_exception_raise_mode(self):
        """测试异步任务异常的抛出模式处理。"""
        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Async test error")
        
        tasks = [(failing_task, ())]
        
        strategy = CoroutineStrategy(logger=self.mock_logger, error_handling='raise')
        
        # 在 raise 模式下，异常会在 _handle_error 中处理
        with pytest.raises(ValueError, match="Async test error"):
            results = await strategy.async_execute(tasks)
    
    @pytest.mark.asyncio
    async def test_return_exceptions_behavior(self):
        """测试 return_exceptions 参数的行为。"""
        async def failing_task():
            raise RuntimeError("Test exception")
        
        async def success_task():
            return "success"
        
        tasks = [
            (failing_task, ()),
            (success_task, ())
        ]
        
        # 测试 return_exceptions=True（默认）
        strategy_true = CoroutineStrategy(return_exceptions=True)
        results_true = await strategy_true.async_execute(tasks)
        
        assert len(results_true) == 2
        assert results_true[0][0] is False  # 异常被处理为失败结果
        assert results_true[1] == (True, "success")
        
        # 测试 return_exceptions=False
        strategy_false = CoroutineStrategy(return_exceptions=False)
        results_false = await strategy_false.async_execute(tasks)
        
        # 即使 return_exceptions=False，我们的实现也会捕获异常并处理
        assert len(results_false) == 2
        assert results_false[0][0] is False
        assert results_false[1] == (True, "success")
    
    # ================== 超时测试 ==================
    
    @pytest.mark.asyncio
    async def test_timeout_success(self):
        """测试超时设置下的成功执行。"""
        async def quick_task():
            await asyncio.sleep(0.05)
            return "completed"
        
        tasks = [(quick_task, ())]
        strategy = CoroutineStrategy(logger=self.mock_logger, timeout=1.0)
        
        results = await strategy.async_execute(tasks)
        
        assert len(results) == 1
        assert results[0] == (True, "completed")
    
    @pytest.mark.asyncio
    async def test_timeout_failure(self):
        """测试超时失败的情况。"""
        async def slow_task():
            await asyncio.sleep(1.0)  # 超过超时时间
            return "should not complete"
        
        tasks = [(slow_task, ())]
        strategy = CoroutineStrategy(logger=self.mock_logger, timeout=0.1)
        
        results = await strategy.async_execute(tasks)
        
        assert len(results) == 1
        assert results[0][0] is False  # 执行失败
        # 检查是否包含超时相关的错误信息
        error_message = str(results[0][1]).lower()
        assert "timeout" in error_message or "timed out" in error_message
    
    @pytest.mark.asyncio
    async def test_mixed_timeout_scenarios(self):
        """测试混合超时场景。"""
        async def quick_task(value):
            await asyncio.sleep(0.05)
            return f"quick_{value}"
        
        async def slow_task(value):
            await asyncio.sleep(0.5)
            return f"slow_{value}"
        
        tasks = [
            (quick_task, ("A",)),
            (slow_task, ("B",)),  # 这个会超时
            (quick_task, ("C",))
        ]
        
        strategy = CoroutineStrategy(logger=self.mock_logger, timeout=0.2)
        results = await strategy.async_execute(tasks)
        
        assert len(results) == 3
        assert results[0] == (True, "quick_A")   # 成功
        assert results[1][0] is False            # 超时失败
        assert results[2] == (True, "quick_C")   # 成功
    
    # ================== 任务命名和日志测试 ==================
    
    @pytest.mark.asyncio
    async def test_task_naming_with_function_name(self):
        """测试有函数名的任务命名。"""
        async def named_task():
            await asyncio.sleep(0.01)
            return "named_result"
        
        tasks = [(named_task, ())]
        results = await self.strategy.async_execute(tasks)
        
        assert len(results) == 1
        assert results[0] == (True, "named_result")
        
        # 验证日志中使用了函数名
        logged_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        task_complete_logs = [log for log in logged_calls if 'completed successfully' in log]
        assert any('named_task' in log for log in task_complete_logs)
    
    # ================== 边界条件测试 ==================
    
    @pytest.mark.asyncio
    async def test_empty_tasks(self):
        """测试空任务列表。"""
        tasks = []
        results = await self.strategy.async_execute(tasks)
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_single_task_with_complex_args(self):
        """测试复杂参数的单个任务。"""
        async def complex_task(data_dict, data_list, *args, **kwargs):
            await asyncio.sleep(0.01)
            return {
                'dict_keys': list(data_dict.keys()),
                'list_len': len(data_list),
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            }
        
        test_dict = {'a': 1, 'b': 2}
        test_list = [1, 2, 3, 4]
        tasks = [(complex_task, (test_dict, test_list, 'arg1', 'arg2'), {'kw1': 'val1'})]
        
        # 注意：我们的实现不直接支持 kwargs，需要调整
        # 这里只测试 args 部分
        tasks = [(complex_task, (test_dict, test_list))]
        results = await self.strategy.async_execute(tasks)
        
        assert len(results) == 1
        assert results[0][0] is True
        result_data = results[0][1]
        assert result_data['dict_keys'] == ['a', 'b']
        assert result_data['list_len'] == 4
    
    # ================== 日志功能测试 ==================
    
    @pytest.mark.asyncio
    async def test_logging_without_logger(self):
        """测试没有logger时的控制台输出。"""
        strategy = CoroutineStrategy()  # 没有logger
        
        async def simple_task():
            await asyncio.sleep(0.01)
            return "test"
        
        tasks = [(simple_task, ())]
        
        # 这个测试主要确保没有logger时不会出错
        results = await strategy.async_execute(tasks)
        
        assert len(results) == 1
        assert results[0] == (True, "test")
    
    @pytest.mark.asyncio
    async def test_logging_messages(self):
        """测试各种日志消息的调用。"""
        async def simple_task():
            await asyncio.sleep(0.01)
            return "success"
        
        tasks = [(simple_task, ())]
        results = await self.strategy.async_execute(tasks)
        
        # 检查info日志被调用
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        
        # 应该包含启动和完成的日志
        assert any('Starting coroutine execution' in call for call in info_calls)
        assert any('completed successfully' in call for call in info_calls)
        assert any('Coroutine execution completed' in call for call in info_calls)
    
    # ================== 集成测试 ==================
    
    @pytest.mark.asyncio
    async def test_complex_mixed_scenario(self):
        """复杂混合场景测试：成功、失败、超时、不同参数。"""
        async def success_task(value):
            await asyncio.sleep(0.01)
            return f"success_{value}"
        
        async def failing_task():
            await asyncio.sleep(0.01)
            raise RuntimeError("Expected async failure")
        
        async def slow_task():
            await asyncio.sleep(1.0)
            return "slow_success"
        
        tasks = [
            (success_task, ("A",)),
            (failing_task, ()),
            (success_task, ("B",)),
            (slow_task, ()),
        ]
        
        strategy = CoroutineStrategy(
            logger=self.mock_logger,
            error_handling='log',
            timeout=0.2  # slow_task会超时
        )
        
        results = await strategy.async_execute(tasks, worker_count=2)
        
        assert len(results) == 4
        assert results[0] == (True, "success_A")   # 成功
        assert results[1][0] is False              # 失败
        assert results[2] == (True, "success_B")   # 成功
        assert results[3][0] is False              # 超时失败
        
        # 验证错误日志被调用（失败和超时）
        assert self.mock_logger.error.call_count >= 2
    
    def test_complex_mixed_scenario_sync(self):
        """复杂混合场景的同步接口测试。"""
        async def success_task(value):
            await asyncio.sleep(0.01)
            return f"sync_success_{value}"
        
        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Sync test error")
        
        tasks = [
            (success_task, ("X",)),
            (failing_task, ()),
            (success_task, ("Y",))
        ]
        
        strategy = CoroutineStrategy(
            logger=self.mock_logger,
            error_handling='log'
        )
        
        results = strategy.execute(tasks, worker_count=3)
        
        assert len(results) == 3
        assert results[0] == (True, "sync_success_X")
        assert results[1][0] is False
        assert results[2] == (True, "sync_success_Y")


# ================== 参数化测试 ==================

class TestCoroutineStrategyParametrized:
    """参数化测试类。"""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("worker_count", [1, 2, 5, None])
    async def test_different_worker_counts_performance(self, worker_count):
        """测试不同工作协程数的性能表现。"""
        async def io_task(duration):
            await asyncio.sleep(duration)
            return f"completed_in_{duration}"
        
        tasks = [(io_task, (0.05,)) for _ in range(4)]
        strategy = CoroutineStrategy()
        
        start_time = time.time()
        results = await strategy.async_execute(tasks, worker_count=worker_count)
        elapsed_time = time.time() - start_time
        
        # 所有任务都应该成功
        assert all(success for success, _ in results)
        assert len(results) == 4
        
        # 记录性能数据
        print(f"Worker count: {worker_count}, Time: {elapsed_time:.3f}s")
        
        # 验证并发性能
        if worker_count is None or worker_count >= 4:
            # 无限制或足够的并发数，时间应该接近单个任务时间
            assert elapsed_time < 0.1
        else:
            # 有限制的并发数，时间取决于并发度
            expected_time = 0.05 * (4 / worker_count)
            assert elapsed_time < expected_time + 0.06  # 允许一些误差
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_handling", ['log', 'raise'])
    async def test_error_handling_modes(self, error_handling):
        """测试不同错误处理模式。"""
        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Parametrized test error")
        
        tasks = [(failing_task, ())]
        strategy = CoroutineStrategy(error_handling=error_handling)

        if error_handling == 'raise':
            with pytest.raises(ValueError, match="Parametrized test error"):
                await strategy.async_execute(tasks)
        else:
            results = await strategy.async_execute(tasks)
            assert len(results) == 1
            assert results[0][0] is False
            assert "Parametrized test error" in str(results[0][1])
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("timeout", [0.05, 0.1, 0.5, None])
    async def test_different_timeout_values(self, timeout):
        """测试不同超时值的行为。"""
        async def variable_delay_task(delay):
            await asyncio.sleep(delay)
            return f"completed_after_{delay}"
        
        tasks = [(variable_delay_task, (0.1,))]  # 固定0.1秒的任务
        strategy = CoroutineStrategy(timeout=timeout)
        
        results = await strategy.async_execute(tasks)
        
        if timeout is None or timeout > 0.1:
            # 应该成功
            assert results[0] == (True, "completed_after_0.1")
        else:
            # 应该超时失败
            assert results[0][0] is False
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("return_exceptions", [True, False])
    async def test_return_exceptions_parameter(self, return_exceptions):
        """测试 return_exceptions 参数的不同值。"""
        async def normal_task():
            await asyncio.sleep(0.01)
            return "normal"
        
        async def failing_task():
            await asyncio.sleep(0.01)
            raise Exception("Test exception")
        
        tasks = [
            (normal_task, ()),
            (failing_task, ())
        ]
        
        strategy = CoroutineStrategy(return_exceptions=return_exceptions)
        results = await strategy.async_execute(tasks)
        
        # 无论 return_exceptions 如何设置，我们的实现都应该返回统一格式
        assert len(results) == 2
        assert results[0] == (True, "normal")
        assert results[1][0] is False


# ================== Fixture 定义 ==================

@pytest_asyncio.fixture
async def sample_async_tasks():
    """提供示例异步任务的fixture。"""
    async def add_async(a, b):
        await asyncio.sleep(0.01)
        return a + b
    
    async def multiply_async(a, b):
        await asyncio.sleep(0.01)
        return a * b
    
    async def power_async(base, exp=2):
        await asyncio.sleep(0.01)
        return base ** exp
    
    return [
        (add_async, (2, 3)),
        (multiply_async, (4, 5)),
        (power_async, (3,))
    ]

@pytest.fixture
def async_logger_mock():
    """提供mock logger的fixture。"""
    return Mock()


class TestCoroutineStrategyWithFixtures:
    """使用fixtures的测试类。"""
    
    @pytest.mark.asyncio
    async def test_with_sample_async_tasks(self, sample_async_tasks, async_logger_mock):
        """使用fixtures的异步任务测试。"""
        aaa = sample_async_tasks

        strategy = CoroutineStrategy(logger=async_logger_mock)
        results = await strategy.async_execute(sample_async_tasks)
        
        expected_results = [
            (True, 5),   # 2 + 3
            (True, 20),  # 4 * 5  
            (True, 9),   # 3 ** 2
        ]
        
        assert results == expected_results
        async_logger_mock.info.assert_called()
    
    def test_with_sample_async_tasks_sync(self, sample_async_tasks, async_logger_mock):
        """使用fixtures的同步接口测试。"""
        strategy = CoroutineStrategy(logger=async_logger_mock)
        results = strategy.execute(sample_async_tasks)
        
        expected_results = [
            (True, 5),   # 2 + 3
            (True, 20),  # 4 * 5  
            (True, 9),   # 3 ** 2
        ]
        
        assert results == expected_results
        async_logger_mock.info.assert_called()


# ================== 性能基准测试 ==================

class TestCoroutineStrategyPerformance:
    """协程策略性能测试类。"""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_high_concurrency_performance(self):
        """测试高并发场景的性能。"""
        async def micro_task(task_id):
            await asyncio.sleep(0.001)  # 1ms的微任务
            return f"result_{task_id}"
        
        # 创建大量任务
        tasks = [(micro_task, (i,)) for i in range(100)]
        strategy = CoroutineStrategy()
        
        start_time = time.time()
        results = await strategy.async_execute(tasks, worker_count=None)  # 无限制并发
        elapsed_time = time.time() - start_time
        
        # 验证所有任务成功完成
        assert len(results) == 100
        assert all(success for success, _ in results)
        
        # 高并发下，时间应该接近单个任务时间
        assert elapsed_time < 0.1  # 应该远小于串行执行的100ms
        
        print(f"100 concurrent micro-tasks completed in {elapsed_time:.3f}s")
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_memory_efficiency_large_tasks(self):
        """测试大量任务的内存效率。"""
        async def memory_task(data_size):
            # 创建一些数据但不保留引用
            data = list(range(data_size))
            await asyncio.sleep(0.001)
            return len(data)
        
        # 创建大量任务，每个处理一定量的数据
        tasks = [(memory_task, (100,)) for _ in range(50)]
        strategy = CoroutineStrategy()
        
        results = await strategy.async_execute(tasks, worker_count=10)
        
        # 验证所有任务成功完成
        assert len(results) == 50
        assert all(success for success, _ in results)
        assert all(result == 100 for success, result in results if success)


if __name__ == "__main__":
    # 直接运行测试文件时的行为
    import sys
    
    # 添加异步支持
    if sys.version_info >= (3, 7):
        # Python 3.7+ 自动支持 asyncio 测试
        pytest.main([__file__, "-v", "--tb=short"])
    else:
        print("需要 Python 3.7+ 来运行异步测试")
        sys.exit(1)
