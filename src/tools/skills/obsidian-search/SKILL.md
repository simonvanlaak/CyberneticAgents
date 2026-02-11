---
name: obsidian-search
description: Search an Obsidian vault (markdown files) and return matching note paths/snippets.
metadata:
  cyberagent:
    tool: obsidian-search
    timeout_class: standard
input_schema:
  type: object
  properties:
    query:
      type: string
      description: Case-insensitive substring to search for (in filename or file contents).
    limit:
      type: integer
      description: Max results to return (default 10).
    include_filename:
      type: boolean
      description: Whether to search filenames (default true).
    include_content:
      type: boolean
      description: Whether to search file contents (default true).
    extensions:
      type: array
      items:
        type: string
      description: File extensions to include (default [".md"]).
    max_file_bytes:
      type: integer
      description: Skip files larger than this many bytes (default 1048576).
output_schema:
  type: object
  properties:
    results:
      type: array
      items:
        type: object
        properties:
          path:
            type: string
          score:
            type: number
          matches:
            type: array
            items:
              type: string
    error:
      type: string
---

Use this skill to search a local Obsidian vault (a folder of markdown notes).

Configuration:
- Set `OBSIDIAN_VAULT_PATH` to the vault root folder.

Notes:
- This tool is read-only.
- It returns relative note paths plus small snippets (matching lines).
- It skips very large files by default to keep execution fast.
