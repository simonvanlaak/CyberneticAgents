from autogen_core import AgentId, CancellationToken
from autogen_core.models import FunctionExecutionResult
from pydantic import BaseModel

from src.rbac.enforcer import get_enforcer, get_system_id_from_namespace_with_type
from src.rbac.system_types import SystemTypes
from src.tools.policy_management import create_policy
from src.tools.rbac_base_tool import RBACBaseTool

from .delegate import Delegate
from .escalate import Escalate
from .policy_management import PolicyManagement
from .system_list import SystemList
from .system_read import SystemRead


class SystemCreateArgsType(BaseModel):
    system_id: str  # Format: namespace_type_name
    policy: str = ""  # Optional policy content for the new system


class SystemCreate(RBACBaseTool):
    def __init__(self, agent_id: AgentId):
        description = (
            "Create new VSM systems. "
            "Usage: Create a new system using system_id format: namespace_type_name (e.g., 'myapp_operations_worker'). "
            "It is highly recommended to also  provide a policy content for the new system."
        )
        super().__init__(
            agent_id=agent_id,
            args_type=SystemCreateArgsType,
            tool_name=self.__class__.__name__,
            description=description,
        )

    async def run(
        self, args: SystemCreateArgsType, cancellation_token: CancellationToken
    ) -> FunctionExecutionResult:
        """Create a new VSM system with RBAC policies."""
        print(f"[{self.agent_id.key}/{self.tool_name}] {args}")
        call_id = self.get_call_id()
        # Parse system_id (format: namespace_type_name)
        try:
            parts = args.system_id.split("_")
            if len(parts) < 3:
                return FunctionExecutionResult(
                    content="Invalid system_id format. Expected: namespace_type_name, got: {args.system_id}",
                    name=self.tool_name,
                    call_id=call_id,
                    is_error=True,
                )

            system_type = parts[-2]

        except Exception as e:
            return FunctionExecutionResult(
                content=f"Failed to parse system_id: {str(e)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        # Validate system type
        valid_types = [
            SystemTypes.SYSTEM_1_OPERATIONS,
            SystemTypes.SYSTEM_2_COORDINATION,
            SystemTypes.SYSTEM_3_CONTROL,
            SystemTypes.SYSTEM_4_INTELLIGENCE,
            SystemTypes.SYSTEM_5_POLICY,
        ]

        if system_type not in valid_types:
            return FunctionExecutionResult(
                content=f"Invalid system type. Must be one of: {', '.join(valid_types)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        # Check RBAC permissions
        if not self.is_action_allowed(system_type):
            return FunctionExecutionResult(
                content=f"Not authorized to create {system_type} systems",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )

        try:
            # Use the updated create_system function with namespace extraction
            created_system_id = create_system(system_id=args.system_id)
            await create_policy(args.system_id, args.policy)

            return FunctionExecutionResult(
                content=f"System {created_system_id} created successfully",
                name=self.tool_name,
                call_id=call_id,
                is_error=False,
            )

        except Exception as e:
            return FunctionExecutionResult(
                content=f"Failed to create system: {str(e)}",
                name=self.tool_name,
                call_id=call_id,
                is_error=True,
            )


DEFAULT_PERMISSIONS = {
    SystemTypes.SYSTEM_1_OPERATIONS: [
        (Escalate.__name__, SystemTypes.SYSTEM_2_COORDINATION),
        (Escalate.__name__, SystemTypes.SYSTEM_3_CONTROL),
        (SystemRead.__name__, SystemTypes.SYSTEM_1_OPERATIONS),
    ],
    SystemTypes.SYSTEM_2_COORDINATION: [
        (Delegate.__name__, SystemTypes.SYSTEM_1_OPERATIONS),
        (Escalate.__name__, SystemTypes.SYSTEM_3_CONTROL),
        (SystemRead.__name__, SystemTypes.SYSTEM_1_OPERATIONS),
    ],
    SystemTypes.SYSTEM_3_CONTROL: [
        (Delegate.__name__, SystemTypes.SYSTEM_1_OPERATIONS),
        (Delegate.__name__, SystemTypes.SYSTEM_2_COORDINATION),
        (Escalate.__name__, SystemTypes.SYSTEM_5_POLICY),
        (SystemRead.__name__, "*"),
        (SystemList.__name__, "*"),
    ],
    SystemTypes.SYSTEM_4_INTELLIGENCE: [
        (Delegate.__name__, SystemTypes.SYSTEM_3_CONTROL),
        (Escalate.__name__, SystemTypes.SYSTEM_5_POLICY),
        (SystemRead.__name__, "*"),
        (SystemList.__name__, "*"),
    ],
    SystemTypes.SYSTEM_5_POLICY: [
        (Delegate.__name__, SystemTypes.SYSTEM_3_CONTROL),
        (Delegate.__name__, SystemTypes.SYSTEM_4_INTELLIGENCE),
        (SystemRead.__name__, "*"),
        (SystemList.__name__, "*"),
        ("SystemCreate", SystemTypes.SYSTEM_1_OPERATIONS),
        ("SystemCreate", SystemTypes.SYSTEM_2_COORDINATION),
        ("SystemCreate", SystemTypes.SYSTEM_3_CONTROL),
        ("SystemCreate", SystemTypes.SYSTEM_4_INTELLIGENCE),
        ("SystemEvolve", SystemTypes.SYSTEM_1_OPERATIONS),
        (PolicyManagement.__name__, SystemTypes.SYSTEM_1_OPERATIONS),
        (PolicyManagement.__name__, SystemTypes.SYSTEM_2_COORDINATION),
        (PolicyManagement.__name__, SystemTypes.SYSTEM_3_CONTROL),
        (PolicyManagement.__name__, SystemTypes.SYSTEM_4_INTELLIGENCE),
    ],
}


def create_system(system_id: str):
    parts = system_id.split("_")
    if len(parts) != 3:
        raise ValueError(
            "Invalid system ID format, must contain exactly two underscores"
        )
    system_namespace = parts[0]
    system_type = parts[1]

    enforcer = get_enforcer()
    # check if system_id already exists
    if len(enforcer.get_implicit_permissions_for_user(system_id)) > 0:
        raise ValueError(f"System ID {system_id} already exists")
    # check if system type already exists in namespace (except for sys 1)
    if system_type not in enforcer.get_all_roles_by_domain(system_namespace):
        permissions = DEFAULT_PERMISSIONS.get(system_type, [])
        if len(permissions) == 0:
            raise ValueError(
                f"Invalid system type {system_type}, no default permissions defined."
            )

        for permission in permissions:
            tool_name = permission[0]
            action = permission[1]

            enforcer.add_policy(system_id, system_namespace, tool_name, action)

    # Add new system to their roles
    success = enforcer.add_role_for_user_in_domain(
        system_id, system_type, system_namespace
    )
    if not success:
        raise ValueError(
            f"Failed to add role for user {system_id} in domain {system_namespace}"
        )
