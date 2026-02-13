from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Awaitable, Callable

from autogen_core import AgentId

from src.cyberagent.agents.messages import UserMessage
from src.cyberagent.cli.message_catalog import get_message


async def handle_dev(
    args: argparse.Namespace,
    *,
    handle_tool_test: Callable[[argparse.Namespace], Awaitable[int]],
    handle_dev_system_run: Callable[[argparse.Namespace], Awaitable[int]],
) -> int:
    if args.dev_command == "tool-test":
        return await handle_tool_test(args)
    if args.dev_command == "system-run":
        return await handle_dev_system_run(args)
    print(get_message("dev", "unknown_dev_command"), file=sys.stderr)
    return 1


async def handle_dev_system_run(
    args: argparse.Namespace,
    *,
    init_db: Callable[[], None],
    register_systems: Callable[[], Awaitable[None]],
    get_runtime: Callable[[], Any],
    stop_runtime_with_timeout: Callable[[], Awaitable[None]],
    suggest_timeout_seconds: float,
) -> int:
    init_db()
    await register_systems()
    runtime = get_runtime()
    try:
        recipient = AgentId.from_str(args.system_id)
    except Exception as exc:
        print(
            get_message(
                "dev",
                "invalid_system_id",
                system_id=args.system_id,
                error=exc,
            ),
            file=sys.stderr,
        )
        return 2
    message = UserMessage(content=args.message, source="Dev")
    try:
        await asyncio.wait_for(
            asyncio.shield(
                runtime.send_message(
                    message=message,
                    recipient=recipient,
                    sender=AgentId(type="UserAgent", key="root"),
                )
            ),
            timeout=suggest_timeout_seconds,
        )
        print(get_message("dev", "message_delivered", system_id=args.system_id))
        return 0
    except asyncio.TimeoutError:
        print(get_message("dev", "message_send_timed_out"))
        return 1
    except Exception as exc:  # pragma: no cover - safety net for runtime errors
        print(
            get_message("dev", "failed_send_message", error=exc),
            file=sys.stderr,
        )
        return 1
    finally:
        await stop_runtime_with_timeout()


async def handle_tool_test(
    args: argparse.Namespace,
    *,
    create_cli_tool: Callable[[], Any],
    find_skill_definition: Callable[[str], Any],
    list_skill_names: Callable[[], list[str]],
    execute_skill_tool: Callable[
        [Any, Any, dict[str, Any], str | None], Awaitable[dict[str, Any]]
    ],
    maybe_reexec_tool_test: Callable[[argparse.Namespace, Exception], int | None],
    init_db: Callable[[], None],
) -> int:
    try:
        parsed_args = json.loads(args.args or "{}")
    except json.JSONDecodeError as exc:
        print(get_message("dev", "invalid_args_json", error=exc), file=sys.stderr)
        return 2
    if not isinstance(parsed_args, dict):
        print(get_message("dev", "args_not_object"), file=sys.stderr)
        return 2

    skill = find_skill_definition(args.tool_name)
    if skill is None:
        known = list_skill_names()
        suffix = f" Available: {', '.join(known)}" if known else ""
        print(
            get_message(
                "dev",
                "unknown_tool",
                tool_name=args.tool_name,
                suffix=suffix,
            ),
            file=sys.stderr,
        )
        return 2

    cli_tool = create_cli_tool()
    if cli_tool is None:
        print(get_message("dev", "cli_tool_unavailable"), file=sys.stderr)
        return 1

    if args.agent_id:
        init_db()
    else:
        print(get_message("dev", "tool_test_no_agent"))

    executor = getattr(cli_tool, "executor", None)
    started = False
    if executor is not None and hasattr(executor, "start"):
        try:
            await executor.start()
            started = True
        except Exception as exc:
            reexec = maybe_reexec_tool_test(args, exc)
            if reexec is not None:
                return reexec
            print(
                get_message("dev", "failed_start_executor", error=exc),
                file=sys.stderr,
            )
            return 1

    try:
        result = await execute_skill_tool(cli_tool, skill, parsed_args, args.agent_id)
    finally:
        if started and executor is not None and hasattr(executor, "stop"):
            await executor.stop()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("success") else 1
