"""LangGraph orchestration of the 8-agent pipeline.

The graph defines an explicit, inspectable DAG:

    collect → deduplicate → classify → rank → summarize → report → email

Each node mutates a shared ``PipelineState``. If LangGraph is unavailable at
runtime, ``run_pipeline`` falls back to an equivalent sequential executor so the
system never hard-depends on the orchestrator being importable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.agents import (
    classification,
    collector,
    deduplication,
    email as email_agent,
    ranking,
    report as report_agent,
    summarization,
)
from app.core.logging import get_logger

log = get_logger(__name__)


class PipelineState(TypedDict, total=False):
    send_email: bool
    stats: dict[str, Any]
    report_id: int | None
    started_at: str


# --------------------------------------------------------------------------- #
# Nodes (each takes the shared state + an injected db session)
# --------------------------------------------------------------------------- #
def _node_collect(db: Session, state: PipelineState) -> PipelineState:
    state.setdefault("stats", {})["collect"] = collector.collect(db)
    return state


def _node_dedup(db: Session, state: PipelineState) -> PipelineState:
    state["stats"]["deduplicate"] = deduplication.deduplicate(db)
    return state


def _node_classify(db: Session, state: PipelineState) -> PipelineState:
    state["stats"]["classify"] = classification.classify(db)
    return state


def _node_rank(db: Session, state: PipelineState) -> PipelineState:
    state["stats"]["rank"] = ranking.rank(db)
    return state


def _node_summarize(db: Session, state: PipelineState) -> PipelineState:
    state["stats"]["summarize"] = summarization.summarize(db)
    return state


def _node_report(db: Session, state: PipelineState) -> PipelineState:
    report = report_agent.generate(db, kind="daily")
    state["report_id"] = report.id
    state["stats"]["report"] = {"report_id": report.id, "events": report.event_count}
    return state


def _node_email(db: Session, state: PipelineState) -> PipelineState:
    if not state.get("send_email", True):
        state["stats"]["email"] = {"skipped": True}
        return state
    from app.db.models import Report

    report = db.get(Report, state["report_id"])
    # Primary deliverable: the branded PDF brief to the configured recipient.
    brief = email_agent.send_daily_brief(db, report)
    # Plus per-user HTML digests for any registered users with email enabled.
    digests = email_agent.send_reports(db, report)
    state["stats"]["email"] = {"brief": brief, "digests": digests}
    return state


_STAGES = [
    ("collect", _node_collect),
    ("deduplicate", _node_dedup),
    ("classify", _node_classify),
    ("rank", _node_rank),
    ("summarize", _node_summarize),
    ("report", _node_report),
    ("email", _node_email),
]


def build_graph(db: Session):
    """Construct the LangGraph StateGraph (returns a compiled graph or None)."""
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:  # noqa: BLE001
        log.warning("langgraph_unavailable", error=str(exc))
        return None

    graph = StateGraph(PipelineState)
    for name, fn in _STAGES:
        graph.add_node(name, (lambda f: (lambda s: f(db, s)))(fn))

    graph.add_edge(START, _STAGES[0][0])
    for (prev, _), (nxt, _) in zip(_STAGES, _STAGES[1:], strict=False):
        graph.add_edge(prev, nxt)
    graph.add_edge(_STAGES[-1][0], END)
    return graph.compile()


def run_pipeline(db: Session, *, send_email: bool = True) -> dict:
    state: PipelineState = {
        "send_email": send_email,
        "stats": {},
        "report_id": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    compiled = build_graph(db)
    if compiled is not None:
        result = compiled.invoke(state)
        log.info("pipeline_complete_langgraph", report_id=result.get("report_id"))
        return dict(result.get("stats", {})) | {"report_id": result.get("report_id")}

    # Sequential fallback
    log.info("pipeline_running_sequential_fallback")
    for name, fn in _STAGES:
        state = fn(db, state)
    return dict(state.get("stats", {})) | {"report_id": state.get("report_id")}
