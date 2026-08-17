# Where the submitted text lives

Submitted to the All Things Agentic Hackathon on 2026-08-17, Fortified
Enterprise Fleet track. Devpost propagates project edits to a submission that
is already in, so this is a floor rather than a deadline: everything below can
still be improved until 2026-09-01 07:00 GMT+7.

The project story is on Devpost and that is the only copy:

    https://devpost.com/software/palinode-ctrl-z-for-ai-agent-fleets

There used to be a `devpost-story.md` here as well. It drifted, which is how a
reviewer ended up quoting "five ADK agents" from this repository while the
submission said six, and while the truth was three. One story, one place.

## What is actually running, in one paragraph

Three ADK `LlmAgent`s make up the supervised fleet: sourcing, invoice and
payables, in `fleet/procurement.py`. Every tool call they make passes through
the Warden, which attaches to ADK's `before_tool_callback`.

The control plane is not built on ADK and does not pretend to be. Sentinel,
Sweeper, Regret, Verifier and Herald are plain Python classes in
`src/palinode/agents/`. They supervise ADK agents rather than being ADK
agents, which is the correct shape: a policy gate that is itself an LLM agent
is a policy gate that can be talked out of its policy.

## What is a Google product and what is our stand in

The Fortified Enterprise Fleet track names a set of Gemini Enterprise Agent
Platform services. Being exact about which of those we use matters more than
claiming coverage.

| The track names | What Palinode has |
|---|---|
| Model Armor | The real thing, on every tool call with prose in its arguments |
| Agent Observability | Real Cloud Trace, carrying our own OpenTelemetry spans |
| Agent Identity | **Our stand in.** A SPIFFE shaped id per agent, the same shape Agent Identity issues, so the ledger schema does not change when the issuer does |
| Agent Registry | **Our stand in.** `warden/registry.py`: identity, tool grants, blast radius budget, runtime mode |
| Agent Gateway | **Our stand in.** The Warden implements the same idea inline. Delegating to Gateway once it is out of private preview is the first thing to do next |
| Memory Bank | **Our stand in.** A Firestore causality graph, hash chained, which is a different thing from Memory Bank and better suited to reversal than to recall |
| Agent Runtime | **Partly.** Cloud Scheduler wakes the Sweeper hourly with no request in flight, which is the long running asynchronous part. Everything else finishes inside the request that started it |

None of the stand ins are presented as the Google product. Where the film or
the story says SPIFFE shaped, it means shaped like, not issued by.

## The form, field by field

Filled in by hand on Devpost. Kept here so the answers are decided once rather
than composed under time pressure at the form.

| Field | Answer |
|---|---|
| Submitter type | Organization |
| Country of residence | Thailand |
| Category | Fortified Enterprise Fleet |
| Organization name | Oro Shin |
| Start date | 08-14-26 |
| Code repo | https://github.com/thankywal/palinode |
| Reproducible testing in README | Yes |
| Hosted project URL | https://palinode-173485225974.us-central1.run.app |
| Google SDK | Agent Development Kit (ADK), Google GenAI SDK |
| Google Cloud services | Cloud Run, Firestore |
| Google AI models | Gemini 3.5 Flash, Lyria, Chirp3 HD, Speech to Text |
| Startup prize, organization | Oro Shin |
| Startup prize, corporate email | thankywal_ceo@oroshin.site |
| Bonus, content | https://youtu.be/FrXYmZm8r60 (the unedited take, a separate public upload) |
| Bonus, social post | https://www.linkedin.com/posts/than-kywal-nyein-3b1808318_allthingsagentichackathon-ugcPost-7494982407415181312-AENs |
| Architecture diagram | `docs/architecture.png`, uploaded to the form |

The demo video is https://youtu.be/AdAM5l4tWAY, public, 3:53.

## Two things the API cannot do

Gallery images and the architecture diagram attachment are not editable over
the Devpost MCP, so both are done by hand:

- the first gallery image is an older architecture diagram naming Gemma, Cloud
  Tasks, Cloud SQL, Pub/Sub and a VPC, none of which this project uses. It has
  to be deleted, and the current `docs/architecture.png` moved first
- the architecture diagram field has a duplicate attachment on it
