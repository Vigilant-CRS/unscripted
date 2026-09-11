"""Rewriting a pack's lines at build time, with a model, behind three checks.

`unscripted generate-pack` produces the shape of a world correctly and its prose flat:
*"The innkeeper saw it. So did I."* That is deliberate -- structure is
generatable and words are a writer's job -- but flat prose is what a studio
judges on the first screen, and forty characters is more lines than most people
will rewrite by hand.

So this is the place for a language model, and the place is **build time**. It
rewrites `topics.json` in the setting's voice, the result is committed JSON, and
at play time nothing infers: no latency, no cost per line, nothing that can
hallucinate in front of a player, and a diff a writer can read and argue with.

THE THREE CHECKS, and the reason each exists.

**A leak.** Every secret in a pack lists its `surface_forms` -- the words that
would give it away. A model rewriting a public line has no idea one of those
phrases is load-bearing, and a line that contains one hands the player the thing
the secret exists to protect. Rejected outright.

**A flipped stance.** `affirm` says the thing happened and `deny` says it did
not, and a model asked for a more natural affirmation will occasionally write a
denial. The guard is shallow and I would rather say so than imply otherwise: it
catches lines that are *only* a refusal, not ones that hedge their way into
meaning the opposite. It is worth having anyway, because "no idea" arriving in
the affirm slot is the failure that actually happens.

**Nothing, or the same thing.** Empty, enormous, or a duplicate of a line
already used elsewhere in the pack -- a model that returns the same sentence for
formal and rough has not done the job asked of it.

A LINE THAT FAILS KEEPS ITS ORIGINAL. A pass that cannot improve something must
not damage it, and a half-rewritten pack that still reads consistently is worth
more than one where every third line is a shrug.

And `unscripted author` runs afterwards, like it does on everything else here.
"""
from __future__ import annotations

import json
import os

#: What a rewritten line may not exceed. Longer than a spoken sentence and the
#: dialogue layer will truncate it anyway; the model should be told, not
#: corrected afterwards.
MAX_CHARS = 160

#: Lines that are *only* a refusal. An affirmation that matches one of these
#: has flipped its stance -- see the note in the module docstring about how
#: shallow this check is.
REFUSALS = (
    "no idea", "nothing to say", "i wouldn't know", "i would not know",
    "couldn't tell you", "could not tell you", "not that i know",
    "i know nothing", "no comment", "never heard", "i have nothing",
)

SYSTEM = (
    "You rewrite single lines of game dialogue. You are given one line and the "
    "voice it should have. Return only the rewritten line: no quotation marks, "
    "no explanation, no alternatives, one sentence or two at most. Keep the "
    "meaning exactly -- if the line asserts something, the rewrite asserts it; "
    "if it refuses, the rewrite refuses. Never introduce a name, a place or a "
    "detail that is not already in what you were given."
)

#: How each register should sound. Handed to the model rather than left to it:
#: "rough" means clipped and plain, not a cockney accent, and a model left to
#: guess produces a different guess every run.
REGISTERS = {
    "formal": "careful and a little stiff; complete sentences; no contractions",
    "neutral": "how an ordinary person actually speaks; contractions are fine",
    "rough": "clipped and plain; few words; drops the subject where speech does",
}


class Outcome:
    """What happened to one line, so a summary can be honest about it."""

    def __init__(self):
        self.rewritten = 0
        self.kept = 0
        self.reasons = {}

    def keep(self, why: str):
        self.kept += 1
        self.reasons[why] = self.reasons.get(why, 0) + 1

    def as_dict(self) -> dict:
        return {"rewritten": self.rewritten, "kept": self.kept,
                "reasons": dict(sorted(self.reasons.items()))}


def surface_forms(pack_dir: str) -> set:
    """Every phrase that would give away a secret in this pack."""
    found = set()
    characters = os.path.join(pack_dir, "characters")
    if not os.path.isdir(characters):
        return found
    for name in sorted(os.listdir(characters)):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(characters, name), encoding="utf-8") as handle:
            character = json.load(handle)
        for secret in character.get("secrets") or []:
            if isinstance(secret, dict):
                for form in secret.get("surface_forms") or []:
                    if str(form).strip():
                        found.add(str(form).strip().lower())
    return found


def acceptable(line: str, *, stance: str, forbidden: set, already: set) -> str:
    """`""` if the line is usable, otherwise why it is not."""
    text = (line or "").strip().strip('"').strip()
    if not text:
        return "empty"
    if len(text) > MAX_CHARS:
        return "too long"
    lowered = text.lower()
    for phrase in forbidden:
        if phrase in lowered:
            return "would leak a secret"
    if stance == "affirm" and any(lowered.startswith(r) or lowered == r
                                  for r in REFUSALS):
        return "affirmation reads as a refusal"
    if lowered in already:
        return "duplicate of another line"
    return ""


def rewrite_pack(pack_dir: str, provider, *, model_id: str,
                 voice: str = "", on_line=None) -> dict:
    """Rewrite every phrasing in `topics.json`. Returns a summary.

    `provider` needs one method: `chat(payload) -> str`, the shape
    `HttpModelProvider` speaks. Anything OpenAI-compatible fits, including a
    model on the machine doing the build.
    """
    topics_path = os.path.join(pack_dir, "topics.json")
    with open(topics_path, encoding="utf-8") as handle:
        document = json.load(handle)

    forbidden = surface_forms(pack_dir)
    if not voice:
        scenario = os.path.join(pack_dir, "scenario.json")
        if os.path.exists(scenario):
            with open(scenario, encoding="utf-8") as handle:
                voice = (json.load(handle).get("intro") or "").strip()

    outcome = Outcome()
    already = set()
    for topic in document.get("topics", []):
        label = topic.get("label") or topic.get("id", "")
        for stance in ("affirm", "deny"):
            block = (topic.get("phrasings") or {}).get(stance) or {}
            for register in sorted(block):
                original = block[register]
                prompt = _prompt(original, label=label, stance=stance,
                                 register=register, voice=voice)
                try:
                    answer = provider.chat({
                        "model": model_id,
                        "messages": [{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": prompt}],
                        # Low but not zero: identical lines for formal and rough
                        # is the failure a temperature of 0 produces.
                        "temperature": 0.5,
                        "max_tokens": 90,
                    })
                except Exception as exc:                  # provider is foreign
                    outcome.keep("provider failed: %s" % type(exc).__name__)
                    if on_line:
                        on_line(topic.get("id"), stance, register, original, str(exc))
                    continue
                why = acceptable(answer, stance=stance, forbidden=forbidden,
                                 already=already)
                if why:
                    outcome.keep(why)
                    if on_line:
                        on_line(topic.get("id"), stance, register, original, why)
                    continue
                cleaned = answer.strip().strip('"').strip()
                block[register] = cleaned
                already.add(cleaned.lower())
                outcome.rewritten += 1
                if on_line:
                    on_line(topic.get("id"), stance, register, cleaned, "")

    if outcome.rewritten:
        with open(topics_path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return outcome.as_dict()


def _prompt(original: str, *, label: str, stance: str, register: str,
            voice: str) -> str:
    said = ("The speaker is confirming this happened."
            if stance == "affirm" else
            "The speaker is refusing, or saying they do not know.")
    lines = []
    if voice:
        lines.append("The setting:\n%s\n" % voice.strip())
    lines.append("The subject: %s" % label)
    lines.append(said)
    lines.append("Voice: %s" % REGISTERS.get(register, register))
    lines.append("")
    lines.append("Rewrite this line:")
    lines.append(original)
    return "\n".join(lines)
