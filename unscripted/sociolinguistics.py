"""SociolinguisticEngine -- register / style as a function of social position,
education, group identity, audience, setting and affect (the slang/register/social-
ranking layer requested in review discussion).

IMPORTANT framing: this is NOT a "good vs bad speech" ladder. It models register
and PRESTIGE variation -- formality, sentence length, lexical breadth, slang/argot,
politeness -- plus accommodation toward the interlocutor (Giles' CAT) and audience
design (Bell). A low-status speaker is not "worse"; they use a different, fully
competent variety. Education must not be equated with intelligence (Ontology v0.1 §4.5).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .types import clamp01, clamp_signed


@dataclass
class StyleVector:
    formality: float = 0.5          # [0,1]
    lexical_sophistication: float = 0.5
    mean_sentence_length: float = 12.0   # target tokens
    slang_level: float = 0.0        # [0,1]
    directness: float = 0.5
    hedging: float = 0.3
    dialect: str = None
    jargon_domain: str = None
    slang_lexicon: str = None       # vocab scheme id for in-group slang
    politeness_strategy: str = "neutral"   # bald / positive / negative / off-record

    def as_dict(self):
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


#: Fallback when a pack authors no ``formality`` on a place. Setting formality is
#: world content -- a police post is formal and a back room is not *in this world* --
#: so it is read from ``world.json`` per place and no longer tabulated here.
DEFAULT_SETTING_FORMALITY = 0.4


class SociolinguisticEngine:
    module_id = "sociolinguistics"
    version = "0.6.0"

    def __init__(self, params=None):
        self.params = {"w_edu": 0.4, "w_setting": 0.3, "w_status": 0.2, "w_role": 0.2,
                       "w_arousal": 0.4, "w_ingroup": 0.5, "lambda_accommodation": 0.4,
                       "base_sentence_len": 8.0, "k_len": 12.0, "k_stress": 6.0}
        if params:
            self.params.update(params)

    def _has_argot(self, agent):
        """Member of a group with an in-group vernacular (gang, subculture)."""
        return 1.0 if any(i.get("id") in ("gang_member",) for i in agent.identities) else 0.0

    def social_status(self, agent, observer=None, world=None, appearance=None):
        """Continuous prestige in [0,1]. With an observer, the PERCEIVED status.

        This docstring has said "reputation- and appearance-mediated" since it
        was written, and the code consulted reputation only -- while every
        character in every shipped pack authored a garment that nothing read. It
        reads it now, when the pack says what a garment means; with no
        `appearance_reactions` the term is exactly zero and this returns what it
        always did.
        """
        base = agent.__dict__.get("social_status", 0.4)
        if observer is None:
            return clamp01(base)
        rep = observer.reputation.get(agent.id, {}) if hasattr(observer, "reputation") else {}
        perceived = 0.6 * base + 0.4 * clamp01(0.5 + 0.5 * rep.get("status", 0.0))
        if appearance is not None and world is not None:
            perceived += 0.25 * appearance.read(observer, agent, world)["status"]
        return clamp01(perceived)

    def compute_style(self, agent, *, interlocutor=None, place=None, salient_identity=None,
                      affect_engine=None, world=None, regard=None,
                      appearance=None) -> StyleVector:
        """`regard` carries the two feelings the register never had: fear, respect.

        Optional, and None unless the standing layer is on, so a world that
        declines that mechanic produces byte-identical style.

        NOT the (agency, communion) pair from `InterpersonalEngine`, and the
        first attempt was. Communion is mostly liking again, and the
        accommodation step below has consulted liking since it was written, so
        that version added a second copy of something already modelled and its
        effect vanished under the existing one -- measured at 0.007 on
        directness, which is decoration. What fear and respect actually add is
        the part liking cannot express: you can be wary of somebody you like,
        and defer to somebody you do not.
        """
        p = self.params
        # general education / vocabulary breadth -- NOT street competence (Ontology v0.1 §4.5:
        # education != intelligence; a street-smart person may have low *general* register education)
        edu = agent.education.get("general", 0.35)
        status = self.social_status(agent)
        setting = (world.place_formality(place, DEFAULT_SETTING_FORMALITY)
                   if world is not None else DEFAULT_SETTING_FORMALITY)
        role_formal = 0.7 if any(r.get("role") in ("role:bartender", "role:officer", "role:doctor")
                                 for r in agent.roles) else 0.4
        arousal = agent.affect.mood.a if agent.affect else 0.0
        neg = max(0.0, -(agent.affect.mood.p if agent.affect else 0.0))
        stress = clamp01(arousal * neg)
        membership = self._has_argot(agent)
        # vernacular pull from in-group membership, suppressed in formal settings (code-switching)
        ingroup_pull = membership * (1.0 - setting)

        formality = clamp01(
            p["w_edu"] * edu + p["w_setting"] * setting + p["w_status"] * status + p["w_role"] * role_formal
            - p["w_arousal"] * stress - p["w_ingroup"] * ingroup_pull)

        lexical = clamp01(0.4 * edu + 0.6 * (edu * formality))
        sent_len = p["base_sentence_len"] + p["k_len"] * lexical * formality - p["k_stress"] * stress
        slang = clamp01(membership * (1.0 - formality))
        anger = (affect_engine.emotions_toward(agent.affect, interlocutor).get("anger", 0.0)
                 if (affect_engine and interlocutor) else 0.0)
        directness = clamp01(0.5 + 0.3 * (1 - agent.big_five.get("agreeableness", 0.5))
                             - 0.3 * formality + 0.4 * anger)
        hedging = clamp01((1 - directness) * (0.4 + 0.4 * formality))

        style = StyleVector(formality=formality, lexical_sophistication=lexical,
                            mean_sentence_length=max(4.0, sent_len), slang_level=slang,
                            directness=directness, hedging=hedging,
                            dialect=agent.__dict__.get("dialect"),
                            jargon_domain=(max(agent.education, key=agent.education.get)
                                           if agent.education else None),
                            slang_lexicon="vocab:reds_slang" if slang > 0.2 else None,
                            politeness_strategy=self._politeness(formality, directness))

        # Communication Accommodation Theory: converge toward a liked interlocutor's register,
        # diverge from a disliked one (spec / Giles).
        if interlocutor is not None:
            rel = agent.relationships.get(interlocutor, {})
            liking = rel.get("liking", 0.0)
            other_status = 0.5
            lookup = (world.agents.get if world is not None
                      else agent.__dict__.get("_world_lookup"))
            if lookup:
                other = lookup(interlocutor)
                if other is not None:
                    other_status = self.social_status(other, observer=agent,
                                                      world=world,
                                                      appearance=appearance)
            target_formality = 0.5 + 0.5 * other_status  # high-status interlocutor pulls formality up
            # CONVERGENCE AND DIVERGENCE ARE A DIAL, NOT A SWITCH.
            #
            # This used to be `(1 if liking >= 0 else -1)`, and that sign flip
            # was a cliff at exactly zero: a stranger, whose liking is 0.000,
            # got the full pull toward the other person's register, and one
            # small unkindness later -- liking -0.15 -- got the full push away
            # from it, taking formality from 0.568 to 0.097. A whole register
            # collapsing on a fifteen-hundredth of a unit is not accommodation,
            # and it saturated the vector so completely that nothing else added
            # to it could be seen.
            #
            # Giles' theory is about degree. So: no feeling, no accommodation;
            # a little liking, a little convergence; real dislike, real
            # divergence. `min(1, |liking| * 2)` reaches full strength at 0.5,
            # which is where a relationship in this runtime is unmistakable.
            direction = (1.0 if liking >= 0 else -1.0) * min(1.0, abs(liking) * 2.0)
            style.formality = clamp01(style.formality + p["lambda_accommodation"]
                                      * (target_formality - style.formality) * direction)

        # HOW SOMEBODY SPEAKS TO A PERSON THEY ARE WARY OF.
        #
        # Wariness makes people careful: they hedge, they stop being blunt, and
        # they reach for a more formal register than they otherwise would.
        # Respect makes them deferential without making them warm. Neither is
        # expressible through liking, which is why this exists at all -- and
        # neither had ever moved before conduct started producing them.
        if regard:
            fear = clamp01(regard.get("fear", 0.0))
            respect = clamp01(regard.get("respect", 0.0))
            style.formality = clamp01(style.formality + 0.25 * fear + 0.15 * respect)
            style.directness = clamp01(style.directness - 0.30 * fear)
            style.hedging = clamp01(style.hedging + 0.30 * fear + 0.10 * respect)
            style.politeness_strategy = self._politeness(style.formality, style.directness)
        return style

    @staticmethod
    def _politeness(formality, directness):
        if formality > 0.7 and directness < 0.5:
            return "negative"      # deferential, indirect
        if formality < 0.3 and directness > 0.6:
            return "bald"          # direct, no redress
        if directness < 0.4:
            return "off_record"
        return "positive"
