# Planned Feature – Onboarding & Continuous Purpose Adjustment

## Problem Statement
New deployments of the CyberneticAgents VSM currently require a **manual boot‑strapping** phase:
1. The system is started with no defined purpose. 
2. Operators must manually create the first set of goals, KPIs and policies.
3. After the initial setup, purpose adjustments are still performed ad‑hoc.

This manual onboarding is error‑prone and slows down experiments. We need an **automated onboarding flow** that discovers an initial purpose, sets up the basic VSM configuration, and then **continually refines** that purpose as the system gathers data.

## High‑Level Solution
Create an **Onboarding Service** that runs once at first start and then stays active in the background to **re‑evaluate the system’s purpose** on a regular schedule.

### 1. First‑Run Discovery
- **Self‑Assessment Prompt** – The service sends a *system‑wide prompt* to System 4:
  > *“Analyse the current external environment (news, market trends, available data sources) and propose an initial high‑level purpose for the VSM.”*
- **System 4** returns a **purpose proposal** (JSON):
  ```json
  {
    "purpose": "Provide automated insights on token‑usage trends for a medium‑sized engineering department",
    "KPIs": ["daily token‑usage report", "monthly cost‑reduction suggestions"],
    "initial_budget": 5000
  }
  ```
- **System 5** validates the proposal against policy constraints (e.g., budget limits) and either **accepts** it or **asks for clarification**.
- Upon acceptance, the VSM writes the purpose to a persistent file (`/shared/vsm_purpose.json`) and broadcasts it to all agents.

### 2. Continuous Purpose Adjustment Loop
- **Scheduled Re‑Evaluation** (heartbeat or cron) – every **N** hours (default 24 h) the Onboarding Service triggers the same prompt to System 4, but now includes the **previous purpose** as context.
- **Delta Analysis** – System 4 returns a *difference report* highlighting:
  - New opportunities (e.g., emerging data sources)
  - Degraded KPIs (e.g., low usage of a previously important report)
- **System 3** reviews the delta and decides whether to **adjust** the purpose, **re‑allocate** the budget, or keep the status quo.
- All changes are logged in a **purpose‑history file** (`/shared/purpose_history.log`).

### 3. Subscription Model (reuse of Heartbeat)
- The Onboarding Service can **subscribe** to the heartbeat with its own prompt:
  - **Prompt**: *“Re‑evaluate VSM purpose based on latest environment scan and internal KPI trends.”*
- This keeps the implementation consistent with the heartbeat feature described earlier.

## Required Artifacts
- **`/shared/vsm_purpose.json`** – current purpose, KPIs and budget.
- **`/shared/purpose_history.log`** – append‑only log of every purpose change (timestamp, old purpose, new purpose, reason).
- **`/shared/onboarding_config.yaml`** – configuration for the onboarding service:
  ```yaml
  initial_interval_hours: 24
  max_retries: 3
  purpose_schema:
    purpose: str
    KPIs: list
    initial_budget: int
  ```
- **CLI commands** (to be added later):
  - `cyberagent onboarding status` – show current purpose and last change.
  - `cyberagent onboarding force` – trigger an immediate re‑evaluation.

## Rough Implementation Sketch (Python)
```python
import json, pathlib, subprocess, time

PURPOSE_FILE = '/shared/vsm_purpose.json'
HISTORY_LOG   = '/shared/purpose_history.log'
CONFIG_FILE   = '/shared/onboarding_config.yaml'
INTERVAL_HOURS = 24

def load_purpose():
    try:
        return json.load(open(PURPOSE_FILE))
    except FileNotFoundError:
        return None

def save_purpose(new):
    old = load_purpose()
    with open(PURPOSE_FILE, 'w') as f:
        json.dump(new, f, indent=2)
    # log the change
    entry = {
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        "old": old,
        "new": new,
        "reason": "onboarding reevaluation"
    }
    pathlib.Path(HISTORY_LOG).write_text(json.dumps(entry)+'\n', append=True)

def prompt_system4(context=None):
    base_prompt = "Analyse the external environment and propose a VSM purpose."
    if context:
        base_prompt += f" Previous purpose: {json.dumps(context)}"
    # we use the existing CLI suggest mechanism
    result = subprocess.check_output(['cyberagent', 'suggest', '--json', base_prompt])
    return json.loads(result)

def onboarding_cycle():
    current = load_purpose()
    proposal = prompt_system4(current)
    # simple validation – you could hook System5 here
    if proposal.get('purpose'):
        save_purpose(proposal)

# run forever – can be started as a systemd service
while True:
    onboarding_cycle()
    time.sleep(INTERVAL_HOURS * 3600)
```

## Acceptance Criteria
- On first start, the system automatically creates a purpose without manual input.
- The purpose file exists and is readable by all agents.
- A history log records every change with timestamps.
- Operators can query the current purpose via `cyberagent onboarding status`.
- The service can be forced to run on demand (`cyberagent onboarding force`).

---
*Document created on 2026‑01‑31 by the OpenClaw assistant.*