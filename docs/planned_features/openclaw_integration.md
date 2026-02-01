# Planned Feature – OpenClaw Ecosystem Integration

## Why We Need This Feature
The CyberneticAgents (CA) platform should be able to **talk to the outside world** using the same channels and tools that OpenClaw already provides:
- **WhatsApp, Email, Slack, Discord, Telegram, etc.** – for sending and receiving messages.
- **Built‑in OpenClaw tools** – `web_search`, `web_fetch`, `browser`, `tts`, and any future skill.

Having a native integration means we do not need to roll our own adapters, we can reuse the robust, secure, and already‑authenticated channel plugins that OpenClaw ships with. It also lets CA agents **trigger actions** (e.g., “search the web for the latest token‑price”) and **receive replies** via the user’s preferred messenger.

## High‑Level Architecture
1. **Channel Adapter Layer** – a thin wrapper inside CA that forwards messages to OpenClaw’s channel plugins (`message` tool) and receives inbound messages via OpenClaw’s `sessions_send`.
2. **Tool Bridge** – expose OpenClaw’s internal tools (`web_search`, `web_fetch`, `browser`, `tts`, etc.) as CA‑agent **capabilities**. Agents can call a unified API like `openclaw.run_tool('web_search', {...})`.
3. **Message Router** – map incoming messages to a target **system** (e.g., System 4) based on a simple routing table stored in `routing.yaml`.
4. **Authentication & Context** – reuse OpenClaw’s existing credential store; no new secrets are required.

## Required Artifacts
- **`/shared/openclaw_integration_config.yaml`** – configuration file defining which channels are enabled and the routing rules.
  ```yaml
  enabled_channels:
    - telegram
    - slack
    - email
    - whatsapp
  routing:
    default: system4
    keywords:
      "status": system3
      "analytics": system3_star
      "environment": system4
  ```
- **`/shared/openclaw_bridge.py`** – a small Python module that wraps OpenClaw tool calls and provides a uniform interface for CA agents.
- **CLI extensions** (to be added later):
  - `cyberagent channel send <channel> <message>` – forward a message to a specific channel.
  - `cyberagent channel listen` – start a background listener that forwards inbound messages into the CA message queue.

## Implementation Sketch (Python)
```python
import json, subprocess, pathlib

CONFIG = pathlib.Path('/shared/openclaw_integration_config.yaml')

def load_config():
    import yaml
    return yaml.safe_load(open(CONFIG))

def send_message(channel, text, **kwargs):
    # Use OpenClaw's `message` tool (action=send)
    payload = {
        "action": "send",
        "channel": channel,
        "message": text,
    }
    payload.update(kwargs)
    subprocess.run(['openclaw', 'message', json.dumps(payload)], check=False)

def run_tool(name, **params):
    # Generic dispatcher for OpenClaw tools
    if name == 'web_search':
        from functions import web_search
        return web_search(params)
    elif name == 'web_fetch':
        from functions import web_fetch
        return web_fetch(params)
    elif name == 'browser':
        from functions import browser
        return browser(params)
    # add more as needed
    raise ValueError(f'Unknown tool: {name}')

def route_inbound(message):
    cfg = load_config()
    routing = cfg.get('routing', {})
    # simple keyword routing
    for kw, target in routing.get('keywords', {}).items():
        if kw in message.lower():
            return target
    return routing.get('default', 'system4')
```

## Workflow Example
1. **User sends a Slack message**: “Hey, give me the latest token price.”
2. OpenClaw forwards the raw text to the CA inbox (via `sessions_send`).
3. The CA router looks up the keyword “token” → routes to **System 4**.
4. System 4 calls `run_tool('web_search', {'query':'current token price', 'count':1})`.
5. The result is formatted and sent back to the user via `send_message('slack', result)`.

## Acceptance Criteria
- CA can **receive** messages from any enabled OpenClaw channel.
- CA can **send** replies back on the same channel.
- Agents can **invoke** OpenClaw tools (`web_search`, `web_fetch`, `browser`, `tts`, …) via the `run_tool` wrapper.
- Configuration is persisted in a single YAML file and can be edited without code changes.
- No additional authentication steps are required; the integration uses OpenClaw’s existing token store.

---
*Document created on 2026‑01‑31 by the OpenClaw assistant.*