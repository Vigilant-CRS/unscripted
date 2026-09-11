"""BeliefEngine (Technical Core v0.2 §2; Ontology v0.3 §8.2; spec v0.5 §5.7).

Beliefs are subjective probabilities updated in log-odds. A source asserting a
proposition is evidence whose strength is the source's reliability kappa.
Dual evidence (support_for / support_against) distinguishes ignorance from conflict.
Correlation discounting prevents one rumor repeated by ten people from becoming
certainty.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from .types import sigmoid, logit, clamp
from .ontology import Proposition, contradicts


def _origin_key(origin_event) -> str:
    """Canonical, JSON-safe key for an evidence origin."""
    return str(origin_event)


#: Separates the two halves of a contribution key. A unit separator, because it
#: cannot occur in an agent id or an origin token and so cannot be forged by one.
_CONTRIB_SEP = "\x1f"

#: Where contributions go when a belief has heard from more distinct
#: (speaker, origin) PAIRS than it retains. They still count towards the log-odds
#: -- the evidence was real -- but they can no longer be attributed, so revision
#: cannot unwind them. Stated rather than hidden: `provenance_dropped` says how
#: much of the readable history went, and this bucket says the arithmetic behind
#: it is no longer separable.
#:
#: NOT the same bound as the origin index, which does not evict at all
#: (`Belief.origins_refused`). One origin can reach a belief through many
#: mouths, so this index can fill while the origin index has not: the pairs are
#: what `revision` matches on, and only attributability is lost here -- never the
#: guarantee about how much one origin is worth.
FORGOTTEN = _CONTRIB_SEP + "forgotten"


def _contribution_key(speaker, origin_event) -> str:
    """Who said it and which origin it carried, as one JSON-safe key.

    This is exactly the pair `revision` matches on, which is why the cumulative
    arithmetic is filed under it rather than under either half alone.
    """
    return (("" if speaker is None else str(speaker)) + _CONTRIB_SEP
            + ("" if origin_event is None else _origin_key(origin_event)))


@dataclass
class Belief:
    proposition: Proposition
    logit_val: float = 0.0             # log-odds of the proposition holding
    support_for: float = 0.0           # accumulated positive log-evidence
    support_against: float = 0.0       # accumulated negative log-evidence
    provenance: list = field(default_factory=list)   # list of dicts: claim_id, origin_event, kappa
    valid_start: int = None
    txn_time: int = None
    #: Distinct origin events already counted, and how often each was heard. This
    #: is what correlation discounting actually asks about, so it is stored as the
    #: set it is: a linear scan over an ever-growing provenance list made every
    #: belief update O(claims) and let a long session grow the record without bound
    #: (13 entries for 2 beliefs after 18 turns).
    origin_counts: dict = field(default_factory=dict)
    #: Provenance entries dropped to stay within the retention limit; surfaced so
    #: the inspector never implies a belief has less history than it does.
    provenance_dropped: int = 0
    #: Cumulative signed log-odds contributed, per (speaker, origin), as
    #: ``[positive, negative]``.
    #:
    #: THIS IS THE ARITHMETIC RECORD, and it exists because the provenance list
    #: is not one. That list is trimmed to the newest 64 entries for the
    #: inspector, and `revision` used to sum the deltas *in it* -- so after a
    #: claim had been heard often enough, the early, heavy entries were gone and
    #: exposing the source who supplied them changed nothing at all. Measured:
    #: 100 hearings from one source, discredited to a tenth, moved the belief
    #: from 0.96344 to 0.96344.
    contributions: dict = field(default_factory=dict)
    #: Distinct origins this belief turned away because its index was full.
    #: They contributed NO evidence -- see `BeliefEngine.correlation_discount`.
    #:
    #: THE INDEX DOES NOT EVICT, and that is the whole of the global bound.
    #: Two earlier designs tried to keep evicting and pay for it afterwards, and
    #: both leaked, because an index that forgets cannot recognise a repeat and
    #: any correction applied at re-admission is a correction to one step of an
    #: unbounded sequence:
    #:
    #:   * evicting outright let a source return at FULL weight -- one origin
    #:     contributed 2.94, was evicted, and its bare repetition contributed
    #:     2.94 again, against a ceiling of 3.27;
    #:   * charging a re-admission `rho` bounded one return and not the series --
    #:     cycling `origin_limit` uninformative sources through the belief bought
    #:     a fresh geometric ladder each time, 0.950 -> 0.99985 over twenty
    #:     cycles;
    #:   * charging all re-admissions ONE shared `rho/(1-rho)` allowance still
    #:     leaked twice over: it did not count the repeats already paid for while
    #:     the origin was still recognised (0.294 granted a second time on top of
    #:     a saturated 3.2716), and a re-admitted origin was back IN the index, so
    #:     its next hearing took the `rho ** heard` branch and skipped the
    #:     allowance entirely -- 6.18 log-odds after a hundred cycles.
    #:
    #: Not evicting makes the bound a consequence of the arithmetic rather than a
    #: rule laid on top of it: the n-th hearing of an origin is worth `rho^(n-1)`
    #: for every n, so its total is a geometric series under `1/(1-rho)` for ANY
    #: ordering of events, across save and load, forever. The cost is stated
    #: rather than hidden: at capacity a genuinely new source is refused, which
    #: over-doubts. Doubt is the safe direction; the alternative was proof.
    origins_refused: int = 0
    #: How many retellings away from the original source this belief is. 0 means
    #: witnessed or heard first-hand. The inspector uses it to show social distance.
    hops: int = 0
    #: Whether the holder is still actively passing this on. Daley & Kendall's
    #: stifling mechanism: a spreader who tries to tell someone who already knows
    #: loses interest in the item. This is what makes a rumour die out on its own
    #: and saturate below the whole population, rather than needing an arbitrary
    #: hop limit to stop it.
    spreading: bool = True

    @property
    def primary_origin(self):
        """The origin this holder would cite -- the first one they heard.

        A retelling carries THIS, not the teller's id, which is what keeps a
        rumour relayed through five mouths worth one witness rather than five.
        """
        return next(iter(self.origin_counts), None)

    @property
    def origins(self) -> dict:
        return self.origin_counts

    def record_provenance(self, claim_id, origin_event, kappa: float, eta: float,
                          *, delta: float = 0.0, speaker=None, limit: int = 64,
                          origin_limit: int = 512) -> None:
        """Record one piece of evidence: for the inspector, and for the arithmetic.

        Two records, because they answer different questions and have different
        lifetimes. The provenance list is what a person reads and is trimmed to
        `limit`. `contributions` is what `revision` recomputes from and is kept
        per (speaker, origin) in full, up to `origin_limit` distinct sources --
        past which a belief says how many it has forgotten rather than pretending
        it can still unwind them.
        """
        if origin_event is not None:
            # Origins are opaque tokens and are often raw event ids. JSON has only
            # string keys, so normalise here: otherwise a saved belief comes back
            # with string keys, stops matching integer origins, and silently starts
            # treating a repeated rumour as independent evidence again.
            key = _origin_key(origin_event)
            if key in self.origin_counts:
                # A KNOWN ORIGIN ALWAYS COUNTS UP, whatever the index holds. This
                # is the half that makes `rho ** heard` a real exponent rather
                # than a guess, and it costs nothing: the entry already exists.
                self.origin_counts[key] += 1
            elif not origin_limit or len(self.origin_counts) < origin_limit:
                self.origin_counts[key] = 1
            else:
                # FULL. The index does not evict, so this source is turned away
                # rather than let in at the price of forgetting another. It also
                # contributed no evidence -- `correlation_discount` returned 0 for
                # exactly this case, which is why the bound holds by arithmetic.
                self.origins_refused += 1
        if delta:
            attribution = _contribution_key(speaker, origin_event)
            if (attribution not in self.contributions and origin_limit
                    and len(self.contributions) >= origin_limit):
                attribution = FORGOTTEN
            bucket = self.contributions.setdefault(attribution, [0.0, 0.0])
            bucket[0 if delta > 0 else 1] += delta
        self.provenance.append({"claim_id": claim_id, "origin_event": origin_event,
                                "kappa": round(kappa, 3), "eta": round(eta, 3),
                                # The signed log-odds this piece of evidence
                                # actually contributed, and who said it. Both exist
                                # so the belief can be RECOMPUTED later: when a
                                # source turns out to have been lying, lowering
                                # trust going forward is not enough -- what they
                                # already convinced people of has to be revisited.
                                "delta": round(delta, 6),
                                "speaker": speaker})
        if limit and len(self.provenance) > limit:
            overflow = len(self.provenance) - limit
            del self.provenance[:overflow]
            self.provenance_dropped += overflow

    @property
    def expected_prob(self) -> float:
        return sigmoid(self.logit_val)

    @property
    def ignorance(self) -> float:
        # high when little evidence either way
        return 1.0 / (1.0 + self.support_for + self.support_against)

    @property
    def conflict(self) -> float:
        sf, sa = self.support_for, self.support_against
        if sf + sa <= 1e-9:
            return 0.0
        return (2.0 * min(sf, sa)) / (sf + sa)

    def as_dict(self):
        # full precision for persistence; inspect views round for display
        return {"proposition": self.proposition.as_dict(), "logit": self.logit_val,
                "expected_prob": self.expected_prob,
                "support_for": self.support_for,
                "support_against": self.support_against,
                "ignorance": self.ignorance, "conflict": self.conflict,
                # copies, not the live lists: a snapshot that aliases mutable
                # runtime state is not a snapshot -- later mutations rewrote the
                # "before" picture and made a lossy round-trip look lossless.
                "provenance": [dict(entry) for entry in self.provenance],
                "origin_counts": dict(self.origin_counts),
                "contributions": {k: list(v) for k, v in self.contributions.items()},
                "origins_refused": self.origins_refused,
                "provenance_dropped": self.provenance_dropped, "hops": self.hops,
                "spreading": self.spreading,
                "valid_start": self.valid_start, "txn_time": self.txn_time}

    @staticmethod
    def from_dict(d: dict) -> "Belief":
        # expected_prob/ignorance/conflict are derived; only the primitives round-trip.
        provenance = [dict(p) for p in d.get("provenance", [])]
        origin_counts = d.get("origin_counts")
        if origin_counts is None:
            # Older records carry no origin index; rebuild what is recoverable so a
            # restored belief still discounts repeats from origins it has seen.
            origin_counts = {}
            for entry in provenance:
                origin = entry.get("origin_event")
                if origin is not None:
                    key = _origin_key(origin)
                    origin_counts[key] = origin_counts.get(key, 0) + 1
        contributions = d.get("contributions")
        if contributions is None:
            # An older record carries no arithmetic ledger. Rebuild what the
            # surviving provenance can still account for; anything already
            # trimmed is unattributable and says so.
            contributions = {}
            for entry in provenance:
                delta = float(entry.get("delta") or 0.0)
                if not delta:
                    continue
                key = _contribution_key(entry.get("speaker"), entry.get("origin_event"))
                bucket = contributions.setdefault(key, [0.0, 0.0])
                bucket[0 if delta > 0 else 1] += delta
        return Belief(proposition=Proposition.from_dict(d["proposition"]),
                      logit_val=d["logit"], support_for=d["support_for"],
                      support_against=d["support_against"],
                      provenance=provenance,
                      origin_counts=dict(origin_counts),
                      contributions={k: list(v) for k, v in contributions.items()},
                      origins_refused=d.get("origins_refused", 0),
                      provenance_dropped=d.get("provenance_dropped", 0),
                      hops=d.get("hops", 0), spreading=d.get("spreading", True),
                      valid_start=d.get("valid_start"), txn_time=d.get("txn_time"))


class BeliefEngine:
    module_id = "belief"
    version = "0.5.0"

    def __init__(self, params=None):
        self.params = {"kappa0": 0.55, "alpha": 0.25, "gamma": 0.20, "delta": 0.30,
                       "kappa_min": 0.20, "kappa_max": 0.95,
                       # Geometric attenuation per repeat from a known origin. The
                       # total any one origin can contribute is 1/(1-rho) hearings,
                       # so repetition saturates instead of accumulating.
                       "rho_correlated": 0.10,
                       # How many individual claim records to keep per belief for
                       # the inspector. The arithmetic is kept separately, in
                       # `Belief.contributions`, and is not trimmed with these.
                       "provenance_limit": 64,
                       # How many distinct sources one belief tracks before it
                       # starts forgetting. Bounded because everything
                       # per-character in this runtime has to be: a claim heard
                       # from unboundedly many origins would otherwise grow a
                       # save file forever. Generous enough that no shipped pack
                       # comes close.
                       "origin_limit": 512}
        if params:
            self.params.update(params)

    def credibility(self, trust: float, competence: float, skepticism: float) -> float:
        p = self.params
        k = p["kappa0"] + p["alpha"] * trust + p["gamma"] * competence - p["delta"] * skepticism
        return clamp(k, p["kappa_min"], p["kappa_max"])

    def correlation_discount(self, belief: Belief, origin_event) -> float:  # noqa: D401
        """eta in [0,1]: how much NEW evidence this assertion carries.

        The nth assertion from an origin already heard n-1 times contributes
        ``rho**(n-1)``. Because rho < 1 that geometric series converges: an origin
        can never contribute more than ``1/(1-rho)`` times a single hearing, no
        matter how often it is repeated.

        The previous version returned a flat 0.1 for any repeat, which attenuated
        but did not saturate -- so a single rumour repeated often still accumulated
        without limit and reached certainty:

            200 repetitions of one origin -> p = 0.995

        That is the exact failure the feature exists to prevent, and it is the
        difference between "a repeated rumour is weak evidence" and "a repeated
        rumour is proof if you are patient".
        """
        if origin_event is None:
            return 1.0
        heard = belief.origins.get(_origin_key(origin_event), 0)
        limit = self.params["origin_limit"]
        if heard == 0 and limit and len(belief.origins) >= limit:
            # AT CAPACITY AND UNRECOGNISED: no evidence, because the belief cannot
            # tell this source from one it has already counted. Refusing is the
            # only answer that keeps the bound below true for every ordering --
            # the two designs that admitted it at a discount both leaked, because
            # a discount applied at admission bounds one step of a sequence the
            # attacker controls the length of. `origins_refused` says how often.
            return 0.0
        return self.params["rho_correlated"] ** heard

    def max_origin_contribution(self) -> float:
        """Ceiling on the evidence one origin can ever contribute, in units of a
        single hearing. Useful for calibration and for explaining the model.

        This is a THEOREM, not a policy, and it holds for every ordering of
        events including save and load. The origin index does not evict, so the
        n-th hearing from an origin is worth `rho^(n-1)` for every n and its
        total is `sum(rho^k for k in range(n)) < 1/(1-rho)`. Nothing else in the
        engine can add to that sum: a source the index has no room for is worth
        exactly zero and is counted in `origins_refused`.
        """
        return 1.0 / (1.0 - self.params["rho_correlated"])

    def update(self, beliefs: dict, claim_prop: Proposition, *, asserter_polarity: str,
               trust: float, competence: float, skepticism: float,
               claim_id, origin_event, world_time, speaker=None):
        """Update the belief about claim_prop. Returns (belief, reason_entries)."""
        reasons = []
        key = claim_prop.core_key()
        belief = beliefs.get(key)
        if belief is None:
            base = Proposition(claim_prop.predicate, dict(claim_prop.slots), "+",
                               claim_prop.valid_start, claim_prop.valid_end, claim_prop.spatial)
            belief = Belief(proposition=base, logit_val=0.0, valid_start=world_time)
            beliefs[key] = belief

        kappa = self.credibility(trust, competence, skepticism)
        eta = self.correlation_discount(belief, origin_event)
        sign = +1.0 if asserter_polarity == "+" else -1.0
        evidence = eta * math.log(kappa / (1.0 - kappa))
        # WHICH POOL A PIECE OF EVIDENCE LANDS IN IS DECIDED BY WHAT IT DID TO
        # THE LOG-ODDS, not by which way it was asserted. Below kappa = 0.5 the
        # log-odds term is negative -- the source is credible enough to be worth
        # believing the OPPOSITE of -- so a positive assertion from them lowers
        # the probability. Filing that under `support_for` because the assertion
        # was positive made the two halves of the record contradict each other:
        # trust=0, competence=0, skepticism=1 drove p to 0.25 while reporting
        # 1.0986 of support FOR.
        contribution = sign * evidence
        belief.logit_val += contribution
        if contribution >= 0:
            belief.support_for += contribution
        else:
            belief.support_against += -contribution
        belief.record_provenance(claim_id, origin_event, kappa, eta,
                                 delta=contribution, speaker=speaker,
                                 limit=self.params["provenance_limit"],
                                 origin_limit=self.params["origin_limit"])
        belief.txn_time = world_time

        reasons.append(("belief.updated", round(sign * evidence, 4),
                        {"proposition": str(claim_prop), "kappa": round(kappa, 3),
                         "eta": round(eta, 3), "new_prob": round(belief.expected_prob, 3)}))

        # contradiction check against existing beliefs (surfaced, not collapsed -- paraconsistent)
        for other in beliefs.values():
            if other is belief:
                continue
            kind = contradicts(belief.proposition, other.proposition)
            if kind:
                reasons.append(("belief.contradiction", 0.0,
                                {"kind": kind, "a": str(belief.proposition), "b": str(other.proposition)}))
        return belief, reasons
