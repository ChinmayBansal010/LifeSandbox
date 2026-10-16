import json
import logging
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import PromptTraceRow

logger = logging.getLogger("life_sandbox.tool_tracker")

_current_trace: ContextVar[dict[str, Any] | None] = ContextVar("current_trace", default=None)
_memory_traces: list[dict[str, Any]] = []
_MAX_MEMORY_TRACES = 200


def _serialize_safe(data: Any, max_len: int = 4000) -> Any:
    if data is None:
        return None
    if isinstance(data, (int, float, bool)):
        return data
    if isinstance(data, str):
        return data if len(data) <= max_len else data[:max_len] + "... [truncated]"
    try:
        dumped = json.dumps(data, default=str)
        if len(dumped) > max_len:
            return dumped[:max_len] + "... [truncated]"
        return json.loads(dumped)
    except Exception:
        return str(data)[:max_len]


@asynccontextmanager
async def trace_prompt(
    prompt: str,
    user_id: str,
    conversation_id: str | None = None,
    db: AsyncSession | None = None,
):
    trace_id = str(uuid4())
    start_time = datetime.now(UTC)
    t0 = time.perf_counter()
    trace_data: dict[str, Any] = {
        "id": trace_id,
        "prompt": prompt,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "status": "running",
        "started_at": start_time.isoformat(),
        "completed_at": None,
        "total_duration_ms": None,
        "tools_accessed": [],
        "response_preview": None,
        "error": None,
    }

    token = _current_trace.set(trace_data)
    _memory_traces.insert(0, trace_data)
    if len(_memory_traces) > _MAX_MEMORY_TRACES:
        _memory_traces.pop()

    try:
        yield trace_data
        trace_data["status"] = "completed"
    except Exception as exc:
        trace_data["status"] = "failed"
        trace_data["error"] = str(exc)
        raise
    finally:
        t1 = time.perf_counter()
        end_time = datetime.now(UTC)
        duration_ms = round((t1 - t0) * 1000, 2)
        trace_data["completed_at"] = end_time.isoformat()
        trace_data["total_duration_ms"] = duration_ms
        _current_trace.reset(token)

        if db is not None:
            try:
                row = PromptTraceRow(
                    id=trace_id,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    prompt=prompt,
                    status=trace_data["status"],
                    started_at=start_time,
                    completed_at=end_time,
                    total_duration_ms=duration_ms,
                    tools_accessed=json.dumps(trace_data["tools_accessed"]),
                    response_preview=trace_data.get("response_preview"),
                    error=trace_data.get("error"),
                )
                db.add(row)
                await db.commit()
            except Exception as exc:
                logger.warning("Could not persist prompt trace row to database: %s", exc)


@asynccontextmanager
async def trace_tool(
    tool_name: str,
    tool_type: str = "tool",
    input_data: Any = None,
):
    start_time = datetime.now(UTC)
    t0 = time.perf_counter()
    event: dict[str, Any] = {
        "id": str(uuid4()),
        "tool_name": tool_name,
        "tool_type": tool_type,
        "started_at": start_time.isoformat(),
        "completed_at": None,
        "duration_ms": 0.0,
        "input_data": _serialize_safe(input_data),
        "output_data": None,
        "status": "running",
        "error": None,
    }

    active_trace = _current_trace.get()
    if active_trace is not None:
        active_trace["tools_accessed"].append(event)

    try:
        yield event
        if event["status"] == "running":
            event["status"] = "success"
    except Exception as exc:
        event["status"] = "error"
        event["error"] = str(exc)
        raise
    finally:
        t1 = time.perf_counter()
        end_time = datetime.now(UTC)
        event["completed_at"] = end_time.isoformat()
        event["duration_ms"] = round((t1 - t0) * 1000, 2)


def get_current_trace() -> dict[str, Any] | None:
    return _current_trace.get()


async def get_traces(
    db: AsyncSession | None = None,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    tool_filter: str | None = None,
    status_filter: str | None = None,
) -> list[dict[str, Any]]:
    if db is not None:
        try:
            stmt = select(PromptTraceRow).order_by(desc(PromptTraceRow.started_at))
            if status_filter and status_filter != "all":
                stmt = stmt.where(PromptTraceRow.status == status_filter)
            rows = (await db.scalars(stmt.limit(100))).all()
            results = []
            for r in rows:
                tools = []
                try:
                    tools = json.loads(r.tools_accessed or "[]")
                except Exception:
                    pass
                skill, skill_trigger, intent = None, None, None
                for t in tools:
                    if t.get("tool_name") == "intent_classifier":
                        out = t.get("output_data") or {}
                        if isinstance(out, dict):
                            skill = out.get("skill")
                            skill_trigger = out.get("skill_trigger")
                            intent = out.get("intent")
                item = {
                    "id": r.id,
                    "user_id": r.user_id,
                    "conversation_id": r.conversation_id,
                    "prompt": r.prompt,
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "total_duration_ms": r.total_duration_ms,
                    "tools_accessed": tools,
                    "response_preview": r.response_preview,
                    "error": r.error,
                    "skill": skill,
                    "skill_trigger": skill_trigger,
                    "intent": intent,
                }
                results.append(item)

            if search:
                s = search.lower()
                results = [
                    x
                    for x in results
                    if s in (x.get("prompt") or "").lower()
                    or any(
                        s in (t.get("tool_name") or "").lower()
                        for t in x.get("tools_accessed", [])
                    )
                ]
            if tool_filter and tool_filter != "all":
                tf = tool_filter.lower()
                results = [
                    x
                    for x in results
                    if any(
                        tf in (t.get("tool_name") or "").lower()
                        for t in x.get("tools_accessed", [])
                    )
                ]
            return results[offset : offset + limit]
        except Exception as exc:
            logger.warning("Could not query traces from db, falling back to memory: %s", exc)

    filtered = _memory_traces
    if status_filter and status_filter != "all":
        filtered = [x for x in filtered if x.get("status") == status_filter]
    if search:
        s = search.lower()
        filtered = [
            x
            for x in filtered
            if s in (x.get("prompt") or "").lower()
            or any(s in (t.get("tool_name") or "").lower() for t in x.get("tools_accessed", []))
        ]
    if tool_filter and tool_filter != "all":
        tf = tool_filter.lower()
        filtered = [
            x
            for x in filtered
            if any(tf in (t.get("tool_name") or "").lower() for t in x.get("tools_accessed", []))
        ]
    return filtered[offset : offset + limit]


async def get_trace_by_id(trace_id: str, db: AsyncSession | None = None) -> dict[str, Any] | None:
    if db is not None:
        try:
            r = await db.scalar(select(PromptTraceRow).where(PromptTraceRow.id == trace_id))
            if r:
                tools = []
                try:
                    tools = json.loads(r.tools_accessed or "[]")
                except Exception:
                    pass
                skill, skill_trigger, intent = None, None, None
                for t in tools:
                    if t.get("tool_name") == "intent_classifier":
                        out = t.get("output_data") or {}
                        if isinstance(out, dict):
                            skill = out.get("skill")
                            skill_trigger = out.get("skill_trigger")
                            intent = out.get("intent")
                return {
                    "id": r.id,
                    "user_id": r.user_id,
                    "conversation_id": r.conversation_id,
                    "prompt": r.prompt,
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "total_duration_ms": r.total_duration_ms,
                    "tools_accessed": tools,
                    "response_preview": r.response_preview,
                    "error": r.error,
                    "skill": skill,
                    "skill_trigger": skill_trigger,
                    "intent": intent,
                }
        except Exception:
            pass

    for t in _memory_traces:
        if t.get("id") == trace_id:
            return t
    return None


async def clear_traces(db: AsyncSession | None = None):
    _memory_traces.clear()
    if db is not None:
        try:
            await db.execute(delete(PromptTraceRow))
            await db.commit()
        except Exception as exc:
            logger.warning("Could not clear traces from db: %s", exc)


async def get_stats(db: AsyncSession | None = None) -> dict[str, Any]:
    traces = await get_traces(db=db, limit=200)
    total_prompts = len(traces)
    total_tool_calls = sum(len(t.get("tools_accessed", [])) for t in traces)

    tool_counts: dict[str, int] = {}
    total_duration = 0.0
    duration_count = 0

    for t in traces:
        dur = t.get("total_duration_ms")
        if dur:
            total_duration += dur
            duration_count += 1
        for tool in t.get("tools_accessed", []):
            name = tool.get("tool_name", "unknown")
            tool_counts[name] = tool_counts.get(name, 0) + 1

    avg_duration = round(total_duration / duration_count, 1) if duration_count > 0 else 0.0

    return {
        "total_prompts": total_prompts,
        "total_tool_calls": total_tool_calls,
        "avg_duration_ms": avg_duration,
        "tool_breakdown": tool_counts,
    }
