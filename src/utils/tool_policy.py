"""Confirmation policy for MCP tools.

The policy is intentionally conservative: unknown actions are treated as writes
unless config says otherwise. This keeps newly inherited upstream tools from
becoming automatically mutable by accident.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIRMATION_KEYS = {
    "confirm",
    "confirmed",
    "confirmation",
    "confirmation_operation_id",
    "operation_id",
    "preview",
    "dry_run",
    "reason",
}


@dataclass(frozen=True)
class PolicyDecision:
    """Result of checking a tool call against the configured safety policy."""

    allowed: bool
    risk: str
    operation_id: str
    response: dict[str, Any] | None = None


def default_policy_path() -> Path:
    """Return the repo-local policy file path."""

    return Path(__file__).resolve().parents[2] / "config" / "tool_policy.json"


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    """Load the tool policy JSON."""

    policy_path = Path(path) if path is not None else default_policy_path()
    with policy_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sanitize_params(value: Any) -> Any:
    """Remove confirmation-only fields before hashing an operation."""

    if isinstance(value, dict):
        return {
            key: sanitize_params(item)
            for key, item in sorted(value.items())
            if key not in CONFIRMATION_KEYS
        }
    if isinstance(value, list):
        return [sanitize_params(item) for item in value]
    return value


def operation_id(tool_name: str, action: str, params: dict[str, Any] | None) -> str:
    """Return a stable operation id for a tool/action/params tuple."""

    payload = {
        "tool": tool_name,
        "action": action,
        "params": sanitize_params(params or {}),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def classify_action(policy: dict[str, Any], tool_name: str, action: str) -> str:
    """Classify a tool action as read, write, delete, or dangerous."""

    tool_policy = policy.get("tools", {}).get(tool_name, {})
    if action in tool_policy.get("read_actions", []):
        return "read"
    if action in tool_policy.get("dangerous_actions", []):
        return "dangerous"
    if action in tool_policy.get("delete_actions", []):
        return "delete"
    if action in tool_policy.get("write_actions", []):
        return "write"
    return str(policy.get("default_risk", "write"))


def _requested_operation_id(params: dict[str, Any]) -> str | None:
    confirmation = params.get("confirmation")
    if isinstance(confirmation, dict):
        value = confirmation.get("operation_id")
        if value:
            return str(value)
    for key in ("confirmation_operation_id", "operation_id"):
        value = params.get(key)
        if value:
            return str(value)
    return None


def check_tool_call(
    policy: dict[str, Any],
    tool_name: str,
    action: str,
    params: dict[str, Any] | None,
) -> PolicyDecision:
    """Return whether a tool call is allowed under the policy."""

    call_params = params or {}
    risk = classify_action(policy, tool_name, action)
    op_id = operation_id(tool_name, action, call_params)
    confirmation = policy.get("confirmation", {})
    require_for_risks = set(confirmation.get("require_for_risks", []))
    allowlisted = set(confirmation.get("allowlisted_writes", []))
    tool_action = f"{tool_name}.{action}"

    if risk == "read" or tool_action in allowlisted:
        return PolicyDecision(allowed=True, risk=risk, operation_id=op_id)

    if risk not in require_for_risks:
        return PolicyDecision(allowed=True, risk=risk, operation_id=op_id)

    if not bool(call_params.get("confirm") or call_params.get("confirmed")):
        return PolicyDecision(
            allowed=False,
            risk=risk,
            operation_id=op_id,
            response={
                "requires_confirmation": True,
                "risk": risk,
                "tool": tool_name,
                "action": action,
                "operation_id": op_id,
                "preview": {
                    "tool": tool_name,
                    "action": action,
                    "params": sanitize_params(call_params),
                },
                "message": (
                    "This Resolve operation is not read-only. Re-run with "
                    "confirm=true and the same operation_id to apply it."
                ),
            },
        )

    requested_id = _requested_operation_id(call_params)
    if requested_id != op_id:
        return PolicyDecision(
            allowed=False,
            risk=risk,
            operation_id=op_id,
            response={
                "error": "Confirmation operation_id does not match this operation.",
                "expected_operation_id": op_id,
                "received_operation_id": requested_id,
                "risk": risk,
            },
        )

    return PolicyDecision(allowed=True, risk=risk, operation_id=op_id)

