from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from pydantic import BaseModel

from src.rbac.system_types import SystemTypes
from src.tools.delegate import Delegate
from src.tools.escalate import Escalate
from src.tools.policy_management import create_policy
from src.tools.rbac_base_tool import RBACBaseTool
from src.tools.system_create import create_system


class SystemEvolveArgsType(BaseModel):
    system_id: str
    new_namespace: str
    policy: str


class SystemEvolve(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        description = (
            f"If a {SystemTypes.SYSTEM_1_OPERATIONS} is not capable of fulfilling its purpose due to high load or complexity, it needs to be evolved."
            f"Parameters: system_id, new_namespace, policy"
            f"- system_id: The system that will be evolved"
            f"- new_namespace: The new namespace for the evolved system."
            f"- policy: The new policy for the evolved system, this needs to describe the purpose of the new evolved system."
        )

        super().__init__(
            agent_id=agent_id,
            args_type=SystemEvolveArgsType,
            tool_name=__class__.__name__,
            description=description,
        )

    async def run(
        self, args: SystemEvolveArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = self.get_call_id()
        # Validate RBAC permissions
        if not self.is_action_allowed(args.system_id):
            return FunctionExecutionResult(
                content="Not authorized to evolve this system",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )
        try:
            await self._system_evolve(
                args.system_id,
                args.new_namespace,
                args.policy,
            )
        except Exception as e:
            return FunctionExecutionResult(
                content=f"Error evolving system: {str(e)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )
        return FunctionExecutionResult(
            content=f"System evolved successfully, can now be reached at {args.new_namespace}",
            name=self.tool_name,
            call_id=call_id,
            is_error=False,
        )

    async def _system_evolve(
        self, system_id: str, new_namespace: str, new_system_policy: str
    ):
        parent_namespace = self.get_namespace(system_id)
        system_type = self.get_type(system_id)
        if system_type != SystemTypes.SYSTEM_1_OPERATIONS:
            raise ValueError(f"Can only evolve {SystemTypes.SYSTEM_1_OPERATIONS}.")

        if self.system_type != SystemTypes.SYSTEM_5_POLICY:
            raise ValueError(f"Only {SystemTypes.SYSTEM_5_POLICY} can evolve a system.")

        if self.is_namespace(new_namespace):
            raise ValueError(
                f"Namespace {new_namespace} already exists, pick a different name."
            )
        # Delete existing system
        self.delete_system(system_id)
        # Create new system - we need to create a System 1 in the new namespace

        # Create System 5 for the new namespace
        created_system_id = f"{new_namespace}_{SystemTypes.SYSTEM_5_POLICY}_sys5"
        create_system(created_system_id)

        await create_policy(created_system_id, new_system_policy)
        # Update permissions
        self.give_system_id_tool_permission(
            created_system_id, Escalate.__class__.__name__, parent_namespace
        )
        parent_sys3 = self.get_system_id_from_namespace_with_type(
            parent_namespace, SystemTypes.SYSTEM_3_CONTROL
        )
        if parent_sys3 is None:
            raise ValueError(
                f"Parent system {parent_namespace} does not have a {SystemTypes.SYSTEM_3_CONTROL}"
            )
        self.give_system_id_tool_permission(
            parent_sys3,
            Delegate.__name__,
            new_namespace,
        )
