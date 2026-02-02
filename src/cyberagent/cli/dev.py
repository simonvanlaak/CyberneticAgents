from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Awaitable, Callable

from autogen_core import AgentId

from src.agents.messages import UserMessage


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
    print("Unknown dev command.", file=sys.stderr)
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
        print(f"Invalid system id '{args.system_id}': {exc}", file=sys.stderr)
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
        print(f"Message delivered to {args.system_id}.")
        return 0
    except asyncio.TimeoutError:
        print(
            "Message send timed out; the runtime may still be working. "
            "Check logs with 'cyberagent logs'."
        )
        return 1
    except Exception as exc:  # pragma: no cover - safety net for runtime errors
        print(f"Failed to send message: {exc}", file=sys.stderr)
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
        print(f"Invalid --args JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(parsed_args, dict):
        print("--args must decode to a JSON object.", file=sys.stderr)
        return 2

    skill = find_skill_definition(args.tool_name)
    if skill is None:
        known = list_skill_names()
        suffix = f" Available: {', '.join(known)}" if known else ""
        print(f"Unknown tool '{args.tool_name}'.{suffix}", file=sys.stderr)
        return 2

    cli_tool = create_cli_tool()
    if cli_tool is None:
        print("CLI tool executor unavailable; check CLI tools image.", file=sys.stderr)
        return 1

    if args.agent_id:
        init_db()
    else:
        print("Note: running without agent id; permissions not enforced.")

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
            print(f"Failed to start CLI tool executor: {exc}", file=sys.stderr)
            return 1

    try:
        result = await execute_skill_tool(cli_tool, skill, parsed_args, args.agent_id)
    finally:
        if started and executor is not None and hasattr(executor, "stop"):
            await executor.stop()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("success") else 1
