---
name: file-reader
description: Read local text files safely for analysis, extraction, and summarization tasks.
metadata:
  cyberagent:
    tool: file-reader
    timeout_class: standard
input_schema:
  type: object
  properties:
    command:
      type: string
output_schema:
  type: object
  properties:
    output:
      type: string
    error:
      type: string
---

Use this skill to inspect text files in allowed work directories.

Guidelines:
1. Prefer targeted reads (`head`, `tail`, or ranged `sed`) before full-file reads.
2. Avoid binary files and avoid printing sensitive values.
3. Extract only the sections needed for the active task.
4. Keep outputs concise and actionable.
