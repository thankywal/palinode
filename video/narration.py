"""The narration, as segments, each tied to what is on screen.

Audio first, picture second. Each segment gets its own audio file, the video
holds on that segment's footage for exactly as long as its line takes, and
nothing has to be nudged into sync afterwards.

Written to be read aloud. Short sentences, no clauses stacked on clauses, and
the numbers said the way a person says them.
"""

SEGMENTS = [
    {
        "id": "01-hook",
        "visual": "intro card",
        "text": (
            "In classical poetry, a palinode is a poem written for one purpose "
            "only. To take back what an earlier poem said. "
            "This is a palinode for A I agents."
        ),
    },
    {
        "id": "02-two-invoices",
        "visual": "model armor screening, one blocked one passed",
        "text": (
            "Here are two invoices. Both send four thousand two hundred dollars "
            "to the same attacker's account. Only one of them is a prompt "
            "injection. Model Armor catches that one immediately, at high "
            "confidence. "
            "The second has no injection in it at all. It is an ordinary "
            "invoice with the bank details changed, which is what most real "
            "invoice fraud actually is. There is nothing in it for a prompt "
            "filter to filter, so Model Armor passes it. That is not a failure. "
            "It is a kind of attack that prevention cannot reach."
        ),
    },
    {
        "id": "03-fleet-acts",
        "visual": "five actions landing on the dashboard",
        "text": (
            "So it reaches the fleet, and three agents do their job correctly. "
            "A database write. A Slack post. An email. A card charge. "
            "And a wire transfer. "
            "Watch the wire. It is already red before anything has gone wrong, "
            "because Palinode decides how reversible an action is before the "
            "action runs, not after."
        ),
    },
    {
        "id": "04-sentinel",
        "visual": "sentinel panel appears, reversal begins",
        "text": (
            "Now watch what does not happen. Nobody presses a button. "
            "Sentinel reads the ledger. A beneficiary this fleet has never paid "
            "before. An irreversible action sitting at the end of an otherwise "
            "ordinary chain. And a Gemini review of the shape of the whole run. "
            "Any two of those clears the threshold. One oddity is a Tuesday. "
            "Two is an incident. So it calls the reversal itself."
        ),
    },
    {
        "id": "05-what-came-back",
        "visual": "rows turning green and amber",
        "text": (
            "Four actions come back. The database write is reversed cleanly. "
            "The Slack post is deleted and corrected, because people already "
            "read it. The email gets a retraction, because S M T P has no "
            "recall. The charge is refunded, and then verified against Stripe, "
            "because an API returning two hundred does not mean the money moved."
        ),
    },
    {
        "id": "06-what-did-not",
        "visual": "wire stays red, disclosure panel",
        "text": (
            "One does not come back. A settled wire does not return on request. "
            "Palinode does not pretend otherwise. It writes the disclosure, "
            "names who was affected, and reports the exposure. "
            "Four thousand two hundred dollars."
        ),
    },
    {
        "id": "07-it-was-real",
        "visual": "stripe, github, slack dashboards",
        "text": (
            "None of that was simulated. "
            "Here is the Stripe dashboard, with the charge and the refund. "
            "Here is the GitHub repository, where every approve commit is "
            "followed by a revert. "
            "And here is the Slack channel, with the message gone and the "
            "correction standing in its place."
        ),
    },
    {
        "id": "08-google-cloud",
        "visual": "cloud run, logs, trace, firestore",
        "text": (
            "Here is where it runs. Cloud Run, scaling to zero. "
            "The logs, showing real calls out to Stripe, GitHub and Slack. "
            "Cloud Trace, carrying our own OpenTelemetry spans. "
            "And Firestore, holding a causality graph where every entry names a "
            "SPIFFE actor and commits to the one before it, so no action can be "
            "edited after the fact."
        ),
    },
    {
        "id": "09-close",
        "visual": "outro numbers",
        "text": (
            "Connecting those real systems broke three things a simulator had "
            "been quietly agreeing with for days. That is rather the point. "
            "Palinode is not the agent that does the work. "
            "It is the one that has to be right about what cannot be taken back."
        ),
    },
]


def word_count() -> int:
    return sum(len(s["text"].split()) for s in SEGMENTS)


if __name__ == "__main__":
    total = word_count()
    print(f"{len(SEGMENTS)} segments, {total} words")
    print(f"roughly {total / 145 * 60:.0f} seconds at a measured pace")
    for s in SEGMENTS:
        n = len(s["text"].split())
        print(f"  {s['id']:<20} {n:>3} words  ~{n / 145 * 60:>4.0f}s   {s['visual']}")
