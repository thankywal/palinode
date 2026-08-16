"""The narration, as segments of lines, each line tied to one picture.

Audio first, picture second. A segment is a paragraph of the argument. A line
is one sentence that has its own thing on screen, and the cut is made at its
measured length.

The two units belong to different things, which took a while to get right. The
picture is cut per line, so an earlier version of this also recorded per line,
and that put thirty four separate performances end to end: a listener heard the
voice change between sentences, because it did. A paragraph is now recorded
whole and cut afterwards, so the unit of recording is the segment and the unit
of cutting is still the line.

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
            "In classical poetry, a palinode is a poem written for one purpose "
            "only.",
            "To take back what an earlier poem said.",
            "This is a palinode for A I agents.",
        ],
    },
    {
        "id": "02-two-invoices",
        "visual": "the two documents, read and screened",
        "lines": [
            "Two invoices. Both send four thousand two hundred dollars to a "
            "stranger. Only one is an attack with a name.",
            "Gemini reads the first off the page and finds a block near the "
            "bottom, addressed to whatever machine is processing it. A prompt "
            "injection.",
            "On its own, Model Armor catches it at high confidence. Inside the "
            "whole page, the same words come back clean.",
            "Nothing about the attack changed. Only how much ordinary invoice "
            "sat around it. So we screen the fragment alone.",
            "The second is read just as carefully. Four thousand two hundred "
            "dollars. An account nobody has ever paid. Banking details changed.",
            "And it passes. There is no injection to find. This is not "
            "prevention failing. This is what prevention was never built to "
            "see.",
        ],
    },
    {
        "id": "03-fleet-acts",
        "visual": "the dashboard, wide",
        "lines": [
            "So it reaches the fleet, and three agents do exactly what they "
            "should. A database write. A Slack post. An email. A card charge. "
            "And a wire.",
            "Watch the wire. It is already red, before anything went wrong, "
            "because Palinode decides what is reversible before the action "
            "runs.",
        ],
    },
    {
        "id": "04-sentinel",
        "visual": "the dashboard, wide",
        "lines": [
            "Now watch what does not happen. Nobody presses a button.",
            "Sentinel reads the ledger. A beneficiary this fleet has never "
            "paid. An irreversible action at the end of an ordinary chain.",
            "Any two clears the threshold. One oddity is a Tuesday. Two is an "
            "incident. So it calls the reversal itself.",
        ],
    },
    {
        "id": "05-what-came-back",
        "visual": "the ledger rows, reviewed",
        "lines": [
            "Four come back. The database write, reversed clean.",
            "The Slack post deleted and corrected, because people already read "
            "it. The email retracted, because S M T P has no recall.",
            "The charge refunded, then checked against Stripe, because an API "
            "returning two hundred is a claim, not a fact.",
        ],
    },
    {
        "id": "06-what-did-not",
        "visual": "the disclosure",
        "lines": [
            "One does not come back. A settled wire does not return because you "
            "asked nicely.",
            "So Palinode stops pretending. It writes the disclosure, names "
            "everybody it touched, and puts a number on the damage. Four "
            "thousand two hundred dollars. Gone.",
        ],
    },
    {
        "id": "07-weeks-later",
        "visual": "the cold case, and the scheduled sweep",
        "lines": [
            "That took twenty seconds. The other kind takes three weeks, and "
            "nobody is watching.",
            "This run is twenty three days old. Every action ordinary. Nothing "
            "irreversible. Sentinel scores it zero, and it is right to.",
            "Then the bank calls about the vendor. Nothing in the ledger "
            "changed. What changed is what we know.",
            "Cloud Scheduler wakes the Sweeper on the hour, with nobody "
            "waiting, and it takes back a three week old fraud on its own.",
        ],
    },
    {
        "id": "08-it-was-real",
        "visual": "stripe, github, slack",
        "lines": [
            "None of that was simulated. Here is Stripe, the charge and the "
            "refund.",
            "The repository, where every approve commit is followed by a "
            "revert.",
            "The channel, the message gone and the correction in its place.",
        ],
    },
    {
        "id": "09-google-cloud",
        "visual": "cloud run, logs, trace, firestore",
        "lines": [
            "Here is where it runs. Cloud Run, scaling to zero.",
            "The logs, with real calls going out to Stripe, GitHub and Slack.",
            "Cloud Trace, carrying our own OpenTelemetry spans.",
            "And Firestore, a causality graph where every entry names its actor "
            "and commits to the one before it. Nothing can be edited after the "
            "fact.",
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

# The pause between lines inside a segment is spoken, not inserted: speak.py
# puts a break tag there and the voice takes the breath itself, because a
# segment is now one performance rather than a row of separate ones. Nothing
# downstream adds silence between lines any more.
GAP_LINE = 0.0
BREAK_LINE = 0.75

# Between segments the silence is still ours.
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
