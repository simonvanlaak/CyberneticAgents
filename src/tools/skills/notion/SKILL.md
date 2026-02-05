---
name: notion
description: Call the Notion API for searching, reading, and updating pages and databases.
metadata:
  cyberagent:
    tool: notion
    timeout_class: standard
input_schema:
  type: object
  properties:
    method:
      type: string
      description: HTTP method (GET, POST, PATCH, DELETE).
    path:
      type: string
      description: API path (e.g. /v1/search) or full URL.
    body:
      type: string
      description: JSON request body as a string.
    query:
      type: array
      items:
        type: string
      description: Query params in key=value form (repeatable).
    version:
      type: string
      description: Notion API version header (default 2025-09-03).
    timeout:
      type: integer
      description: Request timeout in seconds.
output_schema:
  type: object
  properties:
    output:
      type: object
    error:
      type: string
---

Use this skill to access the Notion API for read/write operations.

Notes:
1. `NOTION_API_KEY` is optional; without it the Notion API requests will fail.
2. Default Notion API version is `2025-09-03` unless overridden.
3. The CLI outputs JSON with `status_code`, `ok`, and `response`.

Examples:
- Search pages:
  - `method=POST`
  - `path=/v1/search`
  - `body={"query":"roadmap","page_size":5}`
- Retrieve a page:
  - `method=GET`
  - `path=/v1/pages/<page_id>`
