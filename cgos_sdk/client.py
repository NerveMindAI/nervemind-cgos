"""
CGOS HTTP client — intake v2, proof validate, execution invoke.

Intended ergonomics: submit_decision() → verify_proof() → invoke_execution()
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

import requests

log = logging.getLogger("cgos_sdk")


class CGOSError(Exception):
    """HTTP or contract error from CGOS."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CGOSClient:
    def __init__(
        self,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        internal_service_token: Optional[str] = None,
        bearer_token: Optional[str] = None,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        session: Optional[requests.Session] = None,
        user_agent: str = "nervemind-cgos/0.1.0",
        trace_hook: Optional[Callable[[str, str, int, float], None]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = (api_key or "").strip() or None
        self.internal_service_token = (internal_service_token or "").strip() or None
        self.bearer_token = (bearer_token or "").strip() or None
        self.timeout_s = timeout_s
        self.max_retries = max(0, int(max_retries))
        self._session = session or requests.Session()
        self.user_agent = user_agent
        self.trace_hook = trace_hook

    def _headers(
        self,
        *,
        for_intake: bool = False,
        for_internal: bool = False,
        idempotency_key: Optional[str] = None,
        correlation_id: Optional[str] = None,
        traceparent: Optional[str] = None,
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json", "User-Agent": self.user_agent}
        if for_intake and self.api_key:
            h["X-API-Key"] = self.api_key
        elif for_intake and self.bearer_token:
            h["Authorization"] = f"Bearer {self.bearer_token}"
        if for_internal:
            if self.internal_service_token:
                h["X-CGOS-Internal-Token"] = self.internal_service_token
            elif self.bearer_token and not for_intake:
                h["Authorization"] = f"Bearer {self.bearer_token}"
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        if correlation_id:
            h["X-Correlation-ID"] = correlation_id
        if traceparent:
            h["traceparent"] = traceparent
        if extra:
            h.update(extra)
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        hdrs = dict(headers or {})
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                r = self._session.request(
                    method,
                    url,
                    json=json,
                    headers=hdrs,
                    timeout=self.timeout_s,
                )
                elapsed = time.perf_counter() - t0
                if self.trace_hook:
                    self.trace_hook(method, url, r.status_code, elapsed)
                if r.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(0.25 * (2**attempt))
                    continue
                return r
            except requests.RequestException as e:
                last_exc = e
                if attempt < self.max_retries:
                    time.sleep(0.25 * (2**attempt))
                    continue
                raise CGOSError(f"request failed: {e}") from e
        raise CGOSError(f"request failed after retries: {last_exc}")

    def _raise_for_status(self, r: requests.Response, ctx: str) -> None:
        if r.status_code < 400:
            return
        body = r.text[:4000] if r.text else ""
        raise CGOSError(
            f"{ctx} failed: HTTP {r.status_code}",
            status_code=r.status_code,
            body=body,
        )

    def submit_decision(
        self,
        *,
        source_system: str,
        sector: str,
        decision_type: str,
        decision_id: str,
        context: Dict[str, Any],
        policy_set: str,
        callback_url: str,
        priority: Optional[str] = None,
        sla_seconds: Optional[int] = None,
        correlation_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        traceparent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/cgos/v2/decisions (EXTERNAL_GOVERNED). Requires API key (or bearer)."""
        if not self.api_key and not self.bearer_token:
            raise CGOSError("submit_decision requires api_key or bearer_token")
        body = {
            "decision_class": "EXTERNAL_GOVERNED",
            "source_system": source_system,
            "sector": sector,
            "decision_type": decision_type,
            "decision_id": decision_id,
            "context": context or {},
            "policy_set": policy_set,
            "callback_url": callback_url,
            "priority": priority,
            "sla_seconds": sla_seconds,
            "correlation_id": correlation_id,
        }
        hdrs = self._headers(
            for_intake=True,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            traceparent=traceparent,
        )
        r = self._request("POST", "/api/v1/cgos/v2/decisions", json=body, headers=hdrs)
        self._raise_for_status(r, "submit_decision")
        return r.json()

    def verify_proof(
        self,
        proof_id: str,
        *,
        organization_id: Optional[str] = None,
        intended_action: Optional[Dict[str, Any]] = None,
        traceparent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/cgos/internal/proofs/validate — requires internal token."""
        if not self.internal_service_token:
            raise CGOSError("verify_proof requires internal_service_token")
        body: Dict[str, Any] = {"proof_id": proof_id}
        if organization_id:
            body["organization_id"] = organization_id
        if intended_action is not None:
            body["intended_action"] = intended_action
        hdrs = self._headers(for_internal=True, traceparent=traceparent)
        r = self._request("POST", "/api/v1/cgos/internal/proofs/validate", json=body, headers=hdrs)
        self._raise_for_status(r, "verify_proof")
        return r.json()

    def mint_proof_token(
        self,
        proof_id: str,
        *,
        organization_id: Optional[str] = None,
        intended_action: Optional[Dict[str, Any]] = None,
        traceparent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """POST /api/v1/cgos/internal/proofs/token — HS256 for core-local checks."""
        if not self.internal_service_token:
            raise CGOSError("mint_proof_token requires internal_service_token")
        body: Dict[str, Any] = {"proof_id": proof_id}
        if organization_id:
            body["organization_id"] = organization_id
        if intended_action is not None:
            body["intended_action"] = intended_action
        hdrs = self._headers(for_internal=True, traceparent=traceparent)
        r = self._request("POST", "/api/v1/cgos/internal/proofs/token", json=body, headers=hdrs)
        self._raise_for_status(r, "mint_proof_token")
        return r.json()

    def invoke_execution(
        self,
        *,
        proof_id: str,
        path: str,
        organization_id: Optional[str] = None,
        http_method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        intended_action: Optional[Dict[str, Any]] = None,
        traceparent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /api/v1/cgos/execution/invoke — proof-gated forward to bank core.
        Prefer internal_service_token + organization_id for gateway-style calls.
        """
        if not self.internal_service_token and not self.api_key and not self.bearer_token:
            raise CGOSError("invoke_execution requires internal_service_token, api_key, or bearer_token")
        body: Dict[str, Any] = {
            "proof_id": proof_id,
            "path": path,
            "http_method": http_method,
            "headers": headers,
            "json_body": json_body,
            "intended_action": intended_action,
        }
        if organization_id:
            body["organization_id"] = organization_id
        base = {"traceparent": traceparent} if traceparent else {}
        if self.internal_service_token:
            hdrs = {**base, "Content-Type": "application/json", "User-Agent": self.user_agent}
            hdrs["X-CGOS-Internal-Token"] = self.internal_service_token
        elif self.api_key:
            hdrs = self._headers(for_intake=True, traceparent=traceparent)
        else:
            hdrs = {**base, "Content-Type": "application/json", "User-Agent": self.user_agent, "Authorization": f"Bearer {self.bearer_token}"}
        r = self._request("POST", "/api/v1/cgos/execution/invoke", json=body, headers=hdrs)
        self._raise_for_status(r, "invoke_execution")
        return r.json()

    def verify_auth(self) -> Dict[str, Any]:
        """GET /api/v1/cgos/decision/auth/verify — API key sanity check."""
        if not self.api_key and not self.bearer_token:
            raise CGOSError("verify_auth requires api_key or bearer_token")
        hdrs = self._headers(for_intake=True)
        r = self._request("GET", "/api/v1/cgos/decision/auth/verify", headers=hdrs)
        self._raise_for_status(r, "verify_auth")
        return r.json()

    def get_decision(self, decision_internal_id: str) -> Dict[str, Any]:
        """GET /api/v1/cgos/decisions/{id} — requires admin JWT (bearer_token)."""
        if not self.bearer_token:
            raise CGOSError("get_decision requires bearer_token (admin UI JWT)")
        hdrs = self._headers(for_intake=True)
        r = self._request("GET", f"/api/v1/cgos/decisions/{decision_internal_id}", headers=hdrs)
        self._raise_for_status(r, "get_decision")
        return r.json()

    def wait_for_decision(
        self,
        decision_internal_id: str,
        *,
        terminal_statuses: Optional[List[str]] = None,
        poll_interval_s: float = 2.0,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Poll get_decision until status settles. Requires bearer_token.
        External integrators should prefer callback_url instead of polling.
        """
        terminal = {s.upper() for s in (terminal_statuses or ["APPROVED", "REJECTED", "CONDITIONAL", "CALLBACK_SENT"])}
        deadline = None if timeout_s is None else (time.monotonic() + float(timeout_s))
        while True:
            d = self.get_decision(decision_internal_id)
            st = str(d.get("status") or "").upper()
            fs = str(d.get("final_status") or "").upper()
            if st in terminal or fs in terminal:
                return d
            if deadline is not None and time.monotonic() > deadline:
                raise CGOSError(f"wait_for_decision timeout after {timeout_s}s")
            time.sleep(poll_interval_s)
