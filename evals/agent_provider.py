"""Promptfoo Python Provider for LifeSandbox LangGraph Agent.

Enables evaluation and regression tracking of agent prompts, intent routing,
skill detection, tool execution, and guardrail compliance.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

# Ensure project root is in sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Safe defaults for eval runs
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("AUTH_MODE", "development")


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        try:
            import importlib

            nest_asyncio = importlib.import_module("nest_asyncio")
            nest_asyncio.apply()
        except ImportError:
            pass
        return loop.run_until_complete(coro)
    return asyncio.run(coro)


async def _execute_agent(
    prompt: str, options: dict[str, Any] | None = None, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    options = options or {}
    context = context or {}
    config = options.get("config", {})
    vars_dict = context.get("vars", {})

    mode = config.get("mode", os.environ.get("LLM_PROVIDER", "mock"))
    os.environ["LLM_PROVIDER"] = mode

    from app.conversation.graph import ConversationState, conversation_graph, select_relevant_tools

    user_id = vars_dict.get("user_id", "eval-user")
    message = vars_dict.get("message") or prompt or ""
    history = vars_dict.get("history", [])
    memories = vars_dict.get("memories", [])
    allow_browser = vars_dict.get("allow_browser_use", False)

    # Authorized tools from relevant tool selector or explicit config
    authorized = list(select_relevant_tools(message))
    if "authorized_tools" in vars_dict:
        authorized = vars_dict["authorized_tools"]

    state: ConversationState = {
        "user_id": user_id,
        "conversation_id": str(uuid4()),
        "message": message,
        "history": history,
        "memories": memories,
        "file_context": vars_dict.get("file_context", ""),
        "image_inputs": [],
        "allow_browser_use": allow_browser,
        "authorized_tools": authorized,
        "tool_rounds": 0,
        "tool_calls": [],
    }

    start = time.perf_counter()
    try:
        result = await conversation_graph.ainvoke(state)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        reply = result.get("reply", "")
        tool_calls = result.get("agent_messages", [])
        invoked_tools = []
        for msg in tool_calls:
            if isinstance(msg, dict) and "tool_calls" in msg:
                for tc in msg.get("tool_calls", []):
                    invoked_tools.append(tc.get("function", {}).get("name"))

        return {
            "output": reply,
            "metadata": {
                "skill": result.get("skill"),
                "intent": result.get("intent"),
                "skill_trigger": result.get("skill_trigger"),
                "provider": result.get("provider", mode),
                "model": result.get("model", "unknown"),
                "invoked_tools": invoked_tools,
                "authorized_tools": authorized,
                "latency_ms": duration_ms,
            },
            "latencyMs": duration_ms,
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return {
            "error": f"Agent execution error: {exc}",
            "output": "",
            "metadata": {
                "error": str(exc),
                "latency_ms": duration_ms,
            },
            "latencyMs": duration_ms,
        }


def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo standard provider hook."""
    return _run_async(_execute_agent(prompt, options, context))


if __name__ == "__main__":
    import json

    # Support CLI invocation: python agent_provider.py "prompt" '{"config":{}}' '{"vars":{}}'
    prompt_arg = sys.argv[1] if len(sys.argv) > 1 else "Hello"
    options_arg = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    context_arg = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    res = call_api(prompt_arg, options_arg, context_arg)
    print(json.dumps(res, indent=2))
