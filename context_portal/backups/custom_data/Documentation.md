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
