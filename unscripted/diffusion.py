"""Knowledge diffusion: how information actually moves through a society.

Until this module existed, a character learned something only by being present
when it happened, or by hearing it on a broadcast channel. Nobody ever told
anybody anything. Seventy-two simulated hours with every NPC in the same room
changed nothing:

    player asks Vee about Milan        -> 4 co-present agents know it
    +72h, whole cast co-located        -> still exactly those 4

That made the runtime's central claim -- that rumour spreads through a world with
a traceable origin -- untrue, and it made correlation discounting guard against a
situation the engine could not produce: ten people repeating one rumour requires
a mechanism by which a second person ever repeats it.

The design deliberately adds no new belief machinery. A retelling is emitted as
an ordinary ``claim`` event by the speaker at their location, so it flows through
the existing perception -> belief -> memory -> affect path. Three things fall out
of that for free:

- **Auditability.** Every retelling is a row in the event ledger, with actor,
  location, time and the origin it carries. "How did this NPC know that?" is a
  query, not a guess.
- **Bystanders.** Whoever else is in the room overhears it, weighted by the
  place's noise, exactly as with any other event.
- **Provenance.** The retelling carries the ORIGINAL origin, not the teller. So
  a rumour that reaches you through five mouths from one witness is still one
  witness, and correlation discounting finally has something to discount.

What is authored, not hardcoded: encounter rates, which places are gossipy, how
much confidence a retelling loses, and how often it distorts. See
``world.json: diffusion`` and per-place ``gossip_factor``.
"""
from __future__ import annotations

import math

from . import topology
from .determinism import derive_seed, seeded_uniform
from . import distortion
from .events import Event

#: Defaults. A pack overrides any of these in ``world.json: {"diffusion": {...}}``.
DEFAULT_PARAMS = {
    # Chance that a given co-located, socially connected pair actually talks about
    # something during one simulated hour.
    "encounters_per_hour": 0.35,
    # Hard ceiling per time step, so a crowded scene cannot make a tick O(n^2).
    "max_encounters_per_tick": 48,
    # A speaker only passes on what they actually believe.
    "min_confidence_to_tell": 0.60,
    # Below this tie strength people do not chat unprompted.
    "min_tie": 0.05,
    # How much conviction survives one retelling. Calibrated against serial
    # reproduction (Bartlett 1932; Allport & Postman 1947): roughly two thirds of
    # detail is gone after five or six retellings, which 0.80 per hop reproduces
    # (0.80**5 = 0.33). See docs/CALIBRATION.md.
    "fidelity_decay": 0.80,
    # Chance a retelling changes the claim rather than passing it on intact.
    # What kind of change is decided by unscripted.distortion, following Allport &
    # Postman: mostly detail dropping out, sometimes quantities growing, sometimes
    # the story drifting toward people the teller knows, rarely an outright
    # reversal. Higher than the old value because most distortion is now gradual
    # loss, which is common, rather than inversion, which is not.
    "distortion_prob": 0.18,
    # Relative frequency of the four processes; see unscripted/distortion.py.
    "distortion_weights": None,
    # Daley & Kendall stifling: chance a spreader loses interest in an item after
    # telling it to somebody who already knew. This is the mechanism that makes a
    # rumour saturate on its own.
    "stifle_prob": 1.0,
    # Whether NPCs gossip to the player unprompted. Off by default: it changes the
    # feel of a scene and should be a deliberate design choice.
    "include_player": False,
    # Safety guard only. Termination is supposed to come from stifling, which is a
    # model of something; a hop limit is a model of nothing. Kept high so it never
    # binds in practice, and so that a pack which disables stifling still cannot
    # circulate one claim forever.
    "max_hops": 12,
    # How many bystanders can overhear one exchange. A conversation is not a public
    # announcement: without a bound, every retelling was perceived by everyone in
    # the place, which made a crowded scene quadratic and let gossip saturate a
    # square instantly. Overhearing is how a player picks up rumours in a bar, so
    # it stays on -- just bounded.
    "bystanders": 3,
}


class DiffusionEngine:
    """Selects who tells whom what, and emits it as an auditable world event."""

    module_id = "diffusion"
    version = "1.0.0"

    def __init__(self, params=None):
        self.params = dict(DEFAULT_PARAMS)
        if params:
            self.params.update(params)

    @classmethod
    def for_world(cls, world) -> "DiffusionEngine":
        return cls(getattr(world, "diffusion_params", None))

    # ------------------------------------------------------------------ step --
    def step(self, world, runtime, delta_minutes: int, *, player_id: str | None = None) -> list:
        """Run one diffusion pass over `delta_minutes` of world time.

        Returns reason entries describing every encounter considered and every
        retelling emitted. Emits real events through ``runtime.process_event``.
        """
        if delta_minutes <= 0:
            return []
        p = self.params
        reasons = []
        hours = delta_minutes / 60.0

        emitted = 0
        for place_id, occupants in self._populated_places(world, player_id).items():
            gossip_factor = float((world.places.get(place_id) or {}).get("gossip_factor", 1.0))
            if gossip_factor <= 0.0:
                continue
            # What it is like here scales how often people talk at all. Neutral
            # when the layer is off, so this multiplication changes nothing.
            climate = getattr(runtime, "climate", None)
            mods = climate.modifiers(place_id) if climate is not None else None
            gossip_factor *= (mods or {}).get("tempo", 1.0)

            # Sample encounters; do NOT enumerate pairs. A crowd of n people has
            # n*(n-1) ordered pairs, and walking them made a tick quadratic in
            # population -- 200 co-located agents is ~40,000 candidate pairs per
            # tick, which is a real cost even when almost all of them are rejected.
            # People do not each hold a conversation with everyone present; the
            # number of conversations grows with the size of the room, not with its
            # square. So: expected encounters is linear in occupancy, and each one
            # picks its participants deterministically.
            expected = p["encounters_per_hour"] * gossip_factor * hours * len(occupants)
            wanted = min(int(expected), p["max_encounters_per_tick"] - emitted)
            fraction = expected - int(expected)
            frac_seed = derive_seed(world.global_seed, place_id, world.world_time,
                                    len(occupants), self.module_id, "fraction")
            if seeded_uniform(frac_seed) < fraction:
                wanted += 1
            if wanted <= 0:
                continue
            if emitted + wanted >= p["max_encounters_per_tick"]:
                reasons.append(("diffusion.tick_capped", float(emitted + wanted),
                                {"cap": p["max_encounters_per_tick"], "place": place_id,
                                 "note": "encounters deferred to the next tick"}))

            for index in range(wanted):
                speaker, listener = self._participants(world, occupants, place_id, index)
                if speaker is None:
                    continue
                tie = self._tie(runtime, speaker, listener)
                if tie < p["min_tie"]:
                    reasons.append(("diffusion.no_tie", tie,
                                    {"speaker": speaker.id, "listener": listener.id}))
                    continue
                if self._tell(world, runtime, speaker, listener, place_id, reasons):
                    emitted += 1
        return reasons

    def _audience(self, world, speaker, listener, place_id) -> list:
        """Who can hear this exchange: the listener, plus a few people nearby."""
        others = sorted(a.id for a in world.agents.values()
                        if a.location == place_id and a.id not in (speaker.id, listener.id))
        limit = max(0, int(self.params["bystanders"]))
        if not others or limit == 0:
            return [listener.id]
        seed = derive_seed(world.global_seed, speaker.id, listener.id,
                           world.world_time, self.module_id, "audience")
        start = int(seeded_uniform(seed) * len(others))
        nearby = [others[(start + i) % len(others)] for i in range(min(limit, len(others)))]
        return [listener.id, *nearby]

    def _participants(self, world, occupants, place_id, index):
        """Deterministically pick who is talking to whom in this encounter."""
        if len(occupants) < 2:
            return None, None
        s_seed = derive_seed(world.global_seed, place_id, world.world_time,
                             index, self.module_id, "speaker")
        l_seed = derive_seed(world.global_seed, place_id, world.world_time,
                             index, self.module_id, "listener")
        speaker = occupants[int(seeded_uniform(s_seed) * len(occupants)) % len(occupants)]
        others = [a for a in occupants if a.id != speaker.id]
        listener = others[int(seeded_uniform(l_seed) * len(others)) % len(others)]
        return speaker, listener

    # ------------------------------------------------------------- selection --
    @staticmethod
    def _populated_places(world, player_id):
        places = {}
        for agent in world.agents.values():
            if agent.id == player_id:
                continue
            if agent.location:
                places.setdefault(agent.location, []).append(agent)
        return {pid: sorted(occ, key=lambda a: a.id)
                for pid, occ in places.items() if len(occ) >= 2}

    @staticmethod
    def _pairs(occupants):
        # Ordered pairs: telling is directional, and A telling B is not B telling A.
        for speaker in occupants:
            for listener in occupants:
                if speaker.id != listener.id:
                    yield speaker, listener

    def _tie(self, runtime, speaker, listener) -> float:
        """How likely these two are to swap news at all.

        Uses the social-network model that shipped with the runtime but was never
        called by anything: tie strength from familiarity and liking, raised for
        people whose role puts them at a crossing point of the community.
        """
        strength = runtime.network.tie_strength(speaker, listener.id)
        bridge = runtime.network.bridge_score(speaker)
        return max(0.0, min(1.0, 0.7 * strength + 0.3 * bridge))

    def _tellable(self, speaker, world, threshold_shift: float = 0.0):
        """Beliefs this speaker holds confidently and is not withholding.

        Ranked by how much it is on their mind: confidence margin, weighted by how
        recently it was updated. Protected propositions never appear -- a secret is
        not gossip, and that filter is the same one the dialogue planner uses.
        """
        from . import content
        protected = content.protected_keys(speaker.secrets)
        # A guarded place raises the bar: you pass on what you are surer of, and
        # keep the rest. Zero when the climate layer is off.
        floor = self.params["min_confidence_to_tell"] + threshold_shift
        candidates = []
        for key, belief in speaker.beliefs.items():
            if key in protected:
                continue
            confidence = max(belief.expected_prob, 1.0 - belief.expected_prob)
            if confidence < floor:
                continue
            if not belief.spreading:
                continue          # they have lost interest in passing this one on
            if belief.hops >= self.params["max_hops"]:
                continue
            recency = 1.0 / (1.0 + max(0, world.world_time - (belief.txn_time or 0)) / 240.0)
            candidates.append((confidence * (0.4 + 0.6 * recency), key, belief))
        candidates.sort(key=lambda c: (-c[0], c[1]))
        return candidates

    # --------------------------------------------------------------- telling --
    def tell_about(self, world, runtime, speaker, listener, place_id, key,
                   reasons, medium=None) -> bool:
        """Say this particular thing to this particular person.

        The public half of `_tell`: somebody with a reason supplies the topic,
        and everything after it -- the topology gate, distortion, the claim event,
        earshot, provenance, hops -- is the same code the random path runs. A
        purposeful conversation must not be a second kind of conversation.
        """
        belief = speaker.beliefs.get(key)
        if belief is None:
            return False
        return self._deliver(world, runtime, speaker, listener, place_id, key,
                             belief, reasons, medium)

    def _tell(self, world, runtime, speaker, listener, place_id, reasons) -> bool:
        climate = getattr(runtime, "climate", None)
        shift = (climate.modifiers(place_id) if climate is not None
                 else {}).get("tell_threshold", 0.0)
        candidates = self._tellable(speaker, world, shift)
        if not candidates:
            return False

        # Deterministically pick among the top few, so a speaker does not repeat
        # the single most salient item to everyone they meet.
        seed = derive_seed(world.global_seed, speaker.id, listener.id,
                           world.world_time, self.module_id, "topic")
        top = candidates[:3]
        _, key, belief = top[int(seeded_uniform(seed) * len(top)) % len(top)]
        return self._deliver(world, runtime, speaker, listener, place_id, key,
                             belief, reasons, None)

    def _deliver(self, world, runtime, speaker, listener, place_id, key, belief,
                 reasons, medium=None) -> bool:

        # Nobody says out loud what the two of them already watched a crowd find
        # out. This is categorical rather than the Daley-Kendall coin below: that
        # one models a spreader losing interest, this one models there being
        # nothing left to tell.
        public = getattr(runtime, "common_knowledge", None)
        if public is not None and public.is_common(key, speaker.id, listener.id):
            reasons.append(("common_knowledge.not_news", 0.0, {
                "speaker": speaker.id, "listener": listener.id,
                "proposition": key,
                "note": "both were there when it became public"}))
            return False

        # Would they pass THIS to THIS person, here? Restricted things stay inside
        # their circle, shop talk bores outsiders, and some claims do not
        # circulate in some places at all. This is what keeps a large cast from
        # converging on one shared memory.
        weight, (code, detail) = topology.may_pass_on(
            world, belief.proposition, speaker, listener, place_id)
        if weight <= 0.0:
            reasons.append((code, 0.0, {"speaker": speaker.id, "listener": listener.id,
                                        **detail}))
            return False
        gate = derive_seed(world.global_seed, speaker.id, listener.id,
                           world.world_time, self.module_id, "topology")
        if seeded_uniform(gate) > weight:
            reasons.append(("diffusion.not_worth_telling", weight,
                            {"speaker": speaker.id, "listener": listener.id, **detail}))
            return False

        listener_knew = key in listener.beliefs
        asserted_positive = belief.expected_prob >= 0.5

        # What gets retold may not be what was heard. A distorted claim becomes a
        # DIFFERENT proposition -- its own canonical key -- so the listener forms a
        # separate belief and a town can end up confidently believing something
        # that never happened. It still carries the true origin, so it stays one
        # source that is now wrong.
        told_proposition = belief.proposition
        distortion_kind = None
        distortion_detail = {}
        distort_seed = derive_seed(world.global_seed, speaker.id, listener.id,
                                   world.world_time, self.module_id, "distort")
        # A leaner medium loses more. This is the one number media richness
        # theory actually buys us, and it lands on the levelling the distortion
        # layer already implements rather than on a new mechanism.
        distortion_prob = self.params["distortion_prob"] * (
            medium.distortion_scale() if medium is not None else 1.0)
        if seeded_uniform(distort_seed) < distortion_prob:
            from . import content
            outcome = distortion.distort(
                belief.proposition, speaker=speaker, world=world,
                seed=derive_seed(world.global_seed, speaker.id, listener.id,
                                 world.world_time, self.module_id, "distort-kind"),
                weights=self.params.get("distortion_weights"),
                protected=content.protected_keys(speaker.secrets))
            if outcome is not None:
                told_proposition, distortion_kind, distortion_detail = outcome
                if distortion_kind == distortion.INVERSION:
                    asserted_positive = not asserted_positive
        distorted = distortion_kind is not None

        # The origin travels with the claim, NOT the teller. This is the whole
        # point: five mouths relaying one witness is still one witness.
        origin = belief.primary_origin or f"origin:{speaker.id}:{key}"
        hops = belief.hops + 1
        # Nobody overhears a phone call, which is exactly why a call is where a
        # secret goes -- and why a claim made on one leaves no bystanders holding
        # it afterwards.
        audience = (self._audience(world, speaker, listener, place_id)
                    if medium is None or medium.audience else [])
        # Conviction lost along the chain. This used to be computed, written into
        # the payload and never read by anything -- a documented parameter with no
        # effect. The runtime now scales the evidential weight of the assertion by
        # it, so a fifth-hand rumour genuinely persuades less than a first-hand one.
        strength = self.params["fidelity_decay"] ** hops
        if medium is not None:
            # A voice with no face behind it is harder to weigh, and everybody
            # knows it. This is the listener's discount for the channel, not a
            # claim that phones lie.
            strength *= medium.trust_factor

        event = Event(
            event_id=world.new_event_id(),
            world_time=world.world_time,
            type="claim",
            actor=speaker.id,
            location=place_id,
            payload={
                "proposition": told_proposition.as_dict(),
                "asserter_polarity": "+" if asserted_positive else "-",
                "origin_event": origin,
                "summary": f"{speaker.public_name or speaker.id} passes on what they heard",
                "importance": 0.35,
                "domain": "gossip",
                "audience": audience,
                "medium": (medium.name if medium is not None else "in_person"),
                "diffusion": {"speaker": speaker.id, "listener": listener.id,
                              "hops": hops, "distorted": distorted,
                              "distortion_kind": distortion_kind,
                              "distortion_detail": distortion_detail,
                              "fidelity": round(strength, 4)},
                "assertion_strength": round(strength, 4),
            },
        )
        # process_event applies the hop distance while updating each listener's
        # belief. Doing it there rather than afterwards keeps it a property of how
        # the belief was acquired, and lets it be the SHORTEST known distance to a
        # first-hand source: hearing your own rumour come back around from three
        # mouths away does not push you three mouths from what you witnessed.
        runtime.process_event(event)

        # Daley & Kendall (1964): a spreader who meets someone already informed
        # stops spreading. Without it, termination came from an arbitrary hop cap
        # and the rumour reached everybody; with it, saturation is an outcome of
        # the model rather than a number somebody picked.
        if listener_knew:
            stifle_seed = derive_seed(world.global_seed, speaker.id, listener.id,
                                      world.world_time, self.module_id, "stifle")
            if seeded_uniform(stifle_seed) < self.params["stifle_prob"]:
                belief.spreading = False
                reasons.append(("diffusion.stifled", float(hops), {
                    "speaker": speaker.id, "listener": listener.id,
                    "proposition": str(belief.proposition),
                    "note": "told someone who already knew; stopped spreading this"}))

        # A conversation is not only an exchange of claims. Whoever spoke was in
        # some mood while they did it, and a little of it stays with the listener.
        # Placed here, after the claim has landed, because it is a consequence of
        # the exchange rather than a condition on it: nothing about who catches a
        # mood decides who gets told what.
        contagion = getattr(runtime, "contagion", None)
        if contagion is not None:
            reasons.extend(contagion.between(speaker, listener))

        reasons.append(("diffusion.told", float(hops), {
            "speaker": speaker.id, "listener": listener.id, "place": place_id,
            "proposition": str(told_proposition),
            "origin": origin, "hops": hops, "distorted": distorted,
            "note": "origin travels with the claim; repeats from it stay discounted",
        }))
        if distorted:
            reasons.append(("diffusion.distorted", 1.0, {
                "speaker": speaker.id, "kind": distortion_kind,
                "heard": str(belief.proposition), "retold": str(told_proposition),
                "what_changed": distortion.describe(distortion_kind, distortion_detail),
                **distortion_detail}))
        return True
