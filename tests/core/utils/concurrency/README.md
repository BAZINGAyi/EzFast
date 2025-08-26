# 并发策略测试套件

这个目录包含了对 `core.utils.concurrency` 模块中所有并发策略的完整测试套件。

## 📁 文件结构

```
tests/core/utils/concurrency/
├── __init__.py                    # 包初始化文件
├── conftest.py                    # Pytest 配置文件
├── README.md                      # 本文件
├── test_thread_strategy.py        # 线程池策略完整测试
├── test_process_strategy.py       # 进程池策略完整测试  
├── test_coroutine_strategy.py     # 协程策略完整测试
├── run_thread_test.py             # 线程池策略快速验证
├── run_process_test.py            # 进程池策略快速验证
├── run_coroutine_test.py          # 协程策略快速验证
└── run_all_tests.py               # 全策略集成测试
```

## 🚀 快速开始

### 1. 快速验证（推荐开发时使用）

```bash
# 验证所有策略基本功能
python tests/core/utils/concurrency/run_all_tests.py

# 单独验证某个策略
python tests/core/utils/concurrency/run_thread_test.py
python tests/core/utils/concurrency/run_process_test.py  
python tests/core/utils/concurrency/run_coroutine_test.py
```

### 2. 完整测试（推荐提交前使用）

```bash
# 运行所有测试
pytest tests/core/utils/concurrency/ -v

# 运行特定策略的完整测试
pytest tests/core/utils/concurrency/test_thread_strategy.py -v
pytest tests/core/utils/concurrency/test_process_strategy.py -v
pytest tests/core/utils/concurrency/test_coroutine_strategy.py -v
```

### 3. 带覆盖率的测试

```bash
# 需要先安装 pytest-cov
pip install pytest-cov

# 运行带覆盖率报告的测试
pytest tests/core/utils/concurrency/ --cov=core.utils.concurrency --cov-report=html
```

## 📋 测试内容

### ThreadPoolStrategy 测试
- ✅ 基础功能测试（单任务、多任务）
- ✅ 并发执行性能测试
- ✅ 错误处理测试（log/raise 模式）
- ✅ 超时控制测试
- ✅ 线程池配置测试（线程名前缀、工作线程数）
- ✅ 结果顺序保持测试
- ✅ 边界条件测试（空任务、零工作线程等）
- ✅ 日志功能测试
- ✅ 复杂混合场景测试
- ✅ 参数化测试（不同参数组合）

### ProcessPoolStrategy 测试
- ✅ 基础功能测试
- ✅ CPU密集型任务测试
- ✅ 进程隔离测试
- ✅ 错误处理测试
- ✅ 超时控制测试
- ✅ 进程池配置测试（max_tasks_per_child等）
- ✅ 结果顺序保持测试
- ✅ 内存密集型任务测试
- ✅ 大量任务处理测试
- ✅ 平台特定行为测试（Windows/Unix）

### CoroutineStrategy 测试
- ✅ 异步任务执行测试
- ✅ 并发控制测试（信号量限制）
- ✅ 同步接口测试
- ✅ 错误处理测试
- ✅ 超时控制测试
- ✅ return_exceptions 参数测试
- ✅ 任务命名和日志测试
- ✅ 高并发性能测试
- ✅ 内存效率测试

### 集成测试
- ✅ ConcurrencyContext 策略切换
- ✅ 全局配置管理
- ✅ 性能对比测试
- ✅ 端到端功能验证

## 🎯 测试标记

使用 pytest 标记来分类运行测试：

```bash
# 只运行快速测试（排除慢速测试）
pytest tests/core/utils/concurrency/ -m "not slow"

# 只运行集成测试
pytest tests/core/utils/concurrency/ -m "integration"

# 只运行参数化测试
pytest tests/core/utils/concurrency/ -k "parametrize"
```

## 🔧 依赖要求

```bash
# 基础测试依赖
pip install pytest

# 异步测试支持
pip install pytest-asyncio

# 覆盖率报告（可选）
pip install pytest-cov

# Mock 支持（Python 3.3+ 内置）
# unittest.mock
```

## 📊 性能基准

运行性能基准测试：

```bash
python tests/core/utils/concurrency/run_all_tests.py
```

示例输出：
```
📊 开始性能对比测试...
  测试场景: 4个任务，每个IO耗时0.05s
  线程池 IO 任务: 0.103s
  协程   IO 任务: 0.052s  
  进程池 CPU任务: 0.234s
  ✅ 性能对比测试通过
```

## 🐛 故障排除

### 常见问题

1. **进程池测试在 Windows 上失败**
   ```python
   # 确保设置了正确的启动方法
   import multiprocessing
   multiprocessing.set_start_method('spawn', force=True)
   ```

2. **协程测试失败**
   ```bash
   # 确保安装了 pytest-asyncio
   pip install pytest-asyncio
   ```

3. **导入错误**
   ```bash
   # 确保项目根目录在 Python 路径中
   export PYTHONPATH=$PYTHONPATH:/path/to/project
   ```

### 调试技巧

1. **查看详细输出**
   ```bash
   pytest tests/core/utils/concurrency/ -v -s
   ```

2. **只运行失败的测试**
   ```bash
   pytest tests/core/utils/concurrency/ --lf
   ```

3. **进入调试模式**
   ```bash
   pytest tests/core/utils/concurrency/ --pdb
   ```

## 📈 扩展测试

### 添加新的测试用例

1. **基础测试**: 在对应的 `test_*_strategy.py` 文件中添加新方法
2. **快速验证**: 在对应的 `run_*_test.py` 文件中添加新函数
3. **集成测试**: 在 `run_all_tests.py` 中添加新的测试场景

### 测试模板

```python
def test_new_feature(self):
    """测试新功能。"""
    # 1. 准备测试数据
    tasks = [(your_task_function, (args,))]
    
    # 2. 执行测试
    strategy = YourStrategy(your_config)
    results = strategy.execute(tasks, worker_count=2)
    
    # 3. 验证结果
    assert len(results) == 1
    assert results[0] == (True, expected_result)
    
    # 4. 验证副作用（如日志）
    # self.mock_logger.info.assert_called()
```

## 📚 相关文档

- [并发策略设计文档](../../../../core/utils/concurrency/README.md)
- [ThreadPoolStrategy 设计思路](../../../../docs/concurrency/thread_strategy_design.md)
- [性能测试报告](../../../../docs/concurrency/performance_report.md)

---

💡 **提示**: 建议在开发过程中先运行快速验证脚本，确认基本功能正常后再运行完整的 pytest 测试套件。这样可以提高开发效率并快速定位问题。
