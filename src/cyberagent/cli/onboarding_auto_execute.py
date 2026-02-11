from __future__ import annotations

import logging

from src.cyberagent.cli.agent_message_queue import enqueue_agent_message
from src.cyberagent.cli.onboarding_defaults import (
    get_auto_execute_procedure,
    get_default_strategy_name,
    load_procedure_defaults,
    load_root_team_defaults,
)
from src.cyberagent.core.agent_naming import normalize_message_source
from src.cyberagent.db.db_utils import get_db
from src.cyberagent.db.models.initiative import Initiative
from src.cyberagent.db.models.procedure import Procedure
from src.cyberagent.db.models.procedure_run import ProcedureRun
from src.cyberagent.db.models.strategy import Strategy
from src.cyberagent.db.models.system import get_system_by_type
from src.cyberagent.services import procedures as procedures_service
from src.cyberagent.services import purposes as purposes_service
from src.cyberagent.services import strategies as strategies_service
from src.enums import ProcedureStatus, SystemType

logger = logging.getLogger(__name__)


def auto_execute_onboarding_sop_if_configured(team_id: int) -> None:
    try:
        team_defaults = load_root_team_defaults()
        procedure_templates = load_procedure_defaults()
        procedure_name = get_auto_execute_procedure(team_defaults, procedure_templates)
        if not procedure_name:
            return
        strategy_name = get_default_strategy_name(team_defaults)

        session = next(get_db())
        try:
            procedure = (
                session.query(Procedure)
                .filter(
                    Procedure.team_id == team_id,
                    Procedure.name == procedure_name,
                )
                .first()
            )
            if procedure is None or procedure.status != ProcedureStatus.APPROVED:
                return
            existing_run = (
                session.query(ProcedureRun.id)
                .join(Initiative, ProcedureRun.initiative_id == Initiative.id)
                .filter(
                    ProcedureRun.procedure_id == procedure.id,
                    Initiative.team_id == team_id,
                )
                .first()
            )
            if existing_run is not None:
                return
            strategy = (
                session.query(Strategy)
                .filter(
                    Strategy.team_id == team_id,
                    Strategy.name == strategy_name,
                )
                .first()
            )
            strategy_id = strategy.id if strategy is not None else None
            procedure_id = procedure.id
            procedure_description = procedure.description
        finally:
            session.close()

        if strategy_id is None:
            purpose = purposes_service.get_or_create_default_purpose(team_id)
            strategy = strategies_service.create_strategy(
                team_id=team_id,
                purpose_id=purpose.id,
                name=strategy_name,
                description=procedure_description,
            )
            strategy_id = strategy.id

        control_system = get_system_by_type(team_id, SystemType.CONTROL)
        if control_system is None:
            return
        recipient = control_system.agent_id_str
        if not isinstance(recipient, str) or not recipient:
            return

        run = procedures_service.execute_procedure(
            procedure_id=procedure_id,
            team_id=team_id,
            strategy_id=strategy_id,
            executed_by_system_id=control_system.id,
        )

        sender_system = get_system_by_type(team_id, SystemType.INTELLIGENCE)
        sender = (
            sender_system.agent_id_str
            if sender_system is not None and sender_system.agent_id_str
            else "System4/root"
        )
        enqueue_agent_message(
            recipient=recipient,
            sender=sender,
            message_type="initiative_assign",
            payload={
                "initiative_id": run.initiative_id,
                "source": normalize_message_source(sender),
                "content": f"Start initiative {run.initiative_id}.",
            },
        )
    except Exception:
        logger.exception(
            "Failed to auto-execute onboarding SOP for team_id=%s.",
            team_id,
        )
