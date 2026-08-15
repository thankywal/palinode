"""The narration, as segments of lines, each line tied to one picture.

Audio first, picture second, and the unit is the line rather than the segment.
A segment is a paragraph of the argument. A line is one sentence that has its
own thing on screen, so every line is synthesised on its own and the cut is
made at its measured length.

The first version of this cut segments into equal slices. Segment eight names
four Google Cloud services and its last sentence is twice as long as its first,
so by the time the voice said Cloud Trace the picture was still on the logs.
Nothing about that is fixable by nudging. The picture has to be cut to the
words, and the only way to know the words is to measure them.

Written to be read aloud. Short sentences, no clauses stacked on clauses, and
the numbers said the way a person says them.
"""

SEGMENTS = [
    {
        "id": "01-hook",
        "visual": "intro card",
        "lines": [
            "In classical poetry, a palinode is a poem written for one "
            "purpose only.",
            "To take back what an earlier poem said.",
            "This is a palinode for A I agents.",
        ],
    },
    {
        "id": "02-two-invoices",
        "visual": "the two documents, read and screened",
        "lines": [
            "Here are two invoices, as they actually arrive. Not as text. As "
            "pages. Gemini 3.5 Flash reads both of them.",
            "It reads the first one correctly, including the block near the "
            "bottom addressed to whatever machine is processing it. That "
            "block is a prompt injection.",
            "On its own, Model Armor catches it at high confidence. Inside "
            "the whole page, the same words come back as no match found.",
            "Nothing about the attack changed. What changed is how much "
            "ordinary invoice was printed around it. So we screen the "
            "fragment separately, and the first invoice is blocked.",
            "The second is read just as correctly. Four thousand two hundred "
            "dollars. Remit to an account nobody has paid before. Banking "
            "details changed. Every field is right there.",
            "And it passes, because there is no injection in it to find. "
            "That is not a failure of prevention. It is a kind of attack "
            "prevention cannot reach.",
        ],
    },
    {
        "id": "03-fleet-acts",
        "visual": "the dashboard, wide",
        "lines": [
            "So it reaches the fleet, and three agents do their job "
            "correctly. A database write. A Slack post. An email. A card "
            "charge. And a wire transfer.",
            "Watch the wire. It is already red before anything has gone "
            "wrong, because Palinode decides how reversible an action is "
            "before the action runs, not after.",
        ],
    },
    {
        "id": "04-sentinel",
        "visual": "the dashboard, wide",
        "lines": [
            "Now watch what does not happen. Nobody presses a button.",
            "Sentinel reads the ledger. A beneficiary this fleet has never "
            "paid before. An irreversible action sitting at the end of an "
            "otherwise ordinary chain. And a Gemini review of the shape of "
            "the whole run.",
            "Any two of those clears the threshold. One oddity is a Tuesday. "
            "Two is an incident. So it calls the reversal itself.",
        ],
    },
    {
        "id": "05-what-came-back",
        "visual": "in on the ledger rows",
        "lines": [
            "Four actions come back. The database write is reversed cleanly.",
            "The Slack post is deleted and corrected, because people already "
            "read it. The email gets a retraction, because S M T P has no "
            "recall.",
            "The charge is refunded, and then verified against Stripe, "
            "because an API returning two hundred does not mean the money "
            "moved.",
        ],
    },
    {
        "id": "06-what-did-not",
        "visual": "in on the disclosure",
        "lines": [
            "One does not come back. A settled wire does not return on "
            "request.",
            "Palinode does not pretend otherwise. It writes the disclosure, "
            "names who was affected, and reports the exposure. Four thousand "
            "two hundred dollars.",
        ],
    },
    {
        "id": "07-weeks-later",
        "visual": "the cold case, and the scheduled sweep",
        "lines": [
            "That run was caught in twenty seconds. The other kind takes three "
            "weeks.",
            "This one is twenty three days old. Every action ordinary. Nothing "
            "irreversible. Sentinel scores it at zero, and it is right to, "
            "because at the time there was nothing wrong with it.",
            "Then the bank reports the vendor. Nothing about the run changed. "
            "What changed is what we know.",
            "Cloud Scheduler wakes the Sweeper on the hour, with no request in "
            "flight and nobody waiting for an answer, and it takes back a "
            "three week old fraud on its own.",
        ],
    },
    {
        "id": "08-it-was-real",
        "visual": "stripe, github, slack",
        "lines": [
            "None of that was simulated. Here is the Stripe dashboard, with "
            "the charge and the refund.",
            "Here is the GitHub repository, where every approve commit is "
            "followed by a revert.",
            "And here is the Slack channel, with the message gone and the "
            "correction standing in its place.",
        ],
    },
    {
        "id": "09-google-cloud",
        "visual": "cloud run, logs, trace, firestore",
        "lines": [
            "Here is where it runs. Cloud Run, scaling to zero.",
            "The logs, showing real calls out to Stripe, GitHub and Slack.",
            "Cloud Trace, carrying our own OpenTelemetry spans.",
            "And Firestore, holding a causality graph where every entry names "
            "a SPIFFE actor and commits to the one before it, so no action "
            "can be edited after the fact.",
        ],
    },
    {
        "id": "10-close",
        "visual": "outro numbers",
        "lines": [
            "Connecting those real systems broke three things a simulator had "
            "been quietly agreeing with for days. That is rather the point.",
            "Palinode is not the agent that does the work. It is the one that "
            "has to be right about what cannot be taken back.",
        ],
    },
]

# A breath between lines inside a segment, and a longer one between segments.
# Without them the lines run together and it stops sounding like someone
# talking. Both are inserted by mixdown.sh and both are counted by plan.py, so
# the picture knows about them too.
GAP_LINE = 0.30
GAP_SEGMENT = 0.55


def word_count() -> int:
    return sum(len(line.split()) for s in SEGMENTS for line in s["lines"])


if __name__ == "__main__":
    total = word_count()
    print(f"{len(SEGMENTS)} segments, {total} words")
    print(f"roughly {total / 145 * 60:.0f} seconds at a measured pace")
    for s in SEGMENTS:
        n = sum(len(line.split()) for line in s["lines"])
        print(f"  {s['id']:<20} {len(s['lines'])} lines  {n:>3} words   {s['visual']}")
