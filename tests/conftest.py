# tests/conftest.py
import pytest
import sys
import os

# -------------------------
# 自动添加项目根目录到 Python 搜索路径
# -------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# -------------------------
# Pytest 插件声明（如果需要可扩展）
# -------------------------
pytest_plugins = []

# -------------------------
# 自定义 marker 注册
# -------------------------
def pytest_configure(config):
    """注册自定义 pytest marker"""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (skip with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests"
    )

# -------------------------
# 自动给测试打 marker
# -------------------------
def pytest_collection_modifyitems(config, items):
    """在测试收集后修改测试 item"""
    for item in items:
        # 名称包含 "performance" 自动打 slow
        if "performance" in item.name:
            item.add_marker(pytest.mark.slow)

        # 名称包含 "complex" 或 "mixed_scenario" 打 integration
        if "complex" in item.name or "mixed_scenario" in item.name:
            item.add_marker(pytest.mark.integration)
