# -*- coding: utf-8 -*-

"""CyberneticAgents - VSM-based multi-agent system with AutoGen and Casbin RBAC."""

__version__ = "0.1.0"

# Compatibility re-export for legacy imports used by tests and older modules.
from src.cyberagent.db import init_db

__all__ = ["init_db"]
