#!/usr/bin/env python3
"""
进程池策略测试运行脚本
用于验证 ProcessPoolStrategy 的测试是否正常工作
"""

import sys
import os
import time
import multiprocessing

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.utils.concurrency.process_strategy import ProcessPoolStrategy


# 全局函数，用于进程池测试（必须在模块级别定义才能被pickle）
def simple_add_task(x, y):
    """简单的加法任务。"""
    return x + y

def cpu_task(n):
    """CPU密集型任务。"""
    total = 0
    for i in range(n):
        total += i * i
    return total

def slow_task(duration, value):
    """耗时任务。"""
    time.sleep(duration)
    return value

def slow1_task(duration, value):
    """耗时任务。"""
    time.sleep(duration)
    return value
    return value

def failing_task():
    """会失败的任务。"""
    raise ValueError("测试异常")

def process_info_task():
    """获取进程信息。"""
    return {
        'pid': os.getpid(),
        'process_name': multiprocessing.current_process().name
    }


def run_basic_test():
    """运行基础功能测试。"""
    print("🧪 开始基础进程池策略测试...")
    
    # 创建策略实例
    strategy = ProcessPoolStrategy()
    
    # 测试任务列表
    tasks = [
        (simple_add_task, (2, 3)),
        (simple_add_task, (4, 5))
    ]
    
    # 执行测试
    print("📋 执行基础任务...")
    results = strategy.execute(tasks, worker_count=2)
    
    # 验证结果
    expected = [(True, 5), (True, 9)]
    assert results == expected, f"期望 {expected}, 实际 {results}"
    
    print("✅ 基础任务执行测试通过!")


def run_cpu_intensive_test():
    """运行CPU密集型任务测试。"""
    print("\n🚀 开始CPU密集型任务测试...")
    
    strategy = ProcessPoolStrategy()
    
    # 创建CPU密集型任务
    tasks = [(cpu_task, (10000,)) for _ in range(4)]
    
    # 测试单进程执行
    print("📋 执行单进程CPU任务...")
    start_time = time.time()
    results_single = strategy.execute(tasks, worker_count=1)
    single_time = time.time() - start_time
    
    # 测试多进程执行
    print("📋 执行多进程CPU任务...")
    start_time = time.time()
    results_multi = strategy.execute(tasks, worker_count=2)
    multi_time = time.time() - start_time
    
    # 验证结果
    assert len(results_single) == 4
    assert len(results_multi) == 4
    assert all(success for success, _ in results_single)
    assert all(success for success, _ in results_multi)
    
    print(f"✅ CPU密集型测试通过!")
    print(f"   单进程时间: {single_time:.3f}s")
    print(f"   多进程时间: {multi_time:.3f}s")
    
    if multi_time < single_time:
        print(f"   🎉 多进程提升了 {((single_time - multi_time) / single_time * 100):.1f}% 的性能!")


def run_process_isolation_test():
    """运行进程隔离测试。"""
    print("\n🔒 开始进程隔离测试...")
    
    strategy = ProcessPoolStrategy()
    
    # 创建获取进程信息的任务
    tasks = [(process_info_task, ()) for _ in range(5)]
    
    print("📋 执行进程信息获取任务...")
    results = strategy.execute(tasks, worker_count=3)
    
    # 验证结果
    assert len(results) == 5
    assert all(success for success, _ in results)
    
    # 提取进程信息
    process_infos = [result for success, result in results if success]
    pids = [info['pid'] for info in process_infos]
    unique_pids = set(pids)
    
    print(f"✅ 进程隔离测试通过!")
    print(f"   使用了 {len(unique_pids)} 个不同的进程")
    print(f"   进程PID: {sorted(unique_pids)}")


def run_error_handling_test():
    """运行错误处理测试。"""
    print("\n🛡️ 开始错误处理测试...")
    
    strategy = ProcessPoolStrategy(error_handling='log')
    
    tasks = [
        (simple_add_task, (1, 2)),  # 成功
        (failing_task, ()),         # 失败
        (simple_add_task, (3, 4))   # 成功
    ]
    
    print("📋 执行混合成功/失败任务...")
    results = strategy.execute(tasks, worker_count=2)
    
    # 验证结果
    assert len(results) == 3
    assert results[0] == (True, 3)
    assert results[1][0] is False  # 失败任务
    assert "测试异常" in str(results[1][1])
    assert results[2] == (True, 7)
    
    print("✅ 错误处理测试通过!")


def run_timeout_test():
    """运行超时测试。"""
    print("\n⏱️ 开始超时测试...")
    
    strategy = ProcessPoolStrategy(timeout=1)
    
    tasks = [
        (slow_task, (0.5, "quick")),  # 快任务
        (slow_task, (1.5, "wu"))    # 慢任务（会超时）
    ]
    
    print("📋 执行超时测试...")
    results = strategy.execute(tasks, worker_count=2)
    
    # 验证结果
    print(results)
    assert len(results) == 2
    assert results[0] == (True, "quick")
    assert results[1][0] is False  # 超时失败
    
    print("✅ 超时测试通过!")


def run_performance_benchmark():
    """运行性能基准测试。"""
    print("\n⚡ 开始性能基准测试...")
    
    strategy = ProcessPoolStrategy()
    
    # 创建大量CPU任务
    tasks = [(cpu_task, (5000,)) for _ in range(8)]
    
    print("📋 执行性能基准测试...")
    start_time = time.time()
    results = strategy.execute(tasks, worker_count=4)
    elapsed_time = time.time() - start_time
    
    # 验证结果
    assert len(results) == 8
    assert all(success for success, _ in results)
    
    print(f"✅ 性能基准测试通过!")
    print(f"   8个CPU任务在 {elapsed_time:.3f}s 内完成")
    print(f"   平均每个任务: {elapsed_time/8:.3f}s")


def main():
    """主测试函数。"""
    print("🚀 开始 ProcessPoolStrategy 集成测试")
    print("=" * 50)
    
    try:
        # run_basic_test()
        # run_cpu_intensive_test()
        # run_process_isolation_test()
        # run_error_handling_test()
        run_timeout_test()
        run_performance_benchmark()
        
        print("\n" + "=" * 50)
        print("🎉 所有测试通过!")
        print("ProcessPoolStrategy 工作正常，可以进行完整的 pytest 测试")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # 设置多进程启动方法（Windows需要）
    if os.name == 'nt':
        multiprocessing.set_start_method('spawn', force=True)
    
    # 运行测试
    success = main()
    sys.exit(0 if success else 1)
