"""Agent state container (spec v0.5 §5; Ontology v0.4 §6)."""
from __future__ import annotations
from dataclasses import dataclass, field
from .affect import AffectState, pad_baseline_from_big_five
from .belief import Belief
from .types import Vec3

#: Bumped by every write to any agent's `location`. A world's occupancy index is
#: cached against this, so the index can never go stale no matter who moves
#: somebody -- routines, the player, a snapshot restore, or a test.
LOCATION_EPOCH = 0


@dataclass
class Agent:
    id: str
    big_five: dict = field(default_factory=dict)
    schwartz: dict = field(default_factory=dict)
    needs: dict = field(default_factory=dict)
    identities: list = field(default_factory=list)
    roles: list = field(default_factory=list)
    appearance: dict = field(default_factory=dict)
    education: dict = field(default_factory=dict)          # domain -> competence
    relationships: dict = field(default_factory=dict)      # other_id -> {trust, liking, familiarity}
    secrets: list = field(default_factory=list)            # list[unscripted.content.Secret]
    goals: list = field(default_factory=list)
    location: str = None
    public_name: str = None
    objective_name: str = None
    aliases: tuple = ()                                    # authored names the parser accepts
    routine: object = None                                 # unscripted.routine.Routine, or None to stay put
    social_status: float = 0.4                             # prestige baseline [0,1]
    resources: float = 0.4                                 # liquid wealth/budget [0,1] -> affordability + risk reference
    dialect: str = None
    reputation: dict = field(default_factory=dict)         # subject_id -> {dimension: degree} (this agent's view)
    tom_models: dict = field(default_factory=dict)         # (other, prop_key) -> {confidence,...}
    identity_salience: dict = field(default_factory=dict)  # identity_id -> salience, owned by IdentityEngine
    #: identity_id -> how threatened that belonging currently feels, in [0, 1].
    #: Raised when somebody who shares it is attacked, and decayed with mood --
    #: this is alarm, not a fact about the world. It feeds IdentityEngine's
    #: `w_threat` term, which until now was always multiplied by zero because
    #: nothing ever produced one.
    identity_threat: dict = field(default_factory=dict)
    #: What this character will not trade away. `truthfulness` decides whether a
    #: cornered character lies or refuses; the others are read by the policy
    #: layer. Authored per character, because "would this person lie to you" is a
    #: characterisation decision and not something an engine should guess.
    values: dict = field(default_factory=dict)
    #: How this character handles evidence, as opposed to what they value.
    #: `curiosity` raises what they notice; `confirmation_bias` decides how a
    #: scene they cannot read gets bent -- towards what they already expect, or
    #: simply blurred. Authored, with neutral defaults.
    epistemic: dict = field(default_factory=dict)
    #: Groups this character belongs to beyond their role: family, shift, union,
    #: congregation. Information moves inside these and crosses between them only
    #: through the few people who belong to both.
    networks: tuple = ()
    #: How this character sounds, if the pack says: base pitch and rate, and
    #: `say_as` for a name a synthesiser would otherwise mispronounce. Empty for
    #: everyone else, who get a voice derived from their id.
    voice: dict = field(default_factory=dict)
    #: Whose number this character has. Empty means "work it out from how well
    #: they know people" -- see unscripted/medium.py.
    contacts: tuple = ()
    #: Bounded intake, reset each world day. Nobody takes in everything they hear.
    attention_day: int = -1
    attention_spent: int = 0
    #: incident (proposition core key) -> how far this character's standing
    #: towards whoever did it has already been moved by it. A believed act is a
    #: position, not a running total, so hearing about it again applies only the
    #: difference. Owned by `unscripted.standing`; persisted, because it is state a
    #: player produced.
    standing_applied: dict = field(default_factory=dict)

    # owned runtime state
    beliefs: dict = field(default_factory=dict)            # core_key -> Belief
    memory: list = field(default_factory=list)
    affect: AffectState = None

    def __setattr__(self, name, value):
        # Cheap and total. The alternative -- remembering to invalidate at each of
        # the half-dozen places that move somebody -- is the kind of bookkeeping
        # that works until the seventh one is added.
        if name == "location":
            global LOCATION_EPOCH
            LOCATION_EPOCH += 1
        object.__setattr__(self, name, value)

    def __post_init__(self):
        if self.affect is None:
            base = pad_baseline_from_big_five(self.big_five) if self.big_five else Vec3()
            self.affect = AffectState(mood=Vec3(base.p, base.a, base.d), baseline=base)

    # ---- helpers used by the belief engine context ----
    def trust_in(self, other_id: str) -> float:
        return self.relationships.get(other_id, {}).get("trust", 0.3)

    def competence_in(self, domain: str) -> float:
        return self.education.get(domain, 0.3)

    def trait(self, name: str, default: float = 0.5) -> float:
        """An authored epistemic trait, or a neutral default."""
        try:
            return float(self.epistemic[name])
        except (KeyError, TypeError, ValueError):
            return default

    def value(self, name: str, default: float = 0.5) -> float:
        """An authored value, falling back to a Schwartz proxy then a default."""
        if name in self.values:
            return float(self.values[name])
        proxy = {"truthfulness": "benevolence", "loyalty": "tradition",
                 "self_preservation": "security"}.get(name)
        if proxy and proxy in self.schwartz:
            return float(self.schwartz[proxy])
        return default

    def will_lie_about(self, secret) -> bool:
        """Lie, or refuse? A character lies when the stake outweighs their honesty.

        No cover story means no lie. That is deliberate: the engine will not
        invent what someone claims instead, any more than it invents a fact, so a
        world that has not authored the lie gets a refusal -- which is honest in
        its own way, because silence is itself information.
        """
        if not getattr(secret, "cover_story", None):
            return False
        stake = getattr(secret, "min_trust", 0.45)
        return self.value("truthfulness") < stake

    @property
    def skepticism(self) -> float:
        # low agreeableness / low emotional stability -> more skeptical (a simple derived proxy)
        a = self.big_five.get("agreeableness", 0.5)
        s = self.big_five.get("emotional_stability", 0.5)
        return max(0.0, min(1.0, 0.6 - 0.3 * a - 0.2 * (s - 0.5)))
