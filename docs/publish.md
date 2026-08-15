# What to post, and where

Three places. The video has to live on YouTube because Devpost only accepts a
video host, and a file does not count. The other two are the bonus points.

---

## 1. YouTube

Upload `video/out/palinode-demo.mp4`. **Public**, not unlisted.

Unlisted is enough for the submission itself, but the bonus point for
published content requires the content to be public, and a public upload
covers both with one file.

**Title**

    Palinode: the AI agent fleet that undoes what other agents did

**Description**

    Palinode is an autonomous agent fleet that watches production agents,
    notices when one of them has been played, and reverses what it did across
    Stripe, GitHub and Slack. Nobody presses a button.

    The demo runs against the deployed service on Cloud Run. The charge, the
    commit and the Slack message are real, and so are the refund, the revert
    and the deletion. The wire transfer is the one that does not come back,
    and the system says so instead of pretending.

    Built on Google ADK, Gemini 3.5 Flash on Vertex AI, Model Armor, Firestore
    and Cloud Trace. The soundtrack is Lyria. The narration is Cloud TTS.

    I created this video for the purposes of entering the All Things Agentic
    Hackathon.

    Code: https://github.com/thankywal/palinode
    Live: https://palinode-173485225974.us-central1.run.app

    00:00  A palinode is a poem that takes back an earlier poem
    00:10  Two invoices, and the one Model Armor cannot catch
    00:41  The fleet acts, and Sentinel reverses it on its own
    01:55  Stripe, GitHub and Slack, after the fact
    02:10  Where it runs
    02:31  What connecting the real systems broke

Then paste the watch URL back here and it goes on the submission.

---

## 2. LinkedIn

The hashtag is what earns the point. It has to be there.

    79 percent of enterprises have already had to reverse an action taken by
    an AI agent. Not block it. Reverse it, after it happened.

    Every agent platform I looked at solves the other half of that. They give
    you a kill switch and a trace viewer. A kill switch stops the bleeding, it
    does not put the blood back.

    So I spent this hackathon building Palinode, and the thing I did not
    expect is how much of it turned out to be about honesty.

    The demo has two invoices. Both send 4,200 dollars to the same attacker.
    One is a prompt injection and Model Armor catches it at high confidence.
    The other is an ordinary invoice with the bank details changed, and there
    is nothing in it for a prompt filter to find, so it passes. That is not a
    failure of prevention. It is the category prevention cannot reach.

    Palinode is what happens next. Every tool call is classified for
    reversibility before it runs and has to carry the instructions for its own
    undo. When the fleet gets played, Sentinel reads the ledger, decides on
    its own that this was an incident, and calls the reversal. A refund, a
    revert, a deleted message. Real Stripe, real GitHub, real Slack.

    And then the wire transfer, which does not come back. So the system writes
    the disclosure, names who was affected, and reports the exposure in
    dollars, because the alternative is a product that lies to you on the one
    day it matters.

    The best thing that happened was wiring up the real APIs. Three defects
    had been sitting behind a simulator that agreed with everything I told it,
    including a Slack deletion that quietly did nothing and reported success.
    I only found it by opening Slack and seeing the message still there.

    Built solo at Oro Shin on Google ADK, Gemini 3.5 Flash, Model Armor,
    Cloud Run, Firestore and Cloud Trace.

    #AllThingsAgenticHackathon

    Code: https://github.com/thankywal/palinode
    Demo: <youtube url>

Attach `docs/architecture.png`, or the Slack screenshot in
`video/console/p7-slack.jpg`. The Slack one gets more attention because it
shows a real channel.

---

## 3. Devpost

Everything except the video is already on the submission. Once the YouTube
link exists, the video field and the two optional bonus fields get filled and
it can be submitted.
