#!/usr/bin/env python3
"""
并发策略完整测试套件
用于验证所有并发策略（Thread, Process, Coroutine）的功能
"""

import sys
import os
import time
import multiprocessing
import asyncio

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.utils.concurrency import ThreadPoolStrategy, ProcessPoolStrategy, CoroutineStrategy, ConcurrencyContext


# 全局函数用于进程池测试
def cpu_task(n):
    total = 0
    for i in range(n):
        total += i
    return total

def add_task(x, y):
    return x + y


class ConcurrencyTestSuite:
    """并发策略测试套件。"""
    
    def __init__(self):
        self.results = {
            'thread': {'passed': 0, 'failed': 0, 'time': 0},
            'process': {'passed': 0, 'failed': 0, 'time': 0},
            'coroutine': {'passed': 0, 'failed': 0, 'time': 0}
        }
    
    def run_thread_tests(self):
        """运行线程池策略测试。"""
        print("🧵 开始线程池策略测试...")
        start_time = time.time()
        
        try:
            strategy = ThreadPoolStrategy()
            
            # 基础功能测试
            def io_task(duration, value):
                time.sleep(duration)
                return value
            
            tasks = [(io_task, (0.1, f"task_{i}")) for i in range(3)]
            results = strategy.execute(tasks, worker_count=2)
            
            assert len(results) == 3
            assert all(success for success, _ in results)
            
            self.results['thread']['passed'] += 1
            print("  ✅ 线程池基础功能测试通过")
            
            # 错误处理测试
            def failing_task():
                raise ValueError("线程测试异常")
            
            mixed_tasks = [
                (io_task, (0.01, "success")),
                (failing_task, ())
            ]
            
            results = strategy.execute(mixed_tasks, worker_count=2)
            assert len(results) == 2
            assert results[0] == (True, "success")
            assert results[1][0] is False
            
            self.results['thread']['passed'] += 1
            print("  ✅ 线程池错误处理测试通过")
            
        except Exception as e:
            self.results['thread']['failed'] += 1
            print(f"  ❌ 线程池测试失败: {e}")
        
        finally:
            self.results['thread']['time'] = time.time() - start_time
    
    def run_process_tests(self):
        """运行进程池策略测试。"""
        print("\n🔄 开始进程池策略测试...")
        start_time = time.time()
        
        try:
            strategy = ProcessPoolStrategy()
            
            # CPU密集型任务测试
            tasks = [(cpu_task, (1000,)) for _ in range(3)]
            results = strategy.execute(tasks, worker_count=2)
            
            assert len(results) == 3
            assert all(success for success, _ in results)
            
            self.results['process']['passed'] += 1
            print("  ✅ 进程池CPU任务测试通过")
            
            # 基础功能测试
            basic_tasks = [(add_task, (i, i+1)) for i in range(3)]
            results = strategy.execute(basic_tasks, worker_count=2)
            
            expected = [(True, 1), (True, 3), (True, 5)]
            assert results == expected
            
            self.results['process']['passed'] += 1
            print("  ✅ 进程池基础功能测试通过")
            
        except Exception as e:
            self.results['process']['failed'] += 1
            print(f"  ❌ 进程池测试失败: {e}")
        
        finally:
            self.results['process']['time'] = time.time() - start_time
    
    async def run_coroutine_tests_async(self):
        """运行协程策略测试（异步部分）。"""
        try:
            strategy = CoroutineStrategy()
            
            # 基础异步任务测试
            async def async_task(x, y):
                await asyncio.sleep(0.01)
                return x + y
            
            tasks = [(async_task, (i, i+1)) for i in range(3)]
            results = await strategy.async_execute(tasks, worker_count=2)
            
            expected = [(True, 1), (True, 3), (True, 5)]
            assert results == expected
            
            self.results['coroutine']['passed'] += 1
            print("  ✅ 协程基础功能测试通过")
            
            # 并发控制测试
            async def delayed_task(delay, value):
                await asyncio.sleep(delay)
                return value
            
            concurrent_tasks = [(delayed_task, (0.05, f"task_{i}")) for i in range(5)]
            start = time.time()
            results = await strategy.async_execute(concurrent_tasks, worker_count=3)
            elapsed = time.time() - start
            
            assert len(results) == 5
            assert all(success for success, _ in results)
            assert elapsed < 0.2  # 应该比串行执行快
            
            self.results['coroutine']['passed'] += 1
            print("  ✅ 协程并发控制测试通过")
            
            # 同步接口测试
            sync_results = strategy.execute(tasks, worker_count=2)
            assert sync_results == expected
            
            self.results['coroutine']['passed'] += 1
            print("  ✅ 协程同步接口测试通过")
            
        except Exception as e:
            self.results['coroutine']['failed'] += 1
            print(f"  ❌ 协程测试失败: {e}")
    
    def run_coroutine_tests(self):
        """运行协程策略测试。"""
        print("\n⚡ 开始协程策略测试...")
        start_time = time.time()
        
        try:
            asyncio.run(self.run_coroutine_tests_async())
        except Exception as e:
            self.results['coroutine']['failed'] += 1
            print(f"  ❌ 协程测试运行失败: {e}")
        finally:
            self.results['coroutine']['time'] = time.time() - start_time
    
    def run_context_integration_tests(self):
        """运行上下文集成测试。"""
        print("\n🔗 开始上下文集成测试...")
        
        try:
            # 测试策略切换
            context = ConcurrencyContext()
            context.set_default_worker_count(2)
            
            # 线程策略
            context.set_strategy(ThreadPoolStrategy())
            
            def simple_task(x):
                time.sleep(0.01)
                return x * 2
            
            tasks = [(simple_task, (i,)) for i in range(3)]
            results = context.execute_tasks(tasks)
            
            assert len(results) == 3
            assert all(success for success, _ in results)
            
            print("  ✅ 上下文策略切换测试通过")
            
            # 测试协程策略切换
            async def async_simple_task(x):
                await asyncio.sleep(0.01)
                return x * 3
            
            context.set_strategy(CoroutineStrategy())
            async_tasks = [(async_simple_task, (i,)) for i in range(3)]
            async_results = context.execute_tasks(async_tasks)
            
            assert len(async_results) == 3
            assert all(success for success, _ in async_results)
            
            print("  ✅ 上下文协程策略测试通过")
            
        except Exception as e:
            print(f"  ❌ 上下文集成测试失败: {e}")
    
    def run_performance_comparison(self):
        """运行性能对比测试。"""
        print("\n📊 开始性能对比测试...")
        
        # IO密集型任务对比（线程 vs 协程）
        def io_bound_task(duration):
            time.sleep(duration)
            return "io_done"
        
        async def async_io_task(duration):
            await asyncio.sleep(duration)
            return "async_io_done"
        
        # CPU密集型任务对比（线程 vs 进程）
        tasks_count = 4
        io_duration = 0.05
        
        print(f"  测试场景: {tasks_count}个任务，每个IO耗时{io_duration}s")
        
        # 线程池测试
        thread_strategy = ThreadPoolStrategy()
        io_tasks = [(io_bound_task, (io_duration,)) for _ in range(tasks_count)]
        
        start_time = time.time()
        thread_results = thread_strategy.execute(io_tasks, worker_count=2)
        thread_time = time.time() - start_time
        
        # 协程测试
        coroutine_strategy = CoroutineStrategy()
        async_tasks = [(async_io_task, (io_duration,)) for _ in range(tasks_count)]
        
        start_time = time.time()
        coroutine_results = coroutine_strategy.execute(async_tasks, worker_count=2)
        coroutine_time = time.time() - start_time
        
        # 进程池测试（使用CPU任务）
        process_strategy = ProcessPoolStrategy()
        cpu_tasks = [(cpu_task, (1000,)) for _ in range(tasks_count)]
        
        start_time = time.time()
        process_results = process_strategy.execute(cpu_tasks, worker_count=2)
        process_time = time.time() - start_time
        
        print(f"  线程池 IO 任务: {thread_time:.3f}s")
        print(f"  协程   IO 任务: {coroutine_time:.3f}s")
        print(f"  进程池 CPU任务: {process_time:.3f}s")
        
        # 验证结果正确性
        assert all(success for success, _ in thread_results)
        assert all(success for success, _ in coroutine_results)
        assert all(success for success, _ in process_results)
        
        print("  ✅ 性能对比测试通过")
    
    def print_summary(self):
        """打印测试总结。"""
        print("\n" + "=" * 60)
        print("📋 测试总结报告")
        print("=" * 60)
        
        total_passed = 0
        total_failed = 0
        total_time = 0
        
        for strategy_name, stats in self.results.items():
            passed = stats['passed']
            failed = stats['failed']
            exec_time = stats['time']
            
            total_passed += passed
            total_failed += failed
            total_time += exec_time
            
            status = "✅ 通过" if failed == 0 else "❌ 部分失败"
            print(f"{strategy_name.capitalize():>10}: {passed}通过 {failed}失败 ({exec_time:.3f}s) {status}")
        
        print("-" * 60)
        print(f"{'总计':>10}: {total_passed}通过 {total_failed}失败 ({total_time:.3f}s)")
        
        if total_failed == 0:
            print("\n🎉 所有并发策略测试通过！")
            print("✨ 可以进行完整的 pytest 测试套件")
        else:
            print(f"\n⚠️ 有 {total_failed} 个测试失败，请检查相关问题")
        
        return total_failed == 0


def main():
    """主测试入口。"""
    print("🚀 并发策略完整测试套件")
    print("=" * 60)
    print("测试内容:")
    print("  🧵 ThreadPoolStrategy - 线程池并发策略")
    print("  🔄 ProcessPoolStrategy - 进程池并发策略") 
    print("  ⚡ CoroutineStrategy - 协程并发策略")
    print("  🔗 ConcurrencyContext - 上下文管理")
    print("  📊 性能对比测试")
    print("=" * 60)
    
    # 设置多进程启动方法（Windows需要）
    if os.name == 'nt':
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except RuntimeError:
            pass  # 已经设置过了
    
    # 创建测试套件并运行
    test_suite = ConcurrencyTestSuite()
    
    try:
        test_suite.run_thread_tests()
        test_suite.run_process_tests()
        test_suite.run_coroutine_tests()
        test_suite.run_context_integration_tests()
        test_suite.run_performance_comparison()
        
        # 打印总结并返回结果
        success = test_suite.print_summary()
        return success
        
    except KeyboardInterrupt:
        print("\n\n⏹️ 测试被用户中断")
        return False
    except Exception as e:
        print(f"\n\n💥 测试套件运行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
