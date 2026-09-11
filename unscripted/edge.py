"""Running a language model on the machine the game is on.

A local model is the only kind this runtime encourages: no per-interaction cost,
no network, no vendor who can deprecate your NPCs. But a game has a frame budget
and a model does not care about it. Measured against ollama on one desktop GPU:

    qwen3-vl:4b-instruct     cold  7,493 ms   warm  290 ms
    abliterated 4b (q4_K_M)  cold  6,796 ms   warm  281 ms
    abliterated 8b (q4_K_M)  cold 25,234 ms   warm  361 ms

Two separate problems live in those numbers, and they need different answers.

**Cold start.** The first line of a session costs seven to twenty-five seconds
while the model is paged into VRAM. No budget can hide that; the model has to be
resident before the player talks to anyone. :meth:`warm_up` does that at load
time and reports what it cost.

**Warm latency.** ~300 ms is far past a frame and fine for a dialogue turn --
*if nothing blocks on it*. So the runtime does not wait: it answers immediately
from the deterministic realizer and, if the model produces something better in
time, offers it as an upgrade the game can swap in on a later frame. The player
sees a line at once, and a validated model line replaces it a few frames later or
never.

Both paths end at the same validator. A deferred line is not released because it
arrived; it is released because it passed the same canon and secret checks as any
other generated text.
"""
from __future__ import annotations

import concurrent.futures
import copy
import threading
import time

from .provider import HttpChatRealizer, ProviderError


class ProviderPending(ProviderError):
    """The model did not answer inside the frame budget.

    Deliberately a ProviderError: every existing fallback path already handles
    one, so a busy model degrades to authored text through code that is already
    tested, rather than through a second mechanism.
    """


class DeferredRealizer:
    """Answer within a budget; upgrade later if the model is worth waiting for.

    Wraps any realizer. :meth:`realize` waits at most ``budget_ms``. If the model
    beats the budget its line is returned directly. If not, the request keeps
    running in the background and ``realize`` raises :class:`ProviderPending`, so
    the caller falls back to authored text this turn. The finished line is then
    available from :meth:`take_ready` for the caller to validate and swap in.
    """

    is_deterministic = False

    def __init__(self, inner, *, budget_ms: int = 120, max_pending: int = 8,
                 workers: int = 2):
        self.inner = inner
        self.budget_ms = budget_ms
        self.max_pending = max_pending
        self.model_id = getattr(inner, "model_id", "deferred")
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="unscripted-realizer")
        self._pending: dict = {}
        self._lock = threading.Lock()
        self.stats = {"served_within_budget": 0, "deferred": 0, "dropped_overloaded": 0,
                      "upgrades_ready": 0, "failed": 0}

    # ------------------------------------------------------------- lifecycle --
    def close(self):
        self._pool.shutdown(wait=False, cancel_futures=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---------------------------------------------------------------- realize --
    def realize(self, plan, style) -> str:
        request_id = getattr(plan, "request_id", None)
        with self._lock:
            overloaded = len(self._pending) >= self.max_pending
        if overloaded:
            # A backlog means the model cannot keep up with the scene. Queuing more
            # only makes every later line staler; refuse now and let the caller use
            # authored text.
            self.stats["dropped_overloaded"] += 1
            raise ProviderPending(
                f"{len(self._pending)} generations already in flight; not queuing another")

        future = self._pool.submit(self.inner.realize, plan, style)
        try:
            text = future.result(timeout=self.budget_ms / 1000.0)
            self.stats["served_within_budget"] += 1
            return text
        except concurrent.futures.TimeoutError:
            if request_id is None:
                # Nobody can collect this later, so let it finish and be discarded
                # rather than leaking a slot.
                self.stats["deferred"] += 1
                raise ProviderPending(f"no line within {self.budget_ms} ms") from None
            with self._lock:
                # Snapshot the plan. The caller falls back on ProviderPending and
                # that path MUTATES the plan it was given (dialogue_act becomes the
                # fallback template). Holding the live object would validate the
                # late line against a plan that has since changed underneath it.
                self._pending[request_id] = (future, copy.deepcopy(plan),
                                             dict(style) if isinstance(style, dict) else style,
                                             time.monotonic())
            self.stats["deferred"] += 1
            raise ProviderPending(f"no line within {self.budget_ms} ms") from None
        except ProviderError:
            self.stats["failed"] += 1
            raise
        except Exception as exc:                      # a provider bug is not a crash
            self.stats["failed"] += 1
            raise ProviderError(f"{type(exc).__name__}: {exc}") from exc

    # ----------------------------------------------------------------- upgrade --
    def take_ready(self) -> list:
        """Collect generations that have finished since the last call.

        Returns ``[(request_id, plan, style, text)]``. The caller must validate the
        text before releasing it: arriving is not the same as being safe to say.
        """
        ready = []
        with self._lock:
            done = [rid for rid, (future, *_rest) in self._pending.items() if future.done()]
            for request_id in done:
                future, plan, style, _started = self._pending.pop(request_id)
                try:
                    ready.append((request_id, plan, style, future.result()))
                except Exception:
                    self.stats["failed"] += 1
        self.stats["upgrades_ready"] += len(ready)
        return ready

    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)


# ------------------------------------------------------------------ warm-up --

def warm_up(realizer, *, attempts: int = 2) -> dict:
    """Force the model resident and measure what a warm call costs.

    The first request to a cold local model pays for loading weights into VRAM --
    seven seconds for a 4B, twenty-five for an 8B in measurement. That cost lands
    on whichever NPC the player happens to talk to first. Paying it at load time
    turns it into a loading screen instead of a broken conversation.
    """
    from .dialogue import DialoguePlan

    plan = DialoguePlan(speaker="warmup", addressee="warmup", dialogue_act="greet",
                        goal="warm the model", allowed_facts=[], avoid_topics=[],
                        style={"formality": 0.5}, max_length=8)
    timings = []
    error = None
    for _ in range(max(1, attempts)):
        started = time.perf_counter()
        try:
            realizer.realize(plan, plan.style)
            timings.append((time.perf_counter() - started) * 1000.0)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            break
    return {
        "model_id": getattr(realizer, "model_id", "?"),
        "cold_ms": round(timings[0], 1) if timings else None,
        "warm_ms": round(min(timings[1:]), 1) if len(timings) > 1 else (
            round(timings[0], 1) if timings else None),
        "ok": bool(timings) and error is None,
        "error": error,
    }


# ------------------------------------------------------- capability probing --

#: What a model must manage to be worth using for NPC lines at all.
#: Facts are written with ENGINE core predicates and placeholder ids on purpose:
#: probing must not smuggle any particular world's vocabulary into the engine, and
#: a probe that used a real pack's terms would also be measuring that pack.
PROBE_CASES = (
    ("states_the_fact", "inform",
     ["NOT space:exactly_at(entity=entity:one, place=place:one)"],
     lambda text: len(text.split()) <= 20),
    ("stays_short", "evade", [], lambda text: len(text.split()) <= 20),
    ("no_scaffolding", "inform",
     ["was_at(agent=agent:one, place=place:one, when=earlier)"],
     lambda text: not any(marker in text.lower() for marker in
                          ("allowed_facts", "dialogue_act", "avoid_topics", "{"))),
)


def probe_model(realizer, *, budget_ms: int | None = None) -> dict:
    """Decide at startup whether this model can voice NPCs, and say so.

    A small "thinking" model emits reasoning that gets cleaned away, so nearly
    every line ends up as the authored fallback. That is safe but pointless, and
    discovering it line by line during play tells nobody anything. One probe at
    load time turns it into a startup message a developer can act on.
    """
    from .dialogue import DialoguePlan

    results = {}
    latencies = []
    for name, act, facts, check in PROBE_CASES:
        plan = DialoguePlan(speaker="probe", addressee="probe", dialogue_act=act,
                            goal="answer", allowed_facts=list(facts), avoid_topics=[],
                            style={"formality": 0.5}, max_length=24)
        started = time.perf_counter()
        try:
            text = realizer.realize(plan, plan.style)
            latencies.append((time.perf_counter() - started) * 1000.0)
            results[name] = {"passed": bool(text) and check(text), "sample": text[:120]}
        except Exception as exc:
            results[name] = {"passed": False, "sample": "", "error": f"{type(exc).__name__}: {exc}"}

    passed = sum(1 for r in results.values() if r["passed"])
    typical = round(sorted(latencies)[len(latencies) // 2], 1) if latencies else None
    usable = passed == len(PROBE_CASES)
    verdict = ("usable" if usable else
               "degraded" if passed else
               "unusable")
    advice = {
        "usable": "model produces clean in-character lines",
        "degraded": (f"{len(PROBE_CASES) - passed} of {len(PROBE_CASES)} checks failed; "
                     "many lines will fall back to authored text"),
        "unusable": ("no check passed; every line will be authored text. Use a "
                     "non-thinking instruct model, or run without a provider"),
    }[verdict]
    if typical is not None and budget_ms is not None and typical > budget_ms:
        advice += (f". Typical latency {typical:.0f} ms exceeds the {budget_ms} ms budget, "
                   f"so lines will arrive as deferred upgrades rather than immediately")
    return {"model_id": getattr(realizer, "model_id", "?"), "verdict": verdict,
            "passed": passed, "of": len(PROBE_CASES), "typical_ms": typical,
            "advice": advice, "cases": results}


def build_edge_realizer(*, endpoint: str, model_id: str, api_key: str | None = None,
                        budget_ms: int = 120, timeout: float = 20.0,
                        deferred: bool = True):
    """The realizer stack a local model should normally run behind."""
    http = HttpChatRealizer(endpoint=endpoint, api_key=api_key, model_id=model_id,
                            timeout=timeout)
    return DeferredRealizer(http, budget_ms=budget_ms) if deferred else http
