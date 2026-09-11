"""Model provider + text realizer adapters.

The realizer turns a DialoguePlan + StyleVector into text. The default
TemplateRealizer is fully deterministic and register-aware -- it varies output by
formality, slang, sentence length and directness, so the runtime can operate
without any external model. A real LLM provider implements the same
interface and receives the style vector as prompt constraints; its output is then
buffered and validated (never streamed unvalidated).
"""
from __future__ import annotations
from typing import Protocol
import json
import re
import urllib.error
import urllib.request


class ModelProvider(Protocol):
    def realize(self, plan, style) -> str: ...


class ProviderError(RuntimeError):
    pass


class TemplateRealizer:
    """Deterministic, register-aware realizer.

    The built-in templates express a *stance* -- evading, threatening, asking to
    be paid, greeting, having nothing to add -- and deliberately assert no world
    facts. There is no built-in ``inform``: stating what is true about a world is
    the world's job, not the engine's.

    That distinction matters. The default ``inform`` template used to read "the
    place was shut that night", a sentence about the reference scene's clinic. Any
    other pack inherited it, so a character could assert something they did not
    believe and that was not true in their world. A topic now supplies its own
    phrasings (``topics.json``), and without one the realizer falls back to a safe
    deflection rather than inventing a fact.

    Packs may also override or extend any act template and supply their own slang
    lexicon through ``world.json``.
    """

    #: Output is authored text, so canon parse-back is unnecessary by construction.
    is_deterministic = True

    #: Stance templates: register variants that make no factual claim.
    DEFAULT_TEMPLATES = {
        "evade": {
            "formal": "I am afraid that is not something I am able to discuss.",
            "neutral": "Not sure that's any of your business.",
            "vernacular": "Maybe. Why do you care?",
        },
        "threaten": {
            "formal": "I would strongly advise you to reconsider your line of questioning.",
            "neutral": "Walk away while you still can.",
            "vernacular": "Back off. Now.",
        },
        "request": {
            "formal": "I would be much obliged if you settled what you owe.",
            "neutral": "You still owe me. Time to pay.",
            "vernacular": "Where's my money?",
        },
        "greet": {
            "formal": "Good evening.",
            "neutral": "Evening.",
            "vernacular": "Hey.",
        },
        "deflect": {  # safe fallback
            "formal": "I have nothing further to add.",
            "neutral": "I've got nothing for you.",
            "vernacular": "Nothin' to say.",
        },
    }

    def __init__(self, templates: dict | None = None, slang: dict | None = None):
        self.templates = dict(self.DEFAULT_TEMPLATES)
        for act, variants in (templates or {}).items():
            self.templates[act] = {**self.templates.get(act, {}), **variants}
        self.slang = dict(slang or {})

    @classmethod
    def for_world(cls, world) -> "TemplateRealizer":
        """Realizer carrying this world's authored templates and slang lexicon."""
        return cls(templates=getattr(world, "dialogue_templates", None),
                   slang=getattr(world, "slang_lexicon", None))

    @staticmethod
    def _register(formality):
        if formality >= 0.6:
            return "formal"
        if formality <= 0.3:
            return "vernacular"
        return "neutral"

    def variants(self, plan, style) -> list:
        """Every complete wording of this plan, best register first.

        For an anti-repeat retry to be safe it has to choose between COMPLETE
        realizations of the same commitment -- never between saying it and not
        saying it. So these are the authored variants for this answer, or the
        stance variants for this act, and nothing else.
        """
        source = dict(plan.phrasing or {}) or dict(
            self.templates.get(plan.dialogue_act) or {})
        preferred = self._register(style.get("formality", 0.5))
        order = [preferred] + [r for r in ("neutral", "formal", "vernacular")
                               if r != preferred]
        seen, out = set(), []
        for register in order:
            line = source.get(register)
            if line and line not in seen:
                seen.add(line)
                out.append(line)
        return out

    def _lookup(self, plan, register: str) -> str | None:
        """Authored phrasing for this plan, if any, else the stance template."""
        phrasing = (plan.phrasing or {})
        if phrasing:
            return phrasing.get(register) or phrasing.get("neutral") or next(
                iter(phrasing.values()), None)
        variants = self.templates.get(plan.dialogue_act)
        if not variants:
            return None
        return variants.get(register) or variants.get("neutral")

    def realize(self, plan, style) -> str:
        reg = self._register(style.get("formality", 0.5))
        authored = bool(plan.phrasing)
        text = self._lookup(plan, reg)
        # DID THESE WORDS CARRY THE COMMITMENT. A stance template does not, and
        # this used to answer "was there a template at all" -- so a plan carrying
        # facts, realised from a STANCE template because the pack authored no
        # phrasing for them, still reported the commitment as expressed. What is
        # committed becomes a world event, so the answer has to be about the
        # authored phrasing for this answer, not about any string being available.
        factual = any(getattr(move, "is_factual", False) for move in plan.moves)
        self.expressed_commitment = authored if factual else True
        if text is None:
            # No authored phrasing and no stance template for this act: say nothing
            # factual rather than borrowing another world's sentence.
            text = self.templates["deflect"][reg]
        # slang substitution for in-group/low-formality speakers
        if self.slang and style.get("slang_level", 0.0) > 0.3:
            words = []
            for w in text.split():
                key = w.strip(".,!?").lower()
                repl = self.slang.get(key)
                words.append(repl + w[len(key):] if repl else w)
            text = " ".join(words)
        # SENTENCE-LENGTH PRESSURE NEVER CUTS A LINE THAT CARRIES A CLAIM.
        #
        # Keeping the first sentence is a reasonable stylistic squeeze on a stance
        # line and a silent content loss on a factual one: an authored answer
        # reading "Listen carefully. Place was shut that night. That's all I got."
        # became "Listen carefully." for an agitated speaker -- while the claim
        # about the place still propagated, because the flag had already been set
        # before the edit. Style may choose between complete realizations; it may
        # not remove what the runtime committed to saying.
        if (not factual and style.get("mean_sentence_length", 12) < 7
                and "." in text):
            text = text.split(".")[0].strip().rstrip(".") + "."
        return text


class RecordingTemplateRealizer:
    """Deterministic text provider that records the structured realization input."""

    is_deterministic = True

    def __init__(self):
        self._tr = TemplateRealizer()
        self.last_prompt_constraints = None

    def realize(self, plan, style) -> str:
        self.last_prompt_constraints = {"act": plan.dialogue_act, "allowed_facts": plan.allowed_facts,
                                        "avoid_topics": plan.avoid_topics, "style": style}
        return self._tr.realize(plan, style)


class HttpChatRealizer:
    """Dependency-free adapter for OpenAI-compatible local or hosted chat endpoints.

    The adapter is intentionally thin: it sends only the dialogue plan, allowed
    facts, avoided topics and style vector. The runtime still buffers and
    validates the returned text before releasing it.
    """

    #: A language model writes these lines, so every specific must be checked
    #: against the plan before release (validator layer 3b).
    is_deterministic = False

    def __init__(self, endpoint: str, api_key: str | None = None,
                 model_id: str = "local-chat", timeout: float = 20.0):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_id = model_id
        self.timeout = timeout
        self.last_request = None
        self.last_response = None

    SYSTEM = (
        "You voice a single game NPC. Reply with EXACTLY ONE short in-character line "
        "of spoken dialogue and nothing else.\n"
        "Hard rules:\n"
        "- State EXACTLY what you are told to state. You are not choosing what to "
        "say; you are wording a decision that has already been made.\n"
        "- Say all of it, add nothing, and never invent names, places or events.\n"
        "- Never mention or hint at any avoid_topics.\n"
        "- Match the dialogue_act and style (formality, slang, brevity).\n"
        "- No narration, no quotes, no stage directions, no explanations, no lists, "
        "no meta commentary, no analysis, no 'Thinking'/'Answer' labels.\n"
        "- Output is one sentence the character actually says. /no_think"
    )

    # plain-text reasoning labels weak 'thinking' models emit around the real line
    _LABEL = re.compile(r"(?i)^(thinking process|reasoning|analysis|thought|note|"
                        r"answer|final answer|response|reply|output)\s*:?\s*$")
    _ANSWER_SPLIT = re.compile(r"(?i)\b(?:final answer|answer|response|reply|output)\s*:\s*")

    # markers that mean the model echoed our scaffolding instead of speaking in character
    _SCAFFOLD = ("dialogue_act", "avoid_topics", "allowed_facts", "addressee",
                 "max_length", "agent:", "{")

    @classmethod
    def _clean(cls, text: str, max_length: int) -> str:
        """Reduce a chatty small-model reply to one safe in-character line.

        Returns "" when the reply is unusable (empty, or an echo of the prompt
        scaffolding); the caller turns that into a ProviderError so the runtime
        falls back to the validated deterministic template instead of leaking
        internal plan data (allowed_facts / avoid_topics) to the player.
        """
        # drop chain-of-thought blocks some models emit (e.g. qwen <think>...</think>)
        text = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"</?think>", " ", text, flags=re.IGNORECASE)
        # cut at the first leaked chat-template special token (<|im_start|>, <|endoftext|>, ...)
        text = re.split(r"<\|", text, maxsplit=1)[0]
        # strip markdown emphasis/heading characters so "**Heading:**" -> "Heading:"
        text = re.sub(r"[*_`#]+", "", text)
        # if a labeled reasoning preamble exists, keep only what follows the answer label
        parts = cls._ANSWER_SPLIT.split(text)
        if len(parts) > 1 and parts[-1].strip():
            text = parts[-1]
        # split into lines and drop pure reasoning-label lines ("Thinking Process:")
        lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n") if ln.strip()]
        lines = [ln for ln in lines if not cls._LABEL.match(ln)]
        text = lines[0] if lines else ""
        # strip surrounding quotes/markdown and leading speaker labels ("Barkeep:")
        text = text.strip().strip('"').strip("'").lstrip("*").strip()
        text = re.sub(r"^[A-Z][\w '\-]{0,24}:\s+", "", text)
        # strip a leading list/bullet marker ("1.", "2)", "- ", "* ")
        text = re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", text).strip()
        # quotes/labels may have exposed an inner quote ('Vee: "Back off."') -> strip again
        text = text.strip().strip('"').strip("'").strip()
        # reject scaffolding echoes / leftover labels / non-utterances -> safe fallback
        low = text.lower()
        if (not text or text.endswith(":") or not re.search(r"[A-Za-z]", text)
                or any(marker in low for marker in cls._SCAFFOLD)):
            return ""
        # keep the first sentence so we never release a rambling paragraph
        parts = re.split(r"(?<=[.!?])\s+", text)
        if parts and parts[0]:
            text = parts[0].strip()
        # hard character cap derived from the plan's length budget
        cap = max(40, max_length * 8)
        if len(text) > cap:
            text = text[:cap].rsplit(" ", 1)[0].rstrip(",;:") + "."
        return text.strip()

    @staticmethod
    def _build_user_prompt(plan, style) -> str:
        """Natural-language instructions (not raw JSON) -- weak models echo JSON."""
        # The commitment, not a menu. `allowed_facts` is exactly what the runtime
        # decided this character says -- selecting among options was the model's
        # job until it turned out that choosing which fact reaches a listener IS
        # deciding what enters the society.
        moves = list(getattr(plan, "moves", ()) or ())
        facts = plan.allowed_facts or []
        avoid = plan.avoid_topics or []
        formality = style.get("formality", 0.5)
        register = "formal" if formality >= 0.6 else "rough/streetwise" if formality <= 0.3 else "plain"
        slang = "use street slang" if style.get("slang_level", 0.0) > 0.3 else "little slang"
        lines = [
            f"Write the single line {plan.speaker} says to {plan.addressee}.",
            f"Intent: {plan.dialogue_act}. Goal: {plan.goal}.",
        ]
        if moves:
            hedge = {"certain": "as plain fact",
                     "probable": "as something you believe but were not there for",
                     "uncertain": "hesitantly, as something you are unsure of"}
            for move in moves:
                if not getattr(move, "is_factual", False):
                    continue
                lines.append(
                    f"Say this, {hedge.get(move.certainty, 'plainly')}: "
                    f"{move.rendered()}")
            lines.append("Say all of the above and nothing else of substance.")
        elif facts:
            lines.append("Say exactly this and nothing else of substance: "
                         + "; ".join(facts))
        else:
            lines.append("You have no concrete facts to share; stay vague.")
        if avoid:
            lines.append("NEVER mention or hint at: " + "; ".join(avoid) + ".")
        lines.append(f"Tone: {register}, {slang}, at most {max(4, plan.max_length // 4)} words.")
        lines.append("Reply with ONLY the spoken line, no quotes, no labels, no JSON.")
        return "\n".join(lines)

    def chat(self, payload: dict) -> str:
        """One chat-completions call. Returns the assistant's text.

        Lifted out of `realize` unchanged, because the build-time phrasing pass
        needs a plain prompt-in-text-out call and the only HTTP client in this
        package was welded to the dialogue path. `realize` still shapes its own
        payload and still cleans its own answer; this is the transport.
        """
        self.last_request = payload
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.endpoint, data=body, headers=headers,
                                     method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise ProviderError(f"Text provider request failed: {exc}") from exc
        self.last_response = raw
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError("Text provider returned invalid JSON.") from exc
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "Text provider response did not match chat-completions shape.") from exc

    def realize(self, plan, style) -> str:
        payload = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": self.SYSTEM},
                {"role": "user", "content": self._build_user_prompt(plan, style)},
            ],
            "temperature": 0.4,
            "max_tokens": max(32, int(plan.max_length * 3)),
        }
        content = self.chat(payload)
        cleaned = self._clean(content or "", plan.max_length)
        if not cleaned:
            raise ProviderError("Text provider returned an empty utterance after cleaning.")
        return cleaned
