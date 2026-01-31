# -*- coding: utf-8 -*-
"""
Enum definitions for the CyberneticAgents system.
"""

from sqlalchemy import Enum


class Status(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class PolicyJudgement(Enum):
    VAGUE = "Vague"
    VIOLATED = "Violated"
    SATISFIED = "Satisfied"


class SystemType(Enum):
    OPERATION = 1
    COORDINATION_2 = 2
    CONTROL = 3
    INTELLIGENCE = 4
    POLICY = 5
