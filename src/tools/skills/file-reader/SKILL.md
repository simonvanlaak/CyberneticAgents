---
name: file-reader
description: Read local text files safely for analysis, extraction, and summarization tasks.
metadata:
  cyberagent:
    tool: exec
    subcommand: run
    timeout_class: standard
---

Use this skill to inspect text files in allowed work directories.

Guidelines:
1. Prefer targeted reads (`head`, `tail`, or ranged `sed`) before full-file reads.
2. Avoid binary files and avoid printing sensitive values.
3. Extract only the sections needed for the active task.
4. Keep outputs concise and actionable.
