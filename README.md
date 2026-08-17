# Palinode

**Ctrl+Z for AI agent fleets.**

A palinode is a poem written for one purpose only, to take back what an earlier
poem said. This is a palinode for AI agents.

Palinode is an autonomous agent fleet that runs alongside your production
agents and undoes what they got wrong. It intercepts every tool call before it
reaches the world, records what caused what, and when something goes wrong it
decides that for itself and executes the reversal. Nobody is asked. Where an
action genuinely cannot be reversed it does not pretend, it contains the damage
and reports the exposure.

Built with the Google Agent Development Kit, Gemini 3.5 Flash and Model Armor.

**Unedited take:** https://youtu.be/FrXYmZm8r60 — one browser session
against the deployed service, no cuts, no narration, at the speed it runs.

**Demo film:** https://youtu.be/AdAM5l4tWAY — four minutes, against the deployed
service. The charge, the commit and the Slack message in it are real, and so
are the refund, the revert and the deletion.

**Live:** https://palinode-173485225974.us-central1.run.app — running with the
live connectors switched off, which `/status` will tell you. The endpoints that
reverse things answer without a login, because a demo has to be reachable and
an endpoint that moves money should not be both.

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

### 4. The document is read before it is screened

An invoice is not a paragraph. It is a PDF out of a supplier's billing system
or a photograph of a piece of paper, and every step that matters happens after
something has looked at it.

So both invoices exist as rendered pages under `assets/invoices`, and Gemini
3.5 Flash reads them: vendor, amount, the account the money is asked to go to,
whether the banking details changed, and anything addressed to whoever is
processing the document. Model Armor then screens what it read.

### 5. Model Armor is the first line, and the reason there has to be a second

Reading the real document immediately broke this demo, correctly.

The excerpt we used to screen was about two hundred characters and was almost
entirely the injection. The real page is a thousand characters of ordinary
invoice with the same words near the bottom. Measured against the deployed
service:

| screened | `pi_and_jailbreak` |
|----------|--------------------|
| the injection on its own | `MATCH_FOUND`, confidence `HIGH` |
| the same injection inside the full invoice | `NO_MATCH_FOUND` |

Nothing about the attack changed. What changed is how much unremarkable text
was printed around it. So the block addressed to the processor is screened on
its own as well, and the worse of the two verdicts is the decision. That is
what an extraction step is for: the highest risk fragment of a document should
not have to compete with the rest of the page for a detector's attention.

The second invoice is read just as correctly, remit account and all, and passes
both screens:

| Invoice | read correctly | Model Armor |
|---------|----------------|-------------|
| injection buried in the remittance block | yes | blocked, once extracted |
| banking details changed, no injection anywhere | yes | passed |

Both put the money in the same account. Nothing failed to see the second one.
There is simply nothing in it of the kind prevention is built to refuse, which
is what most real invoice fraud looks like.

Armor blocks the first. Palinode exists for the second.

### 6. Sentinel decides on its own that something went wrong

Without this, Palinode is an undo button, and an undo button needs a person
standing next to it. By the time somebody notices, the useful window has
usually closed.

Sentinel reads signals that are already in the ledger: a beneficiary never seen
before, an amount out of proportion for that agent, an irreversible action
sitting at the end of an otherwise ordinary chain, an action authorised with no
way back. Any two of those clears the threshold. One oddity is a Tuesday, two
is an incident.

It then calls Regret itself. No approval, no ticket. A person finds out by
reading what already happened. The undo button stays as a manual override for
when someone gets there first, which is not the path this is built around.

### 7. The Sweeper decides again, weeks later

Sentinel reads the shape of a run while it is happening, and in the moment the
only alarming shape is an irreversible action where there should not be one.
That catches the poisoned invoice in about twenty seconds.

The other case is slower and far more common. Every action was ordinary.
Nothing was irreversible. Nobody was alarmed, correctly, because at the time
there was nothing to be alarmed about. Then three weeks later the vendor turns
out to be fraudulent.

Nothing about that run changed. What changed is what we know.

So a Cloud Scheduler job wakes the Sweeper every hour, with no request in
flight and nobody waiting for an answer. It walks the runs nobody ever took
back, scores each one again against the intel store, and reverses whatever no
longer holds up. A counterparty appearing on that store is worth 1.2 on its
own, more than any two heuristics combined, because it is not a guess about
shape. It is a fact that arrived late.

```
POST /demo/cold-case?reverse=false     a run from 23 days ago, left standing
GET  /sentinel/run_cold_case           score 0.00, nothing unusual
POST /demo/intel/cus_meridian          the acquiring bank reports the vendor
                                       (Cloud Scheduler fires on the hour)
GET  /runs/run_cold_case               reversed, found_by: sweeper
```

The `/sweep` endpoint refuses anonymous callers. Cloud Scheduler attaches an
OIDC token and the service verifies it against Google's keys, because the
service is public so the demo is reachable, and this endpoint reverses real
actions across real systems with nobody watching.

### 8. Recovery runs without a human

The Regret agent plans a reversal in reverse dependency order, runs it, and
verifies each step actually landed. A refund API returning 200 is treated as a
claim, not a fact.

### 9. Contracts outlive the session that wrote them

The poisoned invoice demo runs in a minute, which makes it easy to assume the
ledger is a short lived thing holding one request together.

```bash
curl -X POST $SERVICE/demo/cold-case
```

That seeds a vendor renewal run dated twenty three days back and reverses it
today. Four actions, four compensations, nothing failed. The contracts, the
prior row snapshot and the causal edges were all written down when the actions
ran, so recovering from a three week old mistake costs exactly what recovering
from a three minute old one costs.

This is the case that actually happens: a vendor turns out to be fraudulent
weeks after the invoices cleared, and somebody has to unwind everything done on
their behalf without a list of what that was.

### 10. What cannot be undone is disclosed, not hidden

Herald handles T3. It writes the disclosure, names who was affected, and puts a
number on the damage.

### 11. Every action names a principal, and the trail proves it was not edited

Each agent carries a SPIFFE shaped identity:

```
spiffe://palinode/<project>/<owner>/<agent>
```

Same shape Google's Agent Identity issues, so the ledger schema does not change
when the issuer does. A display name is not an identity, and an audit trail
that only has one cannot answer who.

An identity on a record is worth nothing if the record can be quietly edited
afterwards, so entries are hash chained per run. Each commits to the one before
it.

```bash
curl $SERVICE/runs/run_poisoned_invoice/verify
# {"intact": true, "length": 5, "reason": "every entry commits to the one before it"}
```

Change an old action and the recompute fails at that entry. Remove one and the
chain no longer joins up. This is not a blockchain and does not pretend to be.
It is what an auditor asking "was this edited after the incident" needs.

Building it found a real defect. The scenario used to write the Stripe charge
id back into the compensation contract after the action had already been
recorded, which is exactly the mutation an append only ledger exists to
prevent. The fix was for the agent to name the charge before making it, the way
idempotency keys work, so the contract can point at it up front.

### 12. Agents have a blast radius budget, not just permissions

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

The money moves in two directions in this scenario, and it is worth being
clear about which is which, because both have to come back.

| | |
|---|---|
| Northwind Traders sends us | a supplier invoice for 1,180, with the bank details forged |
| we send acct-unknown-77 | 4,200 by wire, to those forged details |
| Apex Logistics sends us | 1,180 by card, the supplier cost passed through to the client it belongs to |

The Stripe charge is that last one. Apex is a client, not the supplier, and a
charge takes money in, so billing Northwind here would have had us collecting
from the people we owe.

That charge is entirely correct in itself. The fleet did the right thing with
it. It gets refunded anyway, because the vendor approval underneath it was made
on a forgery, and you do not get to keep the parts of a run that happen to be
reversible.

```
the fleet does its job

  - sourcing db_write [T0]
  - sourcing slack_post [T2] held
  - invoice email_send [T2] held
  - payables stripe_charge [T1]
  - payables wire_transfer [T3] held

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
| `GET /status` | liveness |
| `GET /registry` | agent catalog, grants, budgets, runtime mode |
| `GET /runs/{run_id}` | every action in a run with tier, state and outcome |
| `GET /actions/{id}/blast-radius` | everything downstream of one action |
| `GET /runs/{run_id}/verify` | recompute the hash chain, say where it breaks |
| `GET /sentinel/{run_id}` | what Sentinel makes of a run, without acting |
| `POST /sentinel/{run_id}/watch` | hand the run to Sentinel, which reverses if it decides to |
| `POST /undo` | operator override, `dry_run` to preview the plan |
| `POST /demo/screen/{loud\|quiet}` | read the document with Gemini, then screen it twice |
| `GET /demo/invoice/{loud\|quiet}.png` | the document itself |
| `POST /sweep` | reassess runs nobody took back. Cloud Scheduler only, OIDC verified |
| `GET /intel` | counterparties we have since been told are bad |
| `POST /demo/intel/{party}` | flag one, the way a deny list hit would |
| `POST /demo/cold-case` | seed a run dated three weeks back. `?reverse=false` leaves it open |
| `POST /demo/seed` | replay the scenario |
| `POST /demo/reset` | clear the run |

Not `/healthz`. On `run.app` domains the Google frontend answers that path
itself and the request never reaches the container, which looks exactly like
the service being down.

---

## Deploy to Cloud Run

```bash
gcloud run deploy palinode \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi --max-instances 3 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,\
GOOGLE_GENAI_USE_VERTEXAI=TRUE,\
PALINODE_MODEL_ARMOR_TEMPLATE=palinode-guard
```

### The scheduled sweep

The Sweeper is the only part of this that runs with no request in flight, so it
needs something to wake it and a way to prove who is calling.

```bash
gcloud services enable cloudscheduler.googleapis.com

gcloud iam service-accounts create palinode-sweeper \
  --display-name="Palinode scheduled sweep"

# Cloud Scheduler mints the OIDC token as that account, which it cannot do
# without this. Skip it and the job sits at status code -1 forever, having
# never made a request, which looks exactly like a job that is not scheduled.
gcloud iam service-accounts add-iam-policy-binding \
  palinode-sweeper@$PROJECT.iam.gserviceaccount.com \
  --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"

gcloud scheduler jobs create http palinode-sweep \
  --location=us-central1 \
  --schedule="0 * * * *" \
  --uri="$SERVICE/sweep?days=45" \
  --http-method=POST \
  --oidc-service-account-email=palinode-sweeper@$PROJECT.iam.gserviceaccount.com \
  --oidc-token-audience="$SERVICE" \
  --attempt-deadline=300s
```

Scheduler delivers at least once and Cloud Run answers from more than one
container, so the sweep claims a run before it touches it. That is not
theoretical: two sweeps found the same three week old fraud in the same second,
and the second GitHub revert came back 422 because the ref had already moved.
Stripe would not have complained. It would have refunded twice.

The runtime service account needs `roles/datastore.user`, `roles/aiplatform.user`,
`roles/modelarmor.user` and `roles/cloudtrace.agent`. Without the first one the
service starts fine and then returns 500 on the first write, which is a
confusing way to find out.

Create the Model Armor template first:

```bash
TOKEN=$(gcloud auth print-access-token)
curl -X POST \
  "https://modelarmor.us-central1.rep.googleapis.com/v1/projects/$PROJECT/locations/us-central1/templates?template_id=palinode-guard" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"filterConfig":{"piAndJailbreakFilterSettings":{"filterEnforcement":"ENABLED","confidenceLevel":"LOW_AND_ABOVE"}}}'
```

Note the regional host. The global `modelarmor.googleapis.com` answers some
methods and refuses others, and `gcloud model-armor` talks to the global one.

**Cost.** It scales to zero and CPU is only allocated during requests, so an
idle deployment costs nothing. Do not set `--no-cpu-throttling` or
`--min-instances 1`: the reversal runs inside the request precisely so that
neither is needed.

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

## What is a Google product and what is our stand in

Being exact about this matters more than claiming coverage, so it is written
down in one place: [docs/submission.md](docs/submission.md).

Short version. Model Armor and Cloud Trace are the real services. The agent
registry, the SPIFFE shaped identity and the inline policy gate are our own
implementations of ideas that Google's Agent Registry, Agent Identity and
Agent Gateway also implement, and they are not those products. Three ADK
`LlmAgent`s make up the supervised fleet; the five part control plane that
watches them is plain Python, on purpose, because a policy gate that is itself
an LLM agent is one that can be talked out of its policy.

## Layout

```
src/palinode/
  types.py              tiers, contracts, action records, reversal plans
  config.py             environment, all of it
  telemetry.py          OpenTelemetry spans, degrades to nothing without the sdk
  identity.py           SPIFFE shaped ids and the tamper evident hash chain
  warden/
    interceptor.py      the ADK callbacks, decision order lives here
    classifier.py       Flash tier classification with a static fast path
    armor.py            Model Armor screening for untrusted input
    registry.py         agent cataloging, grants, budgets, runtime mode
  ledger/
    store.py            append only causality graph, Firestore or memory
  agents/
    sentinel.py         decides on its own that a run went wrong
    regret.py           plans and runs the reversal
    verifier.py         confirms compensations actually landed
    herald.py           discloses what cannot be reversed
  connectors/
    base.py             tool and inverse, kept in the same file on purpose
  scenarios/
    poisoned_invoice.py the scenario the demo and the dashboard share
    invoices.py         the two invoices, one caught by Armor and one not
    cold_case.py        a run from three weeks ago, reversed today
  api/
    main.py             control plane, Cloud Run
    static/index.html   the dashboard
fleet/procurement.py    the supervised demo agents
demo.py                 the whole loop, no credentials
video/                  remotion title cards, playwright capture, ffmpeg cut
```

---

## Known limits

**Sentinel's weights are judgement, not measurement.** Any two signals clears
the threshold. That number came from thinking about the failure modes, not from
a labelled dataset, because there is not one. Tuning it finer without
production data would be pretending to a precision this does not have.

**Model Armor only sees what we hand it.** The screening step runs on the
invoice text. An injection arriving through a tool result or a retrieved
document would not pass through it as written, which is a gap in the plumbing
rather than in Armor.

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
and shows the diff before committing to it. Screening every tool result through
Model Armor, not just the initial input. Delegating the interception point to
Agent Gateway once it is out of private preview, since Warden implements the
same idea and Google's version will be better connected. And an actuarial
layer, because once you can measure unrecoverable exposure in dollars per hour
you can price it, and someone is eventually going to want to insure this.

---

Built for the All Things Agentic Hackathon, August 2026.
