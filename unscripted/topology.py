"""Why not everyone knows everything.

Diffusion answers *how* information moves. This answers *where it stops*, which
in a city-sized cast matters more. Left to co-location and trust alone, a claim
eventually reaches anyone who ever shares a room with anyone -- slowly, but a
long-running world has plenty of time.

Three brakes, and the first is the one that shapes the world:

**Knowledge is not a hierarchy.** A street vendor knows more about the local gang
than a corporate director does. Rank is not a knowledge ordering, so a single
pyramid would be wrong. Instead a claim is classified on several independent
axes -- domain, locality, who may access it, how readily it travels -- and a
listener is reachable on some axes and not others.

**People talk inside their networks.** Family, shift, union, congregation, crew.
Most exchanges happen inside one, and information crosses between them only
through the few people who belong to both. Those bridges are what make a rumour's
route interesting rather than uniform.

**Attention is finite.** Nobody takes in everything they are told. A bounded
number of new claims per day get properly encoded; past that, a character hears
and forgets, which is what stops a long-lived world from becoming a single shared
memory.

All three are world content. A pack declares its own classes and networks,
because what counts as restricted, and who counts as a group, is a property of a
setting.
"""

from __future__ import annotations

#: How freely a claim travels once someone holds it, by declared classification.
#: A multiplier on the chance of passing it on, not a hard gate: people do leak
#: restricted things, and a model where they never do is not a model of people.
TRANSMISSIBILITY = {
    "public": 1.0,
    "common": 0.85,
    "local": 0.6,
    "trade": 0.45,        # shop talk: passed on readily, but only to those who care
    "restricted": 0.2,
    "secret": 0.05,
}

DEFAULT_CLASS = "common"


class KnowledgeClass:
    """What a world declares about one kind of claim."""

    __slots__ = ("predicate", "classification", "domain", "access", "locality",
                 "transmissibility")

    def __init__(self, predicate: str, spec: dict | None = None):
        spec = spec or {}
        self.predicate = predicate
        self.classification = spec.get("classification", DEFAULT_CLASS)
        self.domain = spec.get("domain", "street")
        #: Groups, roles or factions whose members will pass this on. Empty means
        #: anyone. This restricts *circulation*, never perception: seeing a thing
        #: you have no clearance for is exactly how interesting trouble starts.
        self.access = tuple(spec.get("access") or ())
        #: Places where it circulates at all. Empty means everywhere.
        self.locality = tuple(spec.get("locality") or ())
        self.transmissibility = float(spec.get(
            "transmissibility", TRANSMISSIBILITY.get(self.classification, 0.85)))

    def as_dict(self) -> dict:
        return {"predicate": self.predicate, "classification": self.classification,
                "domain": self.domain, "access": list(self.access),
                "locality": list(self.locality),
                "transmissibility": round(self.transmissibility, 3)}


def class_for(world, proposition) -> KnowledgeClass:
    """The declared class of a claim, or a neutral default."""
    declared = (getattr(world, "predicates", None) or {})
    spec = declared.get(proposition.predicate) if isinstance(declared, dict) else None
    return KnowledgeClass(proposition.predicate, spec)


def circles(agent) -> set:
    """Every group this character belongs to: networks, roles, factions.

    One flat set on purpose. A claim that circulates among engineers and a claim
    that circulates in the night shift are the same kind of restriction, and
    keeping them in separate namespaces would only mean writing the same rule
    twice.
    """
    found = set()
    for network in getattr(agent, "networks", None) or ():
        found.add(str(network))
    for role in getattr(agent, "roles", None) or ():
        if isinstance(role, dict):
            if role.get("role"):
                found.add(str(role["role"]))
            if role.get("context"):
                found.add(str(role["context"]))
        else:
            found.add(str(role))
    for identity in getattr(agent, "identities", None) or ():
        if isinstance(identity, dict) and identity.get("group"):
            found.add(str(identity["group"]))
    return found


def shared_circles(speaker, listener) -> set:
    return circles(speaker) & circles(listener)


def bridges(world) -> dict:
    """Characters who belong to more than one circle, and to which.

    These are the people through whom anything crosses between groups. Worth
    naming because a world where nothing crosses is as wrong as one where
    everything does, and because "who could this have reached" is a question a
    designer asks constantly.
    """
    out = {}
    for agent in (getattr(world, "agents", None) or {}).values():
        mine = circles(agent)
        if len(mine) > 1:
            out[agent.id] = sorted(mine)
    return out


def may_pass_on(world, proposition, speaker, listener, place_id: str | None = None):
    """Would this speaker pass this claim to this listener? `(weight, reason)`.

    Returns a multiplier in [0, 1] rather than a yes/no, because every one of
    these is a tendency. Zero is reserved for the two cases that really are
    categorical: a claim that does not circulate in this place at all, and a
    listener outside a closed circle.
    """
    knowledge = class_for(world, proposition)

    if knowledge.locality and place_id and place_id not in knowledge.locality:
        return 0.0, ("topology.wrong_place",
                     {"predicate": knowledge.predicate, "here": place_id,
                      "circulates_in": list(knowledge.locality)})

    if knowledge.access:
        allowed = set(knowledge.access)
        if not (allowed & circles(listener)):
            return 0.0, ("topology.outside_the_circle",
                         {"predicate": knowledge.predicate,
                          "restricted_to": sorted(allowed),
                          "listener_belongs_to": sorted(circles(listener))})

    weight = knowledge.transmissibility
    detail = {"predicate": knowledge.predicate,
              "classification": knowledge.classification,
              "transmissibility": round(knowledge.transmissibility, 3)}

    # Inside a shared circle, things move more readily than between strangers who
    # merely happen to be in the same room.
    common = shared_circles(speaker, listener)
    if common:
        weight = min(1.0, weight * 1.35)
        detail["shared_circles"] = sorted(common)

    # Shop talk reaches people who work the same trade, and bores everyone else.
    if knowledge.domain and knowledge.domain != "street":
        interest = listener.competence_in(knowledge.domain)
        weight *= 0.4 + 0.6 * min(1.0, interest * 2.0)
        detail["listener_competence"] = round(interest, 3)

    return max(0.0, min(1.0, weight)), ("topology.transmissibility", detail)


# --------------------------------------------------------------- attention ----

def attention_budget(agent) -> int:
    """How many new claims this character can properly take in per day."""
    base = 6.0
    return max(1, int(round(base * (0.5 + agent.trait("curiosity")))))


def spend_attention(agent, world) -> bool:
    """Consume one unit. False means they are full for today.

    Day-bounded rather than continuous, because attention recovers by sleeping
    and because a per-day figure is something an author can reason about.
    """
    today = int(getattr(world, "world_time", 0)) // 1440
    if getattr(agent, "attention_day", None) != today:
        agent.attention_day = today
        agent.attention_spent = 0
    if agent.attention_spent >= attention_budget(agent):
        return False
    agent.attention_spent += 1
    return True
