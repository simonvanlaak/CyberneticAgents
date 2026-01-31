# Cybernetic Agents Testing Framework

This directory contains the comprehensive testing framework for the Cybernetic Agents system. The test structure mirrors the source code structure for better organization and maintainability.

## Test Structure

```
tests/
├── __init__.py                # Test package initialization
├── conftest.py               # Pytest configuration and fixtures
├── README.md                 # This file
├── fixtures/                 # Test fixtures and utilities
│   ├── __init__.py
│   ├── test_data.py          # Test data generators
│   └── mock_objects.py       # Mock objects for testing
├── rbac/                     # RBAC component tests
│   ├── __init__.py
│   ├── test_enforcer.py      # Casbin enforcer tests
│   ├── test_namespace.py     # Namespace extraction tests
│   └── test_permissions.py   # Permission checking tests
├── tools/                    # Tools component tests
│   ├── __init__.py
│   ├── test_delegate.py      # Delegate tool tests
│   ├── test_escalate.py      # Escalate tool tests
│   ├── test_rbac_helper.py   # RBAC tool helper tests
│   └── test_system_create.py # System creation tool tests
├── test_runtime.py          # Runtime tests
├── test_vsm_agent.py        # VSM agent tests
└── test_registry.py          # Agent registry tests
```

## Testing Philosophy

### Test-Driven Development (TDD)

This project follows strict TDD principles:

1. **Write tests first** - Before implementing any feature
2. **Run tests frequently** - Ensure all tests pass before committing
3. **Test coverage** - Minimum 80% coverage required for all new code
4. **Test organization** - All test files must mirror the source structure

### Test Types

1. **Unit Tests** - Test individual components in isolation
2. **Integration Tests** - Test interactions between components
3. **End-to-End Tests** - Test complete system workflows
4. **Regression Tests** - Prevent reintroducing known bugs

## Test Naming Conventions

### Test Files
- `test_<component>_<feature>.py` - For specific features
- `test_<component>.py` - For general component tests

### Test Classes
- `Test<Component><Feature>` - For feature-specific tests
- `Test<Component>` - For general component tests

### Test Methods
- `test_<scenario>_<expected_result>` - Descriptive test names
- `test_<method>_<condition>` - For method-specific tests

## Test Requirements

### Before Committing Code

1. ✅ All existing tests must pass
2. ✅ New tests must be added for new functionality
3. ✅ Test coverage must be maintained or improved
4. ✅ Tests must follow the naming conventions
5. ✅ Tests must be placed in the correct directory structure

### Test Quality Standards

- **Isolation**: Tests should be isolated (no dependencies between tests)
- **Speed**: Tests should be fast (avoid unnecessary delays)
- **Determinism**: Tests should produce consistent results
- **Clarity**: Test names should clearly describe what they test
- **Coverage**: Tests should cover both happy paths and edge cases

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/rbac/test_enforcer.py -v
```

### Run Tests with Coverage
```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Run Tests with Detailed Output
```bash
python -m pytest tests/ -v --tb=short
```

### Run Tests and Fail Fast
```bash
python -m pytest tests/ -x
```

## Test Fixtures

### Common Fixtures

- `clean_enforcer`: Provides a clean Casbin enforcer instance
- `clean_runtime`: Provides a clean runtime instance
- `mock_agent_id`: Provides a mock agent ID
- `mock_vsm_agent`: Provides a mock VSM agent
- `event_loop`: Provides an event loop for async tests

### Using Fixtures

```python
import pytest

from casbin import Enforcer

class TestRBACEnforcer:
    def test_enforcer_initialization(self, clean_enforcer: Enforcer):
        """Test enforcer initialization."""
        assert clean_enforcer is not None
        assert clean_enforcer.get_policy() == []
```

## Test Examples

### Unit Test Example

```python
# tests/rbac/test_enforcer.py
import pytest
from casbin import Enforcer

from src.rbac.enforcer import get_enforcer

class TestRBACEnforcer:
    def test_enforcer_singleton(self):
        """Test that enforcer is a singleton."""
        enforcer1 = get_enforcer()
        enforcer2 = get_enforcer()

        assert enforcer1 is enforcer2
        assert isinstance(enforcer1, Enforcer)
```

### Integration Test Example

```python
# tests/test_vsm_agent.py
import pytest
from unittest.mock import AsyncMock, patch

from src.vsm_agent import VSMSystemAgent
from src.tools.delegate import DelegateRequest

class TestVSMSystemAgentIntegration:
    async def test_agent_message_handling(self):
        """Test complete message handling workflow."""
        # Setup
        agent = VSMSystemAgent("test_agent")
        request = DelegateRequest(
            content="Test task",
            sender="test_sender",
            target_agent_id="test_target"
        )

        # Execute
        response = await agent.handle_delegate(request, MessageContext())

        # Verify
        assert response.content == "Expected response"
        assert response.is_error is False
```

### Mocking Example

```python
# tests/tools/test_delegate.py
import pytest
from unittest.mock import AsyncMock, patch

from src.tools.delegate import Delegate
from autogen_core import AgentId

class TestDelegateTool:
    async def test_delegate_execution(self):
        """Test delegate tool execution."""
        agent_id = AgentId("test_agent", "test_agent_id")

        # Mock dependencies
        with patch('src.tools.delegate.send_message_to_agent', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = DelegateResponse("Success", False)

            # Create and run delegate tool
            delegate = Delegate(agent_id)
            result = await delegate.run(
                DelegateArgsType(target_agent_id="target_agent", task="Test task"),
                CancellationToken()
            )

            # Verify
            assert result.result[0].content == "Success"
            assert result.is_error is False
```

## Test Data and Fixtures

### Test Data Generators

The `tests/fixtures/test_data.py` module provides:

- Sample system IDs for different VSM types
- Mock messages and requests
- Test policy data
- Helper functions for generating test data

### Using Test Data

```python
from tests.fixtures.test_data import (
    SAMPLE_SYSTEM_IDS,
    create_mock_delegate_request,
    generate_test_system_ids
)

# Get sample system IDs
system_1_id = SAMPLE_SYSTEM_IDS[SystemTypes.SYSTEM_1_OPERATIONS]

# Create mock request
request = create_mock_delegate_request(
    content="Test task",
    sender="test_sender"
)

# Generate test system IDs
test_ids = generate_test_system_ids(namespace="test", count=3)
```

## Test Coverage Requirements

### Minimum Coverage
- **80% overall coverage** for all new code
- **100% coverage** for critical components (RBAC, security)
- **Branch coverage** for complex logic

### Coverage Tools

```bash
# Install coverage tools
pip install pytest-cov

# Run tests with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Generate coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Continuous Integration

### CI Configuration

The project should include CI configuration (e.g., GitHub Actions) to:

1. Run all tests on every push
2. Enforce test coverage requirements
3. Run linting and type checking
4. Build documentation

### Example CI Workflow

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio

    - name: Run tests
      run: |
        python -m pytest tests/ --cov=src --cov-fail-under=80

    - name: Run linting
      run: |
        pip install flake8 black
        flake8 src/ tests/
        black --check src/ tests/
```

## Best Practices

### Test Organization

1. **Mirror source structure**: Tests should be in the same directory structure as the code they test
2. **Single responsibility**: Each test should test one specific thing
3. **Clear naming**: Test names should clearly describe what they test
4. **Proper isolation**: Tests should not depend on each other

### Test Writing

1. **Arrange-Act-Assert pattern**: Structure tests clearly
2. **Use fixtures**: For common setup and teardown
3. **Mock external dependencies**: For isolation and speed
4. **Test edge cases**: Include boundary conditions and error cases

### Test Maintenance

1. **Update tests with code changes**: Keep tests in sync with implementation
2. **Remove obsolete tests**: Clean up tests for removed features
3. **Refactor tests**: Improve test code quality regularly
4. **Document complex tests**: Add comments for non-obvious test logic

## Debugging Tests

### Common Test Issues

1. **Flaky tests**: Tests that produce inconsistent results
2. **Slow tests**: Tests that take too long to run
3. **Overly complex tests**: Tests that are hard to understand
4. **Tightly coupled tests**: Tests that depend on implementation details

### Debugging Techniques

```bash
# Run specific test with verbose output
python -m pytest tests/rbac/test_enforcer.py::TestRBACEnforcer::test_enforcer_singleton -v -s

# Run test with debugging
python -m pytest tests/rbac/test_enforcer.py -v --pdb

# Run test with logging
python -m pytest tests/rbac/test_enforcer.py -v --log-cli-level=DEBUG
```

## Test Documentation

### Documenting Tests

Each test should include:

1. **Descriptive docstring**: Explain what the test verifies
2. **Clear assertions**: Make expected outcomes obvious
3. **Comments for complex logic**: Explain non-obvious test setup
4. **References to requirements**: Link to relevant requirements or issues

### Example Well-Documented Test

```python
class TestNamespaceIsolation:
    """Test namespace isolation in RBAC."""

    def test_cross_namespace_access_denied(self, clean_enforcer: Enforcer):
        """
        Test that cross-namespace access is denied by default.

        This test verifies the security requirement that agents in one namespace
        cannot access resources in another namespace without explicit permission.

        Requirements: SEC-001 (Namespace Isolation)
        """
        # Setup: Add policy for namespace1
        clean_enforcer.add_policy(
            "namespace1_operations_worker",
            "namespace1",
            "Delegate",
            "namespace1_control_root"
        )

        # Execute: Test access to different namespace
        allowed = clean_enforcer.enforce(
            "namespace1_operations_worker",
            "namespace2",
            "Delegate",
            "namespace2_control_root"
        )

        # Verify: Access should be denied
        assert allowed is False, "Cross-namespace access should be denied by default"
```

## Test Reporting

### Test Reports

Generate comprehensive test reports:

```bash
# HTML report
python -m pytest tests/ --cov=src --cov-report=html:coverage_report

# XML report (for CI integration)
python -m pytest tests/ --cov=src --cov-report=xml:coverage.xml

# JUnit report
python -m pytest tests/ --junitxml=test_results.xml
```

### Test Metrics

Track important test metrics:

1. **Test coverage**: Percentage of code covered by tests
2. **Test execution time**: Time taken to run all tests
3. **Test success rate**: Percentage of tests that pass
4. **Test flakiness**: Percentage of tests with inconsistent results

## Future Test Enhancements

### Planned Test Improvements

1. **Performance testing**: Add benchmark tests for critical paths
2. **Security testing**: Add penetration testing for RBAC
3. **Load testing**: Test system behavior under heavy load
4. **Chaos testing**: Test system resilience to failures
5. **Property-based testing**: Add hypothesis testing for edge cases

### Test Automation

1. **Automated test generation**: Generate tests from specifications
2. **Test impact analysis**: Identify tests affected by code changes
3. **Test parallelization**: Run tests in parallel for faster feedback
4. **Test visualization**: Visualize test coverage and results

## Resources

- **Pytest Documentation**: https://docs.pytest.org/
- **Python Testing Best Practices**: https://realpython.com/python-testing/
- **Test-Driven Development**: https://www.agilealliance.org/glossary/tdd/
- **Mocking in Python**: https://docs.python.org/3/library/unittest.mock.html
