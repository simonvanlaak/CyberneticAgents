# Planned Feature – Heartbeat System

## Overview
We want a **heartbeat** mechanism that periodically triggers the VSM.  Sub‑systems can *subscribe* to the heartbeat and receive a self‑prompt that tells them what to do on each tick.

## Core Requirements

1. **Central Heartbeat Scheduler**
   - Runs on a fixed interval (configurable, e.g. every 30 s, 1 min, 5 min).
   - Emits a generic **heartbeat event** that the rest of the system can listen to.

2. **Subscription Model**
   - Any system component (System 3*, System 4, custom agents) can register a **callback prompt**.
   - The subscription list is stored in a small JSON file (`/shared/heartbeat_subscriptions.json`).
   - Example entry:
   ```json
   {
     "system_id": "system4",
     "prompt": "Investigate external environment and produce a summary of any notable changes."
   }
   ```

3. **Pre‑defined Prompts** (must exist out‑of‑the‑box)
   - **System 4 – Environment Scan**
     > *“Investigate the external environment (news feeds, market data, API status) and produce a concise summary of any notable changes.”*
   - **System 3* – Deep Analytics**
     > *“Analyse all tasks executed since the last heartbeat, compare actual outcomes with the intended purpose, and report any mis‑alignments.”*
   - **System 2 – Coordination Check** (optional)
     > *“Collect the latest experiment results from all System 1 agents and publish a consolidated knowledge‑map snapshot.”*
   - **System 5 – Policy Review** (optional)
     > *“Verify that the current curiosity‑budget policy is still within the allowed thresholds; suggest adjustments if needed.”*

4. **Execution Flow**
   1. Scheduler fires → creates a **heartbeat event**.
   2. The event handler loads the subscription list.
   3. For each entry it **dispatches** the associated prompt to the target system (e.g., via a CLI command `cyberagent suggest <prompt>` or by posting a message to a shared queue).
   4. The target system processes the prompt and writes its output to a **heartbeat result store** (`/shared/heartbeat_results/<system_id>.json`).
   5. System 2 can optionally aggregate all results and expose them via a simple HTTP endpoint for human inspection.

5. **Configuration**
   - Interval (`heartbeat_interval_ms`) – default **60000 ms** (1 min).
   - Max‑runtime per tick – safety timeout (e.g., 30 s) after which the scheduler proceeds to the next tick.
   - Ability to **enable/disable** individual subscriptions at runtime by editing the JSON file.

6. **Future Extensibility**
   - Add new predefined prompts (e.g., for System 1 health checks).
   - Allow agents to **register dynamic prompts** via the CLI (`cyberagent subscribe --system A3 --prompt "Run self‑diagnostic and report latency."`).
   - Persist a **history log** of heartbeat cycles (`/shared/heartbeat_history.log`).

## Rough Implementation Sketch (Python)
```python
import json, time, threading, subprocess

SUB_FILE = '/shared/heartbeat_subscriptions.json'
RESULT_DIR = '/shared/heartbeat_results'
INTERVAL = 60  # seconds

def load_subscriptions():
    try:
        return json.load(open(SUB_FILE))
    except FileNotFoundError:
        return []

def dispatch(sub):
    # Here we just call the CLI `cyberagent suggest` with the prompt
    cmd = ['cyberagent', 'suggest', sub['prompt']]
    subprocess.run(cmd, check=False)
    # Results should be written by the target system to RESULT_DIR

def heartbeat_loop():
    while True:
        subs = load_subscriptions()
        for s in subs:
            dispatch(s)
        time.sleep(INTERVAL)

threading.Thread(target=heartbeat_loop, daemon=True).start()
```

The above snippet can be packaged as a small service (systemd unit or Docker container) and started at system boot.

---
*Document created on 2026‑01‑31 by the OpenClaw assistant.*