# Cybernetic Agents Testing Framework

This directory contains the testing framework for the Cybernetic Agents system. The test structure is organized by component, roughly mirroring `src/`.

## Test Structure

```
tests/
├── __init__.py                         # Test package initialization
├── README.md                           # This file
├── fixtures/                           # Fixture helpers (currently placeholder)
│   └── __init__.py
├── agents/                             # Agent behavior tests
│   ├── test_system1.py
│   ├── test_system3.py
│   ├── test_system3_refactored.py
│   ├── test_system3_sequential.py
│   ├── test_system4_self_tools.py
│   ├── test_system4_sequential.py
│   ├── test_system4_strategy_flow.py
│   ├── test_system5_validation.py
│   ├── test_system_base_reflection.py
│   └── test_user_system4_communication.py
├── cli/                                # CLI tests
│   ├── test_cyberagent.py
│   └── test_status_cli.py
├── models/                             # Model tests
│   ├── test_purpose.py
│   ├── test_strategy_initiative_add.py
│   └── test_system_lookup.py
├── registry/                           # Registry tests
│   └── test_register_systems.py
├── tools/                              # Tools tests
│   └── test_contact_user_tools.py
├── test_cli_session.py
├── test_logging_utils.py
└── test_system_base_structured_message.py
```

## Testing Philosophy

### Test-Driven Development (TDD)

This project follows strict TDD principles:

1. **Write tests first** - Before implementing any feature
2. **Run tests frequently** - Ensure all tests pass before committing
3. **Test coverage** - Maintain or improve coverage for new code
4. **Test organization** - Keep tests organized by component

### Test Types

1. **Unit Tests** - Test individual components in isolation
2. **Integration Tests** - Test interactions between components
3. **End-to-End Tests** - Test complete system workflows
4. **Regression Tests** - Prevent reintroducing known bugs

## Test Naming Conventions

### Test Files
- `test_<component>_<feature>.py` - For specific features
- `test_<component>.py` - For general component tests

### Test Classes (Optional)
- `Test<Component><Feature>` - For feature-specific tests
- `Test<Component>` - For general component tests

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

Shared fixtures can live under `tests/fixtures/` or in a `conftest.py` when needed.

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

The integration suite focuses on agent workflows and CLI tool execution.
Legacy delegate/escalate tool examples have been removed.

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
    generate_test_system_ids
)

# Get sample system IDs
system_1_id = SAMPLE_SYSTEM_IDS[SystemTypes.SYSTEM_1_OPERATIONS]

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
        pip install -e .
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
            "ContactUserTool",
            "namespace1_control_root"
        )

        # Execute: Test access to different namespace
        allowed = clean_enforcer.enforce(
            "namespace1_operations_worker",
            "namespace2",
            "ContactUserTool",
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
