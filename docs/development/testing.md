## Testing Guidelines

### Unit Tests

```bash
# Test specific module
pytest tests/unit/test_tools.py

# Test with verbose output
pytest tests/unit/test_tools.py -v

# Test specific function
pytest tests/unit/test_tools.py::test_bash_tool_execute
```

### Integration Tests

```bash
# Requires API key
export ANTHROPIC_API_KEY=sk-ant-xxx
pytest tests/integration/

# Skip slow tests
pytest tests/integration/ -m "not slow"
```

### Writing Tests

```python
# tests/unit/test_custom_tool.py

import pytest
from orchestrator.tools.base import ToolResult
from user_extensions.tools.my_tools import MyTool

@pytest.mark.asyncio
async def test_my_tool_success():
    tool = MyTool()
    result = await tool.execute(input="test")

    assert result.success is True
    assert result.data == "expected output"

@pytest.mark.asyncio
async def test_my_tool_failure():
    tool = MyTool()
    result = await tool.execute(input="invalid")

    assert result.success is False
    assert "error" in result.error.lower()
```

---

