from __future__ import annotations

import argparse

from src.cyberagent.channels.telegram import pairing as pairing_store


def add_pairing_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "pairing",
        help="Manage Telegram pairing requests.",
        description="Manage Telegram pairing requests.",
    )
    pairing_subparsers = parser.add_subparsers(dest="pairing_command", required=True)

    list_parser = pairing_subparsers.add_parser(
        "list", help="List Telegram pairing requests."
    )
    list_parser.add_argument(
        "--status",
        choices=[
            pairing_store.PAIRING_STATUS_PENDING,
            pairing_store.PAIRING_STATUS_APPROVED,
            pairing_store.PAIRING_STATUS_DENIED,
        ],
        default=None,
        help="Filter by status.",
    )

    approve_parser = pairing_subparsers.add_parser(
        "approve", help="Approve a Telegram pairing code."
    )
    approve_parser.add_argument("code", type=str, help="Pairing code.")

    deny_parser = pairing_subparsers.add_parser(
        "deny", help="Deny a Telegram pairing code."
    )
    deny_parser.add_argument("code", type=str, help="Pairing code.")


def handle_pairing(args: argparse.Namespace) -> int:
    command = getattr(args, "pairing_command", None)
    if command == "list":
        return _handle_list(args)
    if command == "approve":
        return _handle_approve(args)
    if command == "deny":
        return _handle_deny(args)
    raise ValueError(f"Unknown pairing command: {command}")


def _handle_list(args: argparse.Namespace) -> int:
    status = getattr(args, "status", None)
    entries = pairing_store.list_pairings(status=status)
    if not entries:
        print("No Telegram pairing requests found.")
        return 0
    for entry in entries:
        print(
            f"{entry.pairing_code} | {entry.status} | "
            f"chat={entry.chat_id} user={entry.user_id}"
        )
    return 0


def _handle_approve(args: argparse.Namespace) -> int:
    code = str(getattr(args, "code", "")).strip()
    if not code:
        print("Pairing code is required.")
        return 1
    record = pairing_store.approve_pairing(code, admin_chat_id=None)
    if record is None:
        print("Pairing code not found.")
        return 1
    print(f"Approved pairing code {record.pairing_code}.")
    pairing_store.notify_user_approved(record)
    return 0


def _handle_deny(args: argparse.Namespace) -> int:
    code = str(getattr(args, "code", "")).strip()
    if not code:
        print("Pairing code is required.")
        return 1
    record = pairing_store.deny_pairing(code, admin_chat_id=None)
    if record is None:
        print("Pairing code not found.")
        return 1
    print(f"Denied pairing code {record.pairing_code}.")
    pairing_store.notify_user_denied(record)
    return 0
