"""Populated judge registry.

This module owns the fully initialized JUDGE_REGISTRY singleton.
Importing this module guarantees a populated registry without
requiring side-effect imports of CLI or other unrelated modules.

Usage:
    from trace_eval.judges.registry import JUDGE_REGISTRY

    judge = JUDGE_REGISTRY.get("reliability")
    result = judge(events)
"""

from trace_eval.judges.context import judge_context
from trace_eval.judges.efficiency import judge_efficiency
from trace_eval.judges.reliability import judge_reliability
from trace_eval.judges.retrieval import judge_retrieval
from trace_eval.judges.tool_discipline import judge_tool_discipline
from trace_eval.registry import JudgeRegistry

# ---------------------------------------------------------------------------
# Populated singleton — order is explicit and stable
# ---------------------------------------------------------------------------

JUDGE_REGISTRY = JudgeRegistry()

JUDGE_REGISTRY.register(
    dimension_key="reliability",
    judge=judge_reliability,
    display_label="Reliability",
    order=0,
)

JUDGE_REGISTRY.register(
    dimension_key="efficiency",
    judge=judge_efficiency,
    display_label="Efficiency",
    order=1,
)

JUDGE_REGISTRY.register(
    dimension_key="retrieval",
    judge=judge_retrieval,
    display_label="Retrieval",
    order=2,
)

JUDGE_REGISTRY.register(
    dimension_key="tool_discipline",
    judge=judge_tool_discipline,
    display_label="Tool Discipline",
    order=3,
)

JUDGE_REGISTRY.register(
    dimension_key="context",
    judge=judge_context,
    display_label="Context",
    order=4,
)

# Seal to prevent accidental mutation of built-in registrations
JUDGE_REGISTRY.seal()
