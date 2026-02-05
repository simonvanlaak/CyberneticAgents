# Telegram Pairing Implementation Plan

## Goal
Implement OpenClaw-style Telegram pairing using SQLite for storage and inline Telegram buttons for admin approval.

## Phase 1: Inventory and Design
- Confirm current Telegram ingestion paths (poller and webhook) and session storage.
- Define a SQLite pairing model with status (`pending`, `approved`, `denied`), pairing code, timestamps, and user metadata.
- Decide admin notification mechanism and callback payload format for inline buttons.

## Phase 2: Pairing Core (TDD)
- Write tests for pairing creation, approval, denial, and idempotent behavior.
- Implement pairing storage and API functions in a dedicated module.
- Add parsing for pairing callback data (`pairing:approve:<code>`, `pairing:deny:<code>`).

## Phase 3: Telegram Integration (TDD)
- Add tests ensuring unpaired users are blocked from forwarding messages.
- Send pairing code to users on first contact.
- Notify admin chat IDs with inline approve/deny buttons.
- Process pairing callbacks and notify users of approval/denial.

## Phase 4: CLI + Docs
- Add `cyberagent pairing` CLI commands to list/approve/deny Telegram pairings.
- Update onboarding copy and Telegram docs to describe pairing flow and admin IDs.
