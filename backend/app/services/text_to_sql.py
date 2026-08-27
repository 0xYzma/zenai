"""
Text-to-SQL engine — DISABLED.

This module is a placeholder. The text-to-SQL feature is not production-safe
and remains off (ENABLE_TEXT_TO_SQL=false). It will only be enabled after:

  - Real analytics views are designed and approved.
  - An allowlist of permitted relations and columns exists.
  - EXPLAIN cost gate, row cap, and statement timeout are implemented.
  - The ai_analytics role is fully provisioned with real grants and RLS policies.
  - The engine is wired into the integrated chat pipeline.
  - Malicious SQL and pooled-context-leak tests pass.

Do not import anything from this module. It is intentionally empty.
"""

raise ImportError(
    "text_to_sql is not enabled. Set ENABLE_TEXT_TO_SQL=true only after "
    "completing all prerequisites documented at the top of this file."
)
