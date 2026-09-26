"""
TaskFlow Pro — Google Gemini AI Integration

Provides two AI-powered capabilities:
1. Dependency Suggestion Engine — suggests likely task dependencies
2. Risk Analysis — analyzes DAG structure for risk indicators

Follows human-in-the-loop principle: all suggestions are advisory only.
The AI layer has NO direct write access to the graph.
Degrades gracefully if Gemini API is unavailable.
"""

import json
import logging
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

# Lazy import — only load if API key is configured
_genai = None
_model = None


def _get_model():
    """Lazy-initialize the Gemini model."""
    global _genai, _model
    if _model is not None:
        return _model
    if not settings.gemini_available:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _genai = genai
        _model = genai.GenerativeModel(settings.GEMINI_MODEL)
        logger.info(f"Gemini model initialized: {settings.GEMINI_MODEL}")
        return _model
    except Exception as e:
        logger.warning(f"Failed to initialize Gemini: {e}")
        return None


async def suggest_dependencies(
    new_task_title: str,
    new_task_description: str,
    existing_tasks: list[dict],
) -> list[dict]:
    """
    Suggest likely dependencies for a new or existing task.

    Sends a structured prompt to Gemini containing the new task info
    and a summary of all existing tasks. The model returns structured
    JSON with suggestions including confidence scores.

    Grounding techniques:
    - Context grounding: prompt includes only real, existing tasks
    - Response schema enforcement: model returns valid JSON with task references
    - Confidence thresholds: suggestions below 40% are filtered out
    - Temperature 0.2 for deterministic responses
    """
    model = _get_model()
    if model is None:
        return []

    # Build numbered task list for context grounding
    task_list = "\n".join(
        f"  [{i+1}] ID: {t['id'][:8]}... | Title: {t['title']} | "
        f"Status: {t['status']} | Description: {t.get('description', 'N/A')[:100]}"
        for i, t in enumerate(existing_tasks)
    )

    prompt = f"""You are a project dependency analyst. Your job is to identify which existing tasks
are likely prerequisites or dependents of a new task.

NEW TASK:
  Title: {new_task_title}
  Description: {new_task_description}

EXISTING TASKS (reference by their ID):
{task_list}

INSTRUCTIONS:
1. Analyze the new task and identify which existing tasks are likely related
2. For each suggestion, determine if the existing task is a PREREQUISITE (must be done before the new task) or a DEPENDENT (depends on the new task)
3. Assign a confidence score from 0 to 100
4. Provide a brief one-sentence rationale

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{{
  "suggestions": [
    {{
      "existing_task_id": "<full task ID>",
      "direction": "prerequisite" or "dependent",
      "confidence": <0-100>,
      "rationale": "<one sentence>"
    }}
  ]
}}

Rules:
- Only reference task IDs from the existing task list above
- Confidence should reflect how certain you are about the dependency
- If no dependencies are likely, return {{"suggestions": []}}
- Maximum 5 suggestions
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 1024,
            },
        )

        # Parse JSON response
        text = response.text.strip()
        # Handle markdown code blocks
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        data = json.loads(text)
        suggestions = data.get("suggestions", [])

        # Validate and filter
        valid_task_ids = {t["id"] for t in existing_tasks}
        task_map = {t["id"]: t for t in existing_tasks}

        filtered = []
        for s in suggestions:
            task_id = s.get("existing_task_id", "")
            # Try matching by full ID or prefix
            matched_id = None
            for vid in valid_task_ids:
                if vid == task_id or vid.startswith(task_id):
                    matched_id = vid
                    break

            if matched_id and s.get("confidence", 0) >= 40:
                filtered.append({
                    "existing_task_id": matched_id,
                    "existing_task_title": task_map[matched_id]["title"],
                    "direction": s.get("direction", "prerequisite"),
                    "confidence": min(100, max(0, int(s.get("confidence", 50)))),
                    "rationale": s.get("rationale", ""),
                })

        return filtered

    except json.JSONDecodeError as e:
        logger.warning(f"Gemini returned invalid JSON: {e}")
        return []
    except Exception as e:
        logger.warning(f"Gemini dependency suggestion failed: {e}")
        return []


def analyze_risk(
    nodes: list[dict],
    edges: list[dict],
    critical_path: list[str],
) -> list[dict]:
    """
    Analyze DAG structure to assign risk indicators to each task.

    Risk factors (computed deterministically, no AI needed):
    - High fan-in: task has many prerequisites (more things that can block it)
    - Critical path membership: delays directly impact project completion
    - High fan-out: task has many dependents (failure cascades widely)
    - No dates: task has no schedule (planning risk)
    - Short description: vague task titles suggest unclear scope

    The core dependency engine remains fully deterministic.
    """
    critical_set = set(critical_path)
    risk_items = []

    # Build quick lookup
    in_degree: dict[str, int] = {}
    out_degree: dict[str, int] = {}
    for node in nodes:
        in_degree[node["id"]] = 0
        out_degree[node["id"]] = 0
    for edge in edges:
        out_degree[edge["source"]] = out_degree.get(edge["source"], 0) + 1
        in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1

    for node in nodes:
        tid = node["id"]
        factors = []
        score = 0

        # Factor: Critical path membership
        if tid in critical_set:
            factors.append({
                "factor": "On critical path — delays directly impact project completion",
                "severity": "high",
            })
            score += 30

        # Factor: High fan-in (many prerequisites)
        fan_in = in_degree.get(tid, 0)
        if fan_in >= 3:
            factors.append({
                "factor": f"High fan-in ({fan_in} prerequisites) — many blocking dependencies",
                "severity": "high",
            })
            score += 25
        elif fan_in == 2:
            factors.append({
                "factor": f"Moderate fan-in ({fan_in} prerequisites)",
                "severity": "medium",
            })
            score += 10

        # Factor: High fan-out (many dependents)
        fan_out = out_degree.get(tid, 0)
        if fan_out >= 3:
            factors.append({
                "factor": f"High fan-out ({fan_out} dependents) — failure cascades widely",
                "severity": "high",
            })
            score += 25
        elif fan_out == 2:
            factors.append({
                "factor": f"Moderate fan-out ({fan_out} dependents)",
                "severity": "medium",
            })
            score += 10

        # Factor: No schedule dates
        if not node.get("start_date") and not node.get("end_date"):
            factors.append({
                "factor": "No schedule dates assigned — planning risk",
                "severity": "medium",
            })
            score += 15

        # Factor: Short/vague title
        title = node.get("title", "")
        if len(title) < 15:
            factors.append({
                "factor": "Short task title — may indicate unclear scope",
                "severity": "low",
            })
            score += 5

        score = min(100, score)

        if factors:
            risk_items.append({
                "task_id": tid,
                "task_title": node.get("title", ""),
                "risk_score": score,
                "factors": factors,
                "on_critical_path": tid in critical_set,
            })

    # Sort by risk score descending
    risk_items.sort(key=lambda x: x["risk_score"], reverse=True)
    return risk_items
