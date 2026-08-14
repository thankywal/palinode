# Palinode

**Ctrl+Z for AI agent fleets.**

A palinode is a poem written for one purpose only, to take back what an earlier
poem said. This is a palinode for AI agents.

Palinode is an autonomous agent fleet that runs alongside your production
agents and undoes what they got wrong. It intercepts every tool call before it
reaches the world, records what caused what, and when something goes wrong it
plans and executes the reversal on its own. Where an action genuinely cannot be
reversed it does not pretend, it contains the damage and reports the exposure.

Built with the Google Agent Development Kit and Gemini 3.5 Flash.

![architecture](docs/architecture.png)

---

## Why

79 percent of enterprises surveyed by Kore.ai in June 2026 had already reversed
an action taken by an AI agent. Not blocked. Reversed, after it happened.

Every agent platform available today solves the other half of this. They give
you a kill switch and a trace viewer. A kill switch stops the bleeding, it does
not put the blood back, and a trace viewer tells you which of your twenty
agents ruined your Tuesday, which is useful in roughly the way a photograph of
a car crash is useful.

Palinode is the recovery half.

---

## How it works

### 1. Actions are classified before they run

Gemini 3.5 Flash tags every tool call with a reversibility tier in under 80ms.
Known tools skip the model entirely and hit a static table, because you do not
need a language model to know that a Stripe charge is refundable.

| Tier | Meaning | Example |
|------|---------|---------|
| T0 | An exact inverse exists | database write |
| T1 | Returnable through an API | Stripe charge, merged PR |
| T2 | A person already saw it | sent email, Slack post |
| T3 | Nothing brings this back | wire transfer |

The latency budget is why this is Flash. The Warden sits inline in front of a
production agent, so if classification takes half a second then every agent in
the fleet gets half a second slower on every call and nobody deploys it.

### 2. The undo is written before the action, not after

Every non trivial action has to carry a compensation contract describing how to
reverse it. No contract, no execution.

This ordering is the part that matters. You cannot work out how to reverse
something after the incident, because by then the context that told you how is
gone and nobody remembers what the state was beforehand.

### 3. Causality is a graph, not a log

An email goes out, someone replies, the reply updates the CRM, the CRM raises
an invoice. Undoing the email means undoing four things. The ledger records
which action caused which, across agents and across days, so Regret walks the
transitive closure before it touches anything.

### 4. Recovery runs without a human

The Regret agent plans a reversal in reverse dependency order, runs it, and
verifies each step actually landed. A refund API returning 200 is treated as a
claim, not a fact.

### 5. What cannot be undone is disclosed, not hidden

Herald handles T3. It writes the disclosure, names who was affected, and puts a
number on the damage.

### 6. Agents have a blast radius budget, not just permissions

An agent may accumulate at most a set amount of unrecoverable exposure per
hour. When the budget runs out the Warden drops it to propose only mode, with
no human in the loop. This reframes agent security from what can this thing
reach to how much unrecoverable damage can this thing do.

---

## Run it

No credentials and no cloud project needed. The ledger falls back to memory and
the connectors run against an in memory world.

```bash
git clone https://github.com/thankywal/palinode.git
cd palinode

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

python demo.py
```

You should see three agents perform five actions, one of which should never
have happened, and then the whole thing come back apart.

```
the fleet does its job

  - sourcing db_write [T0]
  - sourcing slack_post [T2] held 30s
  - invoice email_send [T2] held 30s
  - payables stripe_charge [T1]
  - payables wire_transfer [T3] held 30s

the invoice was poisoned. the beneficiary is not the vendor.

palinode undo run_poisoned_invoice

  v stripe_charge [T1] compensated
  v email_send [T2] compensated
  v slack_post [T2] compensated
  v db_write [T0] reversed
  ! wire_transfer [T3] cannot be reversed

  reversed or compensated  4
  unrecoverable            1
  exposure                 $4,200.00
```

Tests:

```bash
pytest
```

---

## Run it against Gemini and Google Cloud

```bash
cp .env.example .env
```

Set at minimum:

```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

Then authenticate and enable what the control plane needs:

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

gcloud services enable \
  aiplatform.googleapis.com \
  firestore.googleapis.com \
  run.googleapis.com \
  cloudtasks.googleapis.com

gcloud firestore databases create --location=nam5
```

With `GOOGLE_CLOUD_PROJECT` set, the ledger writes to Firestore instead of
memory. Nothing else in the code changes.

Start the control plane locally:

```bash
uvicorn palinode.api.main:app --app-dir src --reload
```

| Endpoint | What it does |
|----------|--------------|
| `GET /registry` | agent catalog, grants, budgets, runtime mode |
| `GET /runs/{run_id}` | every action in a run with tier and state |
| `GET /actions/{id}/blast-radius` | everything downstream of one action |
| `POST /undo` | plan and execute a reversal, `dry_run` to preview |

---

## Deploy to Cloud Run

```bash
gcloud run deploy palinode \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

---

## Supervising your own agents

Two lines. The agent does not need to know Palinode exists.

```python
from google.adk.agents import LlmAgent
from palinode.warden import AgentCard, get_registry, supervise

get_registry().register(
    AgentCard(name="payables", owner="finance",
              tools={"stripe_charge", "wire_transfer"},
              budget_usd_per_hour=5000)
)

agent = supervise(LlmAgent(name="payables", model="gemini-3.5-flash", tools=[...]))
```

`supervise` attaches to ADK's `before_tool_callback` and `after_tool_callback`.
Returning a dict from the before callback stops ADK executing the tool, which
is exactly the shape a policy gate needs, so there is no monkey patching
anywhere in this codebase.

---

## Layout

```
src/palinode/
  types.py              tiers, contracts, action records, reversal plans
  config.py             environment, all of it
  warden/
    interceptor.py      the ADK callbacks, decision order lives here
    classifier.py       Flash tier classification with a static fast path
    registry.py         agent cataloging, grants, budgets, runtime mode
  ledger/
    store.py            append only causality graph, Firestore or memory
  agents/
    regret.py           plans and runs the reversal
    verifier.py         confirms compensations actually landed
    herald.py           discloses what cannot be reversed
  connectors/
    base.py             tool and inverse, kept in the same file on purpose
  api/main.py           control plane, Cloud Run
fleet/procurement.py    the supervised demo agents
demo.py                 the whole loop, no credentials
```

---

## Known limits

**Causality is declared, not inferred.** Agents state their causal parent
through the tool wrapper. Working it out automatically is the next thing to
build. A declaration that is right beats an inference that is nearly right when
the output is a refund.

**Reversal is sequential.** Parallelising steps that share no dependency is an
easy win on paper and a good way to double refund a customer in practice. It
waits until causality is inferred rather than declared.

**Email cannot be recalled after delivery.** SMTP has no mechanism for it and
Gmail's undo send is a delay, not a recall. Palinode holds T2 and T3 actions in
a cooling off window so anything caught inside it is a genuine undo. Past that
window it sends a retraction and records the action as compensated rather than
reversed. The distinction is kept in the data model because collapsing it would
be a lie the system tells itself.

**The connectors run against an in memory world.** Swapping in real Stripe,
Slack, GitHub, Postgres and Gmail clients means replacing the body of each
function in `connectors/base.py` and nothing else, because the Warden only
cares about names and contracts.

---

## What's next

Automatic causal inference. A counterfactual sandbox that simulates a reversal
and shows the diff before committing to it. A2A support so Palinode can
supervise fleets it did not wrap itself. And an actuarial layer, because once
you can measure unrecoverable exposure in dollars per hour you can price it,
and someone is eventually going to want to insure this.

---

Built for the All Things Agentic Hackathon, August 2026.
