from datetime import datetime, timezone
from threading import RLock
from typing import Any

from services.persistence import repository


class TokenTracker:
    def __init__(self):
        self._lock = RLock()
        self._calls: dict[str, list[dict[str, Any]]] = {}

    def record(self, session_id: str, record: dict) -> dict:
        with self._lock:
            calls = self._calls.setdefault(session_id, [])
            calls.append(record)

            by_agent: dict[str, dict] = {}
            for call in calls:
                agent = call["agent_name"]
                stats = by_agent.setdefault(agent, {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                })
                stats["input_tokens"] += call["input_tokens"]
                stats["output_tokens"] += call["output_tokens"]
                stats["total_tokens"] += call["total_tokens"]
                stats["cost"] += call["cost"]

            summary = {
                "calls": list(calls),
                "per_agent": by_agent,
                "total_input_tokens": sum(
                    x["input_tokens"] for x in calls
                ),
                "total_output_tokens": sum(
                    x["output_tokens"] for x in calls
                ),
                "total_tokens": sum(
                    x["total_tokens"] for x in calls
                ),
                "total_cost": round(
                    sum(x["cost"] for x in calls), 8
                ),
            }

            repository.save("token_usage", session_id, summary)
            return summary

    def get(self, session_id: str) -> dict:
        with self._lock:
            if session_id in self._calls:
                calls = list(self._calls[session_id])
            else:
                stored = repository.load("token_usage", session_id)
                if stored:
                    return stored
                calls = []

        by_agent: dict[str, dict] = {}
        for call in calls:
            stats = by_agent.setdefault(call["agent_name"], {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
            })
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                stats[key] += call[key]
            stats["cost"] += call["cost"]

        return {
            "calls": calls,
            "per_agent": by_agent,
            "total_input_tokens": sum(c["input_tokens"] for c in calls),
            "total_output_tokens": sum(c["output_tokens"] for c in calls),
            "total_tokens": sum(c["total_tokens"] for c in calls),
            "total_cost": round(sum(c["cost"] for c in calls), 8),
        }


token_tracker = TokenTracker()