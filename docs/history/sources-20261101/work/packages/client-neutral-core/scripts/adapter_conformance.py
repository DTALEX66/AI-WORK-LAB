from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


OPERATIONS = ("detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback")


@runtime_checkable
class AdapterProtocol(Protocol):
    def detect(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def capabilities(self) -> dict[str, Any]: ...
    def plan(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def apply(self, plan: dict[str, Any]) -> dict[str, Any]: ...
    def invoke(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def observe(self, request: dict[str, Any]) -> dict[str, Any]: ...
    def rollback(self, plan: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class FakeAdapter:
    adapter_id: str

    def detect(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"status": "DETECTED", "adapter_id": self.adapter_id, "evidence_state": "ISOLATED"}

    def capabilities(self) -> dict[str, Any]:
        return {"status": "CAPABILITIES_READ", "adapter_id": self.adapter_id, "operations": list(OPERATIONS)}

    def plan(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "WAITING_APPROVAL",
            "plan_id": f"plan-{request['task_id']}",
            "task_id": request["task_id"],
            "approval": {"required": True, "status": "PENDING"},
            "steps": [{"action": request["action"], "external_mutation": True}],
            "rollback": {"available": True, "status": "READY"},
        }

    def apply(self, plan: dict[str, Any]) -> dict[str, Any]:
        approval = plan.get("approval", {})
        if approval.get("required") is not True or approval.get("status") != "APPROVED":
            raise PermissionError("approval required before apply")
        return {"status": "APPLIED", "plan_id": plan["plan_id"], "external_mutation": True}

    def invoke(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"status": "INVOKED", "run_id": request["run_id"], "task_id": request["task_id"]}

    def observe(self, request: dict[str, Any]) -> dict[str, Any]:
        return {"status": "OBSERVED", "run_id": request["run_id"], "events": []}

    def rollback(self, plan: dict[str, Any]) -> dict[str, Any]:
        return {"status": "ROLLED_BACK", "plan_id": plan["plan_id"], "external_mutation": True}


def run_conformance(adapter: AdapterProtocol) -> dict[str, Any]:
    missing = [name for name in OPERATIONS if not callable(getattr(adapter, name, None))]
    if missing:
        return {
            "passed": False,
            "operations": list(OPERATIONS),
            "missing_operations": missing,
            "evidence_state": "ISOLATED_FAIL",
        }
    request = {"task_id": "conformance-task", "run_id": "conformance-run", "action": "write"}
    capabilities = adapter.capabilities()
    advertised = set(capabilities.get("operations", []))
    plan = adapter.plan(request)
    if plan.get("approval", {}).get("required") is not True or plan.get("status") != "WAITING_APPROVAL":
        return {"passed": False, "operations": list(OPERATIONS), "missing_operations": [], "evidence_state": "ISOLATED_FAIL"}
    approved = {**plan, "approval": {**plan["approval"], "status": "APPROVED"}}
    if "apply" in advertised:
        try:
            adapter.apply(plan)
        except PermissionError:
            pass
        else:
            return {"passed": False, "operations": list(OPERATIONS), "missing_operations": [], "evidence_state": "ISOLATED_FAIL"}
        apply_result = adapter.apply(approved)
        if apply_result.get("status") == "UNSUPPORTED":
            return {"passed": False, "operations": list(OPERATIONS), "missing_operations": [], "evidence_state": "ISOLATED_FAIL"}
    else:
        apply_result = adapter.apply(approved)
        if apply_result.get("status") != "UNSUPPORTED":
            return {"passed": False, "operations": list(OPERATIONS), "missing_operations": [], "evidence_state": "ISOLATED_FAIL"}
    invoke_result = adapter.invoke(request)
    rollback_result = adapter.rollback(approved)
    for operation, result in (("invoke", invoke_result), ("rollback", rollback_result)):
        if operation not in advertised and result.get("status") != "UNSUPPORTED":
            return {"passed": False, "operations": list(OPERATIONS), "missing_operations": [], "evidence_state": "ISOLATED_FAIL"}
    results = {
        "detect": adapter.detect(request),
        "capabilities": capabilities,
        "plan": plan,
        "apply": apply_result,
        "invoke": invoke_result,
        "observe": adapter.observe(request),
        "rollback": rollback_result,
    }
    if any(not isinstance(result, dict) or not result.get("status") for result in results.values()):
        return {"passed": False, "operations": list(OPERATIONS), "missing_operations": [], "evidence_state": "ISOLATED_FAIL"}
    return {
        "passed": True,
        "operations": list(OPERATIONS),
        "missing_operations": [],
        "evidence_state": "ISOLATED_PASS",
        "results": results,
    }
