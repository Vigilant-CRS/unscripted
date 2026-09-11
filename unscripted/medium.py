"""How something was said, and what that costs it.

Until now a person-to-person claim was one undifferentiated act: A told B. But
the same two people telling each other the same thing face to face, over a phone
and in a note are three different events, and the difference is not decoration.

    face to face   everything survives, and the room hears it
    a phone call   detail goes, nobody overhears, and it is harder to weigh
    a note         the words survive, the tone does not, and it can be shown to
                   somebody else later

Daft & Lengel's media richness theory (*Organizational Information Requirements,
Media Richness and Structural Design*, 1986) is the usual framing: media differ
in how much they carry per exchange -- feedback, cues, personalisation -- and
leaner media lose more of what was meant. This module is that idea reduced to
three numbers a runtime can act on, and it lands them on machinery that already
exists rather than inventing a parallel one:

    fidelity      -> the probability the retelling LEVELS, which is the process
                     Allport & Postman measured and `unscripted/distortion.py` already
                     implements. A phone call drops a `when` more often than a
                     conversation does.
    audience      -> whether `_audience()` returns bystanders. Nobody overhears a
                     call, and that is why a call is where a secret goes.
    trust_factor  -> the assertion strength the listener weighs, because a voice
                     with no face behind it is harder to judge and everybody
                     knows it.

WHO CAN REACH WHOM is the other half. A room is who is standing in it; a phone is
who has your number. A character may declare `contacts`, and where a pack has not
said, familiarity above a threshold stands in -- people who know each other well
have each other's number, which is true often enough to be a good default and is
stated here so nobody mistakes it for a finding.

**Off by default.** With `media=False` every exchange is face to face, exactly as
before, and `for_exchange()` returns `IN_PERSON` whatever it is asked. The layer
adds reach; it does not change what a conversation in a room already was.
"""
from __future__ import annotations

from dataclasses import dataclass

#: How well two people have to know each other before a pack that has not said
#: otherwise assumes they can call one another.
CONTACT_FAMILIARITY = 0.45


@dataclass(frozen=True)
class Medium:
    """One way of saying something, and what it costs."""
    name: str
    #: 1.0 loses nothing beyond what any retelling loses; lower levels more.
    fidelity: float
    #: Whether anybody else in the room takes it in.
    audience: bool
    #: Whether the two have to be in the same place.
    needs_colocation: bool
    #: What the listener's weighing of the claim is multiplied by.
    trust_factor: float

    def distortion_scale(self) -> float:
        """How much likelier a retelling is to lose a detail on this medium."""
        return 2.0 - max(0.0, min(1.0, self.fidelity))


IN_PERSON = Medium("in_person", fidelity=1.0, audience=True,
                   needs_colocation=True, trust_factor=1.0)
PHONE = Medium("phone", fidelity=0.72, audience=False,
               needs_colocation=False, trust_factor=0.88)
NOTE = Medium("note", fidelity=0.88, audience=False,
              needs_colocation=False, trust_factor=0.78)

BY_NAME = {medium.name: medium for medium in (IN_PERSON, PHONE, NOTE)}


def contacts_of(agent) -> frozenset:
    """Whose number this character has.

    Authored with `"contacts": ["agent:..."]`, or inferred from how well they
    know somebody. The inference is a default, not a claim: a pack that cares
    about who can reach whom should say so, and a pack that does not still gets
    a plausible small-world graph rather than a fully connected one.
    """
    authored = getattr(agent, "contacts", None)
    if authored:
        return frozenset(authored)
    known = set()
    for other_id, relationship in (getattr(agent, "relationships", None) or {}).items():
        if not isinstance(relationship, dict):
            continue
        if float(relationship.get("familiarity", 0.0)) >= CONTACT_FAMILIARITY:
            known.add(other_id)
    return frozenset(known)


def for_exchange(speaker, listener, *, enabled: bool = True) -> Medium | None:
    """The medium these two would use, or None if they cannot reach each other.

    Same room: they speak. Different rooms and each other's number: they call.
    Otherwise the exchange does not happen, which is the point -- a world where
    everybody can always reach everybody has no geography left.
    """
    if not enabled:
        return IN_PERSON if speaker.location == listener.location else None
    if speaker.location == listener.location:
        return IN_PERSON
    if listener.id in contacts_of(speaker):
        return PHONE
    return None


def describe(medium: Medium) -> str:
    """One line for a trace or a debug HUD."""
    if medium.audience:
        heard = "the room hears it"
    else:
        heard = "nobody else hears it"
    return (f"{medium.name.replace('_', ' ')}: {heard}, "
            f"detail survives {medium.fidelity:.0%} as well, "
            f"weighed at {medium.trust_factor:.0%}")
