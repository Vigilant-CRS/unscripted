"""The action bridge: intents out, results back.

Everything the runtime decides has so far been either a belief or a sentence.
Both are cheap to be wrong about, because nothing in the visible world depends on
them. Movement is not: the routine layer sets `agent.location` directly, and an
engine that renders the same character somewhere else now has two worlds -- one
the player sees, one the simulation reasons about. Nothing detects the split,
because nothing ever asked the engine whether the character actually got there.

So a physical act becomes a two-step exchange:

    runtime            engine
      |  MOVE_TO(dock)   |      the runtime states an INTENT and does not move
      | ---------------> |      anyone; the character is still where he was
      |                  |      the engine walks him, or fails to
      |   SUCCEEDED      |
      | <--------------- |      only now does the world change
      |                  |

The four results are the ones an engine can actually distinguish: it did it, it
tried and failed, something cut it short, or the destination cannot be reached
from where the character stands. A fifth, TIMED_OUT, is the runtime's own: an
engine that never answers must not pin a character in a pending state forever.
An expired intent is treated as a failure -- the character stays put, which is
what the engine is showing -- and counted, because a build quietly timing out
every intent looks identical to a build with no bridge attached.

**Off by default, and off means unchanged.** With `action_bridge=False` the
runtime moves people itself exactly as before, this module issues nothing, and
`capabilities.action_bridge` reports false. A studio without an integration is
not made to build one.

This module converts and records. It never decides what to issue and never
applies an effect -- the world layer does both, which is why this sits in
adapters and not above it.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


#: The closed catalogue of what the runtime asks an engine to do.
#:
#: One entry, deliberately. `MOVE_TO` is emitted because relocation is the one
#: physical act the runtime already decides on its own -- routines move the cast
#: every day, and that is the divergence worth closing first. `WARN` and `GIVE`
#: appear in the roadmap and are NOT here, because nothing in the runtime decides
#: them yet: an intent type that is declared but never issued reads to an
#: integrator as a channel they have to handle, and it would never fire.
INTENT_TYPES = ("MOVE_TO",)

#: What an engine may report back.
ENGINE_RESULTS = ("SUCCEEDED", "FAILED", "INTERRUPTED", "UNREACHABLE")

#: What the runtime concludes when nobody reports at all.
TIMED_OUT = "TIMED_OUT"

RESULTS = ENGINE_RESULTS + (TIMED_OUT,)

#: Results after which the intended effect is applied. Exactly one.
APPLIED = ("SUCCEEDED",)


@dataclass(frozen=True)
class ActionIntent:
    """One thing the runtime has asked the engine to do, and has not seen resolved."""
    intent_id: str
    actor: str
    type: str
    params: dict
    reason: str
    issued_at: int                 # world time, minutes
    expires_at: int                # world time after which it is TIMED_OUT

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedIntent:
    intent: ActionIntent
    status: str
    detail: str
    resolved_at: int
    applied: bool

    def as_dict(self) -> dict:
        return {**self.intent.as_dict(), "status": self.status, "detail": self.detail,
                "resolved_at": self.resolved_at, "applied": self.applied}


class UnknownIntent(LookupError):
    """Asked about an intent this runtime never issued, or already resolved.

    LookupError rather than KeyError on purpose: KeyError's ``str()`` wraps the
    message in quotes, and this message is shown to an integrator over HTTP.
    """


class InvalidResult(ValueError):
    """An engine reported something outside the closed result set."""


@dataclass
class ActionBridge:
    """Pending intents and their outcomes. Deterministic, serialisable, off by default."""

    enabled: bool = False
    #: World minutes an intent may stay pending. A day-long routine block with a
    #: sixty-minute window means a character who cannot be walked is late for one
    #: block, not stuck forever.
    timeout_minutes: int = 60
    _pending: dict = field(default_factory=dict)
    _resolved: list = field(default_factory=list)
    _counter: int = 0
    #: Kept as a tally rather than derived from `_resolved`, which is trimmed.
    counts: dict = field(default_factory=lambda: {r: 0 for r in RESULTS})

    # ------------------------------------------------------------- issuing ----

    def issue(self, *, actor: str, type: str, params: dict, reason: str,
              world_time: int) -> ActionIntent:
        """Record an intent and return it. Applies nothing."""
        if type not in INTENT_TYPES:
            raise ValueError(f"not an intent this runtime issues: {type!r}. "
                             f"Known: {', '.join(INTENT_TYPES)}")
        self._counter += 1
        # Derived from actor, time and an ordinal: replaying the same session
        # reproduces the same ids, so a recorded engine result still matches.
        intent = ActionIntent(
            intent_id=f"intent:{actor}:{world_time}:{self._counter}",
            actor=actor, type=type, params=dict(params), reason=reason,
            issued_at=world_time, expires_at=world_time + self.timeout_minutes)
        self._pending[intent.intent_id] = intent
        return intent

    def pending(self) -> list:
        """Everything the engine still owes an answer for, oldest first."""
        return sorted(self._pending.values(), key=lambda i: (i.issued_at, i.intent_id))

    def pending_for(self, actor: str) -> list:
        return [i for i in self.pending() if i.actor == actor]

    def has_pending(self, actor: str, type: str) -> bool:
        """Whether this character is already mid-act, so nothing issues twice."""
        return any(i.actor == actor and i.type == type for i in self._pending.values())

    # ----------------------------------------------------------- resolving ----

    def resolve(self, intent_id: str, status: str, *, world_time: int,
                detail: str = "") -> ResolvedIntent:
        """Close an intent with what the engine reported.

        Returns the record; the caller decides what, if anything, to apply --
        `record.applied` says whether the effect should happen.
        """
        status = str(status or "").upper()
        if status not in ENGINE_RESULTS:
            raise InvalidResult(
                f"{status!r} is not a result an engine may report. "
                f"Use one of: {', '.join(ENGINE_RESULTS)}.")
        return self._close(intent_id, status, world_time=world_time, detail=detail)

    def expire(self, world_time: int) -> list:
        """Time out every intent past its window. Deterministic in world time."""
        overdue = [i.intent_id for i in self.pending() if world_time > i.expires_at]
        return [self._close(iid, TIMED_OUT, world_time=world_time,
                            detail="no result was reported before the intent expired")
                for iid in overdue]

    def _close(self, intent_id: str, status: str, *, world_time: int,
               detail: str) -> ResolvedIntent:
        intent = self._pending.pop(intent_id, None)
        if intent is None:
            raise UnknownIntent(
                f"no pending intent {intent_id!r}. It was never issued, or it has "
                f"already been resolved -- a second result for one intent is a bug "
                f"in the integration, not a state this runtime holds.")
        record = ResolvedIntent(intent=intent, status=status, detail=str(detail or ""),
                                resolved_at=world_time, applied=status in APPLIED)
        self.counts[status] = self.counts.get(status, 0) + 1
        self._resolved.append(record)
        # The ledger is the audit trail; this list only has to answer "what
        # happened recently" for the inspector, so it stays bounded.
        if len(self._resolved) > 256:
            del self._resolved[:-256]
        return record

    # ------------------------------------------------------------ read model --

    def recent(self, limit: int = 20) -> list:
        return self._resolved[-limit:]

    def report(self) -> dict:
        """What an integrator needs to see at a glance."""
        issued = sum(self.counts.values()) + len(self._pending)
        return {
            "enabled": self.enabled,
            "issued": issued,
            "pending": len(self._pending),
            "timeout_minutes": self.timeout_minutes,
            **{status.lower(): self.counts.get(status, 0) for status in RESULTS},
        }

    # ------------------------------------------------------------ snapshot ----

    def as_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "timeout_minutes": self.timeout_minutes,
            "counter": self._counter,
            "counts": dict(self.counts),
            "pending": [i.as_dict() for i in self.pending()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ActionBridge":
        bridge = cls(enabled=bool(data.get("enabled", False)),
                     timeout_minutes=int(data.get("timeout_minutes", 60)))
        bridge._counter = int(data.get("counter", 0))
        bridge.counts = {r: int(data.get("counts", {}).get(r, 0)) for r in RESULTS}
        for raw in data.get("pending", []):
            intent = ActionIntent(
                intent_id=raw["intent_id"], actor=raw["actor"], type=raw["type"],
                params=dict(raw.get("params") or {}), reason=raw.get("reason", ""),
                issued_at=int(raw["issued_at"]), expires_at=int(raw["expires_at"]))
            bridge._pending[intent.intent_id] = intent
        return bridge
