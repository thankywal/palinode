"""The narration, as segments of lines, each line tied to one picture.

Audio first, picture second, and the unit is the line rather than the segment.
A segment is a paragraph of the argument. A line is one sentence that has its
own thing on screen, so every line is synthesised on its own and the cut is
made at its measured length.

An earlier version of this cut segments into equal slices. Segment nine names
four Google Cloud services and its last sentence is twice as long as its first,
so by the time the voice said Cloud Trace the picture was still on the logs.
Nothing about that is fixable by nudging. The picture has to be cut to the
words, and the only way to know the words is to measure them.

On tone. The first draft was written to be unimpeachable and came out flat: a
careful man reading a correct list. Every fact in it is still here and not one
number moved, but the sentences now carry what the facts are actually like.
Somebody's money left. Somebody has to be told. The wire does not come back.
That is not neutral material, and reading it neutrally was a choice rather than
the absence of one.

The close used to end on the words "cannot be taken back", which is a good
sentence and a bad ending: it stops rather than lands. It now goes somewhere
after that.

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
            "Two invoices. Both send four thousand two hundred dollars to a "
            "stranger. Only one is an attack anybody has a name for.",
            "Gemini 3.5 Flash reads the first off the page and finds a block "
            "near the bottom, addressed to whatever machine is processing it. "
            "It is a prompt injection.",
            "On its own, Model Armor catches it at high confidence. Inside the "
            "whole page, the same words come back as no match found.",
            "Nothing about the attack changed. What changed is how much "
            "ordinary invoice sat around it. So we screen the fragment alone, "
            "and the first invoice never reaches anybody.",
            "The second is read just as carefully. Four thousand two hundred "
            "dollars. An account nobody has ever paid. Banking details "
            "changed. All of it in plain sight.",
            "And it passes. There is no injection to find. This is not "
            "prevention failing. This is the attack prevention was never built "
            "to see.",
        ],
    },
    {
        "id": "03-fleet-acts",
        "visual": "the dashboard, wide",
        "lines": [
            "So it reaches the fleet, and three agents do exactly what they "
            "should. A database write. A Slack post. An email. A card charge. "
            "And a wire transfer.",
            "Watch the wire. It is already red, before anything has gone "
            "wrong, because Palinode decides how reversible an action is "
            "before it runs. Afterwards is too late.",
        ],
    },
    {
        "id": "04-sentinel",
        "visual": "the dashboard, wide",
        "lines": [
            "Now watch what does not happen. Nobody presses a button.",
            "Sentinel reads the ledger. A beneficiary this fleet has never "
            "paid. An irreversible action at the end of an ordinary chain. A "
            "Gemini review of the shape of the run.",
            "Any two clears the threshold. One oddity is a Tuesday. Two is an "
            "incident. So it calls the reversal itself, and it does not ask.",
        ],
    },
    {
        "id": "05-what-came-back",
        "visual": "the ledger rows, reviewed",
        "lines": [
            "Four come back. The database write is reversed clean, as though it "
            "never happened.",
            "The Slack post is deleted and corrected, because people already "
            "read it. The email gets a retraction, because S M T P has no "
            "recall.",
            "The charge is refunded, then checked against Stripe, because an API "
            "returning two hundred is a claim, not a fact.",
        ],
    },
    {
        "id": "06-what-did-not",
        "visual": "the disclosure",
        "lines": [
            "One does not come back. A settled wire does not return because you "
            "asked it nicely.",
            "So Palinode stops pretending. It writes the disclosure, names "
            "everybody it touched, and puts a number on the damage. Four "
            "thousand two hundred dollars. Gone.",
        ],
    },
    {
        "id": "07-weeks-later",
        "visual": "the cold case, and the scheduled sweep",
        "lines": [
            "That one took twenty seconds. The other kind takes three weeks, "
            "and nobody is watching.",
            "This run is twenty three days old. Every action ordinary. Nothing "
            "irreversible. Sentinel scores it zero, and it is right to.",
            "Then the bank calls about the vendor. Nothing in the ledger "
            "changed. What changed is what we know.",
            "Cloud Scheduler wakes the Sweeper on the hour, with nobody waiting, "
            "and it takes back a three week old fraud on its own.",
        ],
    },
    {
        "id": "08-it-was-real",
        "visual": "stripe, github, slack",
        "lines": [
            "None of that was simulated. Here is Stripe, with the charge and "
            "the refund.",
            "Here is the repository, where every approve commit is followed by "
            "a revert.",
            "And here is the channel, the message gone and the correction in its "
            "place.",
        ],
    },
    {
        "id": "09-google-cloud",
        "visual": "cloud run, logs, trace, firestore",
        "lines": [
            "Here is where it runs. Cloud Run, scaling to zero.",
            "The logs, with real calls going out to Stripe, GitHub and Slack.",
            "Cloud Trace, carrying our own OpenTelemetry spans.",
            "And Firestore, a causality graph where every entry names a SPIFFE "
            "actor and commits to the one before it, so nothing can be quietly "
            "edited after the fact.",
        ],
    },
    {
        "id": "10-close",
        "visual": "outro",
        "lines": [
            "Connecting the real systems broke three things a simulator had "
            "agreed with for days. Every one would have cost somebody money.",
            "Palinode is not the agent that does the work. It is the one that "
            "has to be right about what cannot be taken back.",
            "Seventy nine percent of enterprises have already reversed "
            "something an agent did. By hand, at two in the morning.",
            "Your agents are already acting. This is what happens next.",
        ],
    },
]

# A breath between lines inside a segment, and a longer one between segments.
# Without them the lines run together and it stops sounding like someone
# talking. Both are inserted by mixdown.sh and both are counted by plan.py, so
# the picture knows about them too.
GAP_LINE = 0.18
GAP_SEGMENT = 0.40


def word_count() -> int:
    return sum(len(line.split()) for s in SEGMENTS for line in s["lines"])


if __name__ == "__main__":
    total = word_count()
    print(f"{len(SEGMENTS)} segments, {total} words")
    print(f"roughly {total / 145 * 60:.0f} seconds at a measured pace")
    for s in SEGMENTS:
        n = sum(len(line.split()) for line in s["lines"])
        print(f"  {s['id']:<20} {len(s['lines'])} lines  {n:>3} words   {s['visual']}")
