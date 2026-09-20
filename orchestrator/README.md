# AI Orchestrator V1

The orchestrator sits above the deterministic engineering skill registry and job lifecycle.

## Current flow

Natural-language request
→ intent routing
→ fact extraction
→ registered-skill validation
→ missing-input questions
→ job creation
→ deterministic engineering execution
→ human review
→ approval / dispatch

## Provider boundary

`orchestrator/provider.py` defines a provider-neutral structured-intent contract. The V1 default is an auditable rule-based router. A future Tasklet/OpenAI/other agent provider can implement the same contract without changing the engineering skills, queue, tenant model, or human-review workflow.

## HTTP intake

`POST /v1/intake`

Example:

```json
{
  "message": "Size a round duct for 8000 CFM using velocity at 7 m/s",
  "inputs": {"material": "gss"},
  "project_context": {"site": "Delhi"},
  "standards_context": {"standards": []},
  "assumptions_context": {}
}
```

The response contains both the orchestration plan and the created job.

The orchestrator never performs engineering calculations itself. It asks the registered deterministic skill what inputs it still requires, then routes the job to that skill.

## Optional OpenAI provider

Set `ENGINEERING_AI_INTENT_PROVIDER=openai` and configure `OPENAI_API_KEY` to use the
OpenAI-backed intent/extraction provider. `ENGINEERING_AI_MODEL` can override the model.
Without that setting, the platform remains on the deterministic rule-based router.

The provider is constrained to structured JSON intent extraction. It does not perform
engineering calculations; registered deterministic skills remain the calculation authority.
