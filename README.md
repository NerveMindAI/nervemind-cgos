# nervemind-cgos

Enterprise runtime governance SDK for supervised AI systems, policy-controlled execution, and operational oversight infrastructure.

**NerveMind CGOS** enables organizations to integrate runtime governance, human oversight, governance-aware execution workflows, and controlled operational decisioning into enterprise AI environments.

## Key capabilities

- Runtime governance APIs
- Policy-controlled execution workflows
- Human-in-the-loop escalation
- Governance telemetry and audit visibility
- Tenant-scoped governance operations
- Multi-agent runtime supervision
- Controlled execution authorization
- Enterprise operational oversight

## Install

```bash
pip install nervemind-cgos
```

For local development from source:

```bash
git clone https://github.com/nervemind/nervemind-cgos.git
cd nervemind-cgos
pip install -e .
```

## Quick start

```python
from cgos_sdk import CGOSClient

client = CGOSClient(
    base_url="https://your-governance-api.example.com",
    api_key="your-tenant-api-key",
    internal_service_token="...",  # for verify_proof / invoke_execution (S2S)
)

out = client.submit_decision(
    source_system="core-payments",
    sector="banking",
    decision_type="limit_increase",
    decision_id="dec-001",
    context={"amount": 5000},
    policy_set="ORGANIZATION_POLICY_V1",
    callback_url="https://your-enterprise.example/callbacks/cgos",
    correlation_id="trace-abc",
)

proof_check = client.verify_proof(out.get("proof_id") or "prf_...")
exec_resp = client.invoke_execution(
    proof_id="prf_...",
    path="/api/v1/payments/transfer",
    organization_id="org_123",
    http_method="POST",
    json_body={"to": "x", "amount": 1},
)
```

## Authentication

| Call | Header |
|------|--------|
| Decision intake (v2) | `X-API-Key` or `Authorization: Bearer <api_key>` |
| Proof validate / execution | `X-CGOS-Internal-Token` (service-to-service) |

Optional **bearer JWT** (operator sessions) enables `wait_for_decision()` polling on `GET /api/v1/cgos/decisions/{id}`. Production integrations should prefer **callback URLs** over polling.

## Reliability

`CGOSClient` supports configurable `timeout_s`, `max_retries`, `Idempotency-Key` on intake, and optional `traceparent` / `correlation_id` on every request for governance telemetry continuity.

## Operational boundaries

This SDK integrates with the **NerveMind CGOS Runtime Governance control plane**. It provides governance infrastructure integration — not autonomous legal interpretation, regulatory certification, or compliance guarantees unless explicitly defined in your enterprise agreement.

Pair SDK usage with your organization's policy lifecycle, human oversight workflows, and audit export processes. For external attestation patterns (SPIFFE, signed policy bundles, CI validators), see NerveMind CGOS enterprise documentation.

## Documentation

- [NerveMind CGOS Documentation](https://nervemindos.com/resources/documentation)
- [Integration Guides](https://nervemindos.com/developers/integration-guides)
- [API Reference](https://nervemindos.com/developers/api-reference)

## Support

**Developed by NerveMind AI, Inc.**

- Email: [support@nervemindai.com](mailto:support@nervemindai.com)
- Repository: [https://github.com/nervemind/nervemind-cgos](https://github.com/nervemind/nervemind-cgos)

## License

MIT License — see [LICENSE](LICENSE). Use of NerveMind CGOS cloud services is subject to your organization's service or enterprise agreement.
