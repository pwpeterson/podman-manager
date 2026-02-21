# Custom Data: Documentation

### INTERACTIVE_CHAT_UX_RECOMMENDATIONS

*   [2026-01-07 17:15:17]

```json
{
  "scope": "ai_analyzer interactive follow-up session",
  "current_state": {
    "input": "single-line input() with ==> prompt",
    "output": "inline markdown-ish rendering; no explicit user/assistant separation",
    "history": "none"
  },
  "recommendations": [
    {
      "title": "Chat bubbles (Panels) with explicit roles",
      "targets": [
        "ai_analyzer/display/interactive.py:_process_followup_question"
      ],
      "impact": "High",
      "effort": "Low"
    },
    {
      "title": "Maintain in-session transcript/history",
      "targets": [
        "ai_analyzer/display/interactive.py:InteractiveAnalysisHandler"
      ],
      "impact": "High",
      "effort": "Low-Med"
    },
    {
      "title": "Slash commands (/help,/exit,/retry,/model,/context,/copy,/save)",
      "targets": [
        "ai_analyzer/display/interactive.py:start_session"
      ],
      "impact": "High",
      "effort": "Low"
    },
    {
      "title": "Multi-line input (/paste or line continuation)",
      "targets": [
        "ai_analyzer/display/interactive.py:_read_single_line_input"
      ],
      "impact": "Med-High",
      "effort": "Low"
    },
    {
      "title": "Use rich.markdown.Markdown for assistant output (reduce regex renderer)",
      "targets": [
        "ai_analyzer/display/markdown.py:_render_markdown"
      ],
      "impact": "Med",
      "effort": "Med"
    },
    {
      "title": "Suggested follow-ups with numeric shortcuts",
      "targets": [
        "ai_analyzer/display/interactive.py:_process_followup_question"
      ],
      "impact": "Med",
      "effort": "Low"
    },
    {
      "title": "Streaming responses via Live panel (if model-proxy supports streaming)",
      "targets": [
        "ai_system/model_proxy_client.py",
        "ai_analyzer/display/interactive.py"
      ],
      "impact": "Very High",
      "effort": "High"
    }
  ],
  "notes": {
    "conport_search_status": "semantic_search_conport failing due to GPU OOM; decision/UX history not retrievable via semantic search in current environment"
  }
}
```

---
### SUPABASE_POOLER_STARTUP_EXPLANATION

*   [2026-02-21 18:31:55]

```json
{
  "title": "How supabase-pooler Starts During pm reinit supabase",
  "summary": "Explanation of the confusing error messages during pooler startup",
  "startup_flow": {
    "layer_2": "supabase-db starts and waits 30 seconds for initialization",
    "layers_3_9": "Other services start sequentially",
    "layer_10": "supabase-pooler attempts to start with database readiness check"
  },
  "error_explanation": {
    "what_happens": "_start_service_with_monitoring() calls _ensure_database_ready_for_pooler() which tries to execute: podman exec supabase-db pg_isready",
    "attempts": "Makes 12 attempts (60 seconds total) with 5-second delays",
    "error_message": "Each attempt fails with 'no container with name or ID supabase-db found'",
    "misleading": "The error doesn't mean the container doesn't exist - it means podman exec can't find/access it"
  },
  "root_causes": [
    "Database container hasn't fully started yet despite 30s wait",
    "Container still initializing PostgreSQL",
    "Container running but not accepting connections",
    "Container in restart loop",
    "Container named differently than expected (e.g., supabase-db.service vs supabase-db)"
  ],
  "fix_needed": {
    "step_1": "First check if container exists: podman ps --filter name=supabase-db --format json",
    "step_2": "Get the actual container name/ID from running containers",
    "step_3": "Then run pg_isready using verified container name",
    "step_4": "Provide clearer error messages distinguishing: container not found, container found but not ready, connection refused"
  },
  "current_behavior": "Pooler startup fails gracefully - marks layer as failed but continues with remaining layers (Kong, Studio, etc.)",
  "code_location": "managers/supabase_stack_manager.py:334 (_ensure_database_ready_for_pooler)",
  "related_functions": [
    "_start_service_with_monitoring (line 241)",
    "start_supabase_stack (line 95)"
  ]
}
```
