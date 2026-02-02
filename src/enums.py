# -*- coding: utf-8 -*-
"""
Enum definitions for the CyberneticAgents system.
"""

from enum import Enum as PyEnum


class Status(PyEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class PolicyJudgement(PyEnum):
    VAGUE = "Vague"
    VIOLATED = "Violated"
    SATISFIED = "Satisfied"


class SystemType(PyEnum):
    OPERATION = "operation"
    COORDINATION_2 = "coordination"
    CONTROL = "control"
    INTELLIGENCE = "intelligence"
    POLICY = "policy"
