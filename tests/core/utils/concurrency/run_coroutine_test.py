#!/usr/bin/env python3
"""
协程策略测试运行脚本
用于验证 CoroutineStrategy 的测试是否正常工作
"""

import sys
import os
import asyncio
from time import sleep

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.utils.concurrency.coroutine_strategy import CoroutineStrategy

async def simple_task(x, y):
    await asyncio.sleep(0.01)
    return x + y

async def multiply_task(x, y):
    await asyncio.sleep(0.02)
    return x * y
    
def run_basic_test1():
    """运行基础功能测试。"""
    print("🧪 开始基础协程策略测试...")
    
    # 创建策略实例
    strategy = CoroutineStrategy()
    
    # 定义测试任务
    # def simple_task(x, y):
    #     sleep(0.01)
    #     return x + y
    
    # def multiply_task(x, y):
    #     sleep(0.02)
    #     return x * y
    
    # 测试任务列表
    tasks = [
        (simple_task, (2, 3)),
        (multiply_task, (4, 5))
    ]
    
    
    # 验证结果
    expected = [(True, 5), (True, 20)]
    
    # 测试同步接口
    print("📋 执行同步接口测试...")
    sync_results = strategy.execute(tasks)
    
    assert sync_results == expected, f"期望 {expected}, 实际 {sync_results}"
    print("✅ 同步接口测试通过!")
    
async def run_basic_test():
    """运行基础功能测试。"""
    print("🧪 开始基础协程策略测试...")
    
    # 创建策略实例
    strategy = CoroutineStrategy()
    
    # 定义测试任务
    async def simple_task(x, y):
        await asyncio.sleep(0.01)
        return x + y
    
    async def multiply_task(x, y):
        await asyncio.sleep(0.02)
        return x * y
    
    # 测试任务列表
    tasks = [
        (simple_task, (2, 3)),
        (multiply_task, (4, 5))
    ]
    
    # 执行测试
    print("📋 执行异步任务...")
    results = await strategy.async_execute(tasks)
    
    # 验证结果
    expected = [(True, 5), (True, 20)]
    assert results == expected, f"期望 {expected}, 实际 {results}"
    
    print("✅ 异步执行测试通过!")
    
    # 测试同步接口
    print("📋 执行同步接口测试...")
    sync_results = await strategy.execute(tasks)
    
    assert sync_results == expected, f"期望 {expected}, 实际 {sync_results}"
    print("✅ 同步接口测试通过!")


async def run_concurrency_test():
    """运行并发控制测试。"""
    print("\n🚀 开始并发控制测试...")
    
    strategy = CoroutineStrategy()
    
    # 跟踪并发任务数
    active_tasks = 0
    max_concurrent = 0
    
    async def tracking_task(task_id):
        nonlocal active_tasks, max_concurrent
        active_tasks += 1
        max_concurrent = max(max_concurrent, active_tasks)
        
        await asyncio.sleep(0.1)  # 模拟工作
        
        active_tasks -= 1
        return f"task_{task_id}_done"
    
    # 创建5个任务，限制并发数为2
    tasks = [(tracking_task, (i,)) for i in range(5)]
    
    print("📋 执行并发控制测试 (最大并发数: 2)...")
    results = await strategy.async_execute(tasks, worker_count=2)
    
    # 验证结果
    assert len(results) == 5
    assert all(success for success, _ in results)
    assert max_concurrent <= 2, f"并发数超限: {max_concurrent}"
    
    print(f"✅ 并发控制测试通过! 最大并发数: {max_concurrent}")


async def run_error_handling_test():
    """运行错误处理测试。"""
    print("\n🛡️ 开始错误处理测试...")
    
    strategy = CoroutineStrategy(error_handling='log')
    
    async def success_task():
        await asyncio.sleep(0.01)
        return "success"
    
    async def failing_task():
        await asyncio.sleep(0.01)
        raise ValueError("测试异常")
    
    tasks = [
        (success_task, ()),
        (failing_task, ()),
        (success_task, ())
    ]
    
    print("📋 执行混合成功/失败任务...")
    results = await strategy.async_execute(tasks)
    
    # 验证结果
    assert len(results) == 3
    assert results[0] == (True, "success")
    assert results[1][0] is False  # 失败任务
    assert "测试异常" in str(results[1][1])
    assert results[2] == (True, "success")
    
    print("✅ 错误处理测试通过!")


async def run_timeout_test():
    """运行超时测试。"""
    print("\n⏱️ 开始超时测试...")
    
    strategy = CoroutineStrategy(timeout=0.1)
    
    async def quick_task():
        await asyncio.sleep(0.05)
        return "quick"
    
    async def slow_task():
        await asyncio.sleep(0.2)  # 超过超时时间
        return "slow"
    
    tasks = [
        (quick_task, ()),
        (slow_task, ())
    ]
    
    print("📋 执行超时测试...")
    results = await strategy.async_execute(tasks)
    
    # 验证结果
    assert len(results) == 2
    assert results[0] == (True, "quick")
    assert results[1][0] is False  # 超时失败
    
    print("✅ 超时测试通过!")


async def run_performance_test():
    """运行性能测试。"""
    print("\n⚡ 开始性能测试...")
    
    strategy = CoroutineStrategy()
    
    async def io_task(duration):
        await asyncio.sleep(duration)
        return f"completed_in_{duration}"
    
    # 创建多个IO任务
    tasks = [(io_task, (0.05,)) for _ in range(10)]
    
    import time
    start_time = time.time()
    
    print("📋 执行10个并发IO任务...")
    results = await strategy.async_execute(tasks)
    
    elapsed_time = time.time() - start_time
    
    # 验证结果
    assert len(results) == 10
    assert all(success for success, _ in results)
    
    # 并发执行应该比串行快很多
    assert elapsed_time < 0.2, f"并发执行时间过长: {elapsed_time:.3f}s"
    
    print(f"✅ 性能测试通过! 10个任务并发完成时间: {elapsed_time:.3f}s")


async def main():
    """主测试函数。"""
    print("🚀 开始 CoroutineStrategy 集成测试")
    print("=" * 50)
    
    try:
        await run_basic_test()
        await run_concurrency_test()
        await run_error_handling_test()
        await run_timeout_test()
        await run_performance_test()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试通过!")
        print("CoroutineStrategy 工作正常，可以进行完整的 pytest 测试")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    
    run_basic_test1()
    
    # 运行测试
    # success = asyncio.run(main())
    # sys.exit(0 if success else 1)
