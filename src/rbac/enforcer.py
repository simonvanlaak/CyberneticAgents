"""
RBAC Enforcer for OpenClaw Tool Access

Uses Casbin to enforce tool access policies for VSM agents.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Casbin enforcer (lazy initialization)
_enforcer = None


def get_enforcer():
    """Get the Casbin enforcer instance."""
    global _enforcer

    if _enforcer is None:
        try:
            import casbin
            from casbin_sqlalchemy_adapter import Adapter
            from sqlalchemy import create_engine

            # Initialize Casbin with SQLAlchemy adapter
            engine = create_engine("sqlite:///data/rbac.db")
            adapter = Adapter(engine)

            _enforcer = casbin.Enforcer("src/rbac/model.conf", adapter)
            logger.info("RBAC enforcer initialized")

        except ImportError as e:
            logger.warning(f"Casbin not available, RBAC disabled: {e}")

            # Return a mock enforcer that allows everything
            class MockEnforcer:
                def enforce(self, *args, **kwargs):
                    return True

            _enforcer = MockEnforcer()
        except Exception as e:
            logger.error(f"Failed to initialize RBAC enforcer: {e}")

            # Return a mock enforcer that allows everything
            class MockEnforcer:
                def enforce(self, *args, **kwargs):
                    return True

            _enforcer = MockEnforcer()

    return _enforcer


def check_tool_permission(agent_id: str, tool_name: str) -> bool:
    """
    Check if an agent has permission to use a tool.

    Args:
        agent_id: ID of the agent (e.g., "root_intelligence_sys4")
        tool_name: Name of the tool (e.g., "web_search", "exec")

    Returns:
        bool: True if access is allowed, False otherwise
    """
    try:
        enforcer = get_enforcer()
        return enforcer.enforce(agent_id, tool_name, "allow")
    except Exception as e:
        logger.error(f"RBAC check failed: {e}")
        return False
