"""Prompt templates for optional LLM-backed synthesis."""

from __future__ import annotations


API_LLM_MASKS_PROMPT_VERSION = "api_llm_masks_v1"


def api_llm_masks_system_prompt(*, max_candidates: int) -> str:
    return f"""You propose regex mask candidates for a deterministic log parser.
Return JSON only, matching the provided schema.
The parser will validate every candidate locally; unsafe or broad masks will be rejected.

Rules:
- Propose at most {max_candidates} candidate masks.
- Prefer conservative, context-preserving regexes.
- For key-value fields, preserve the key and use value_group for only the value.
- Good: request_id=([A-Za-z0-9_.:-]+) with value_group 1.
- Bad: request_id=[A-Za-z0-9_.:-]+ with no value_group.
- Do not create masks for log levels such as INFO, WARN, ERROR, DEBUG, TRACE, or FATAL.
- Do not create broad full-line masks.
- Do not create broad NUMBER or GENERIC_ID masks unless the sample clearly requires them.
- Use replacements in the exact form <VAR:TYPE>.
- Use only regex flags from IGNORECASE, MULTILINE, ASCII.
- Do not include raw sensitive examples; examples_observed should be empty or redacted."""


def api_llm_masks_user_prompt(sample_lines: list[str]) -> str:
    rendered = "\n".join(sample_lines)
    return f"""Analyze these sample logs and propose candidate regex masks.

Sample logs:
```text
{rendered}
```"""

