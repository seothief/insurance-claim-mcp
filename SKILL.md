---
name: insurance-claim-mcp
description: Deterministic AI insurance claim assistant via Model Context Protocol (MCP). Reconciles unstructured medical receipts and diagnosis codes (KCD) against registered insurance policy terms with zero-hallucination, fail-closed mathematical rule evaluation.
---

# Insurance Claim MCP Assistant

This skill provides complete operational guidelines for connecting to, querying, and deploying the **insurance-claim-mcp** service.

## When to Use This Skill
- Extracting medical events (hospital admission/outpatient, injury vs disease, treatment codes, hospital tiers) and calculating estimated insurance claim payouts.
- Registering insurance policies, coverage limits, and rider terms with automated fail-closed validation.
- Interacting with the FastMCP service over Streamable HTTP (`/mcp`) or local stdio.

---

## 1. Architectural Philosophy: Decoupled AI & Rules Engine

```mermaid
flowchart LR
    A["Raw Document\n(Receipt / Policy Image)"] --> B["LLM Agent\n(Perception & Extraction)"]
    B --> C["FastMCP Protocol\n(Tools & Resources)"]
    C --> D["Deterministic Rules Engine\n(Fail-Closed Pure Math)"]
    D --> E["Auditable Output\n(Zero Math Hallucination)"]
```

- **Perception (LLM)**: Reads unstructured receipts, medical bills, and policy certificate images to extract standardized fields (e.g. KCD diagnosis codes, admission days, treatment amounts).
- **Computation (Rules Engine)**: Deterministic evaluation using pure Python functions.
- **Fail-Closed Principle**: Any unverified rider (`verified=false`) or missing clinical fact returns `NOT_EVALUATED` ($0 payout)—never an estimated guess.

---

## 2. MCP Surface (Tools, Resources, Prompts)

### Tools (11)
- `register_user`: Create a new user profile with PBKDF2 PIN.
- `register_user_policy`: Register an insurance policy and its riders.
- `resolve_user_rider`: Reconcile unmapped riders with the standard catalog.
- `evaluate_claim`: Calculate deterministic claim benefits against active policies.
- `list_user_policies`: Retrieve registered user policies and rider terms.
- `delete_user_policy`: Safely delete a registered policy.
- `list_standard_rules`: View standard coverage rules and deductible limits.

### Resources (3)
- `insurance://guide/onboarding`: Step-by-step onboarding walkthrough.
- `insurance://rules/standard`: Canonical coverage catalog.
- `insurance://guide/document-request/{policy_type}/{product_name}`: Dynamic template for insurer document requests.

### Prompts (1)
- `insurance_assistant_prompt`: Standard orchestrator prompt for multi-turn claim analysis.

---

## 3. Client Configuration

### Claude Code / Cursor / Windsurf Configuration
Add the server configuration to your `mcp_config.json`:

```json
{
  "mcpServers": {
    "insurance-claim": {
      "serverUrl": "https://<YOUR-CLOUD-RUN-URL>/mcp",
      "headers": {
        "X-User-Key": "<USER_SECRET_KEY>"
      }
    }
  }
}
```

For local stdio execution:
```json
{
  "mcpServers": {
    "insurance-claim-local": {
      "command": "python",
      "args": ["-m", "claim_service.mcp.server"]
    }
  }
}
```

---

## 4. Verification & Testing
Before making changes, always ensure the test suite and static analyzers pass:
```bash
python -m pytest -q
python -m ruff check src tests scripts
python -m mypy src
```
