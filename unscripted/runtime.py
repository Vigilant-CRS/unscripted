"""Runtime tick loop (spec v0.5 §6).

Wires the knowledge spine (Perception -> Belief -> Memory) and Part A (Affect)
for each event, collects reason traces, and persists projections. One pass per
event; emotion feedback applies to the next event (the deliberate simplification
in spec §12).
"""
from __future__ import annotations
from . import topology
from .interpretation import InterpretationEngine
from .perception import PerceptionEngine
from .belief import BeliefEngine
from .memory import Memory, MemoryEngine
from .affect import AffectEngine
from .determinism import derive_seed, seeded_uniform
from .events import Event
from .ontology import Proposition
from .relationship import RelationshipEngine, ReputationEngine, IdentityEngine
from .appearance import AppearanceEngine
from .standing import StandingEngine
from .social import (ValueEngine, SocialExchangeEngine, SocialIdentityEngine,
                     NormEngine, SocialNetworkEngine, TheoryOfMindEngine,
                     ImpressionManagementEngine)
from .sociolinguistics import SociolinguisticEngine
from .policy import PolicyEngine
from .actions import default_candidates
from .dialogue import DialoguePlanner, ConversationState
from .validator import (Validator, ACCEPT, CANON_OFF, REJECT_HARD,
                        REJECT_SOFT, is_unsafe)
from .provider import TemplateRealizer, ProviderError
from .agency import (default_reactive_rules, fire_reactive_rules, mobilization_candidate,
                     ally_response, resolve, risk_reference_point, leverage)
from .diffusion import DiffusionEngine
from .actionbridge import ActionBridge
from .climate import ClimateEngine
from .common_knowledge import CommonKnowledgeEngine
from .notes import NoteBoard
from .promises import PromiseLedger
from .contagion import ContagionEngine
from .pursuit import PursuitEngine
from .routine import RoutineEngine
from .factions import Faction, ProgressClock, Director


class Runtime:
    def __init__(self, world, store=None):
        self.world = world
        self.store = store
        self.perception = PerceptionEngine()
        self.interpretation = InterpretationEngine()
        self.belief = BeliefEngine()
        self.memory = MemoryEngine()
        self.affect = AffectEngine()
        # Part C owners
        self.relationship = RelationshipEngine()
        self.reputation = ReputationEngine()
        self.standing = StandingEngine(getattr(world, "standing_conduct", None))
        self.appearance = AppearanceEngine()
        self.identity = IdentityEngine()
        # social feature providers (§5.8-5.15)
        self.value = ValueEngine()
        self.exchange = SocialExchangeEngine()
        self.social_identity = SocialIdentityEngine()
        self.norm = NormEngine()
        self.network = SocialNetworkEngine()
        self.tom = TheoryOfMindEngine()
        self.impression = ImpressionManagementEngine()
        # sociolinguistics + Part B + dialogue stack
        self.socioling = SociolinguisticEngine()
        self.policy = PolicyEngine()
        self.planner = DialoguePlanner()
        # the validator scans for THIS world's protected vocabulary, gathered from
        # the secrets its characters actually hold
        self.validator = Validator.for_world(world)
        self.realizer = TemplateRealizer.for_world(world)
        # the deterministic safety net every fallback path uses; it carries the
        # same authored templates and slang as the primary realizer
        self.fallback_realizer = TemplateRealizer.for_world(world)
        self.conversations = {}
        self.last_traces = {}
        self._mem_counter = 0
        # population level-of-detail (opt-in): defer per-tick decay for dormant agents
        # and apply it lazily on access. Exact, not approximate: exponential decay is
        # composable, so one catch-up over the full elapsed time == many small steps.
        self.population_lod = False
        #: See RuntimeConfig.projection_scope. Set by the SDK; "all" here so a
        #: core used directly behaves as it always has.
        self.projection_scope = "all"
        #: See RuntimeConfig.semantic_release. "controlled" means a sentence that
        #: carries a fact is the pack's, not a provider's.
        self.semantic_release = "controlled"
        self._projected: set = set()
        #: Set to a marker while a tick is running, so per-event reasons are
        #: merged into one answer for the whole tick instead of overwriting each
        #: other. None outside a tick.
        self._collecting = None
        #: Reason entries a tick produced past the per-bucket cap, so a full
        #: bucket is never mistaken for a quiet one.
        self._dropped_traces: dict = {}
        self._last_decay = {aid: world.world_time for aid in world.agents}
        # daily routines move the cast; diffusion needs people to actually meet
        self.routine = RoutineEngine.for_world(world)
        #: Physical acts an engine carries out. Disabled here so a core used
        #: directly behaves as it always has; the SDK turns it on from config.
        self.actions_out = ActionBridge(enabled=False)
        # information diffusion: who tells whom what, over time
        self.diffusion = DiffusionEngine.for_world(world)
        #: What it is like in each place. Disabled here so a core used directly
        #: behaves exactly as it did before this layer existed.
        self.climate = ClimateEngine.for_world(world, enabled=False)
        #: Who has a reason to speak, as opposed to who happens to be standing
        #: next to whom. Disabled here so a core used directly is unchanged.
        self.pursuit = PursuitEngine(enabled=False, media=False)
        #: Whether somebody else's afternoon rubs off. Disabled here for the same
        #: reason as the rest: a core used directly is exactly what it was.
        self.contagion = ContagionEngine(enabled=False)
        #: What is out in the open, as opposed to merely widely known. Disabled
        #: here for the same reason as the rest.
        self.common_knowledge = CommonKnowledgeEngine(enabled=False)
        #: What has been left lying about. Disabled here as the rest are.
        self.notes = NoteBoard(enabled=False)
        #: What has been undertaken, and whether it came to anything. Disabled
        #: here as the rest are.
        self.promises = PromiseLedger(enabled=False)
        #: Set by the SDK so gossip can skip the player unless a pack opts in.
        self.player_id = None
        # agency + faction/director layer
        self.reactive_rules = default_reactive_rules()
        self.director = Director()
        for fd in getattr(world, "factions", []):
            self.director.add_faction(Faction(
                faction_id=fd["id"], influence=fd.get("influence", 0.5),
                resources=fd.get("resources", 0.5), territory=fd.get("territory", []),
                goals=fd.get("goals", []),
                clocks={g: ProgressClock(g, 6) for g in fd.get("goals", [])}))
        # tag agents with seed + world lookup for deterministic, context-aware modules
        for a in world.agents.values():
            a.__dict__["_global_seed"] = world.global_seed
            a.__dict__["_world_lookup"] = lambda aid: world.agents.get(aid)

    # ---------- event path ----------
    def process_event(self, event: Event, dt: float = 1.0):
        # The room is already different by the time the claim lands in it, and
        # the trace says so: a designer watching a scene go wrong needs to see
        # the weather move, not infer it from a number three screens away.
        for reason in self.climate.react(event):
            self.last_traces.setdefault("_climate", []).append(reason)
        w = self.world
        w.world_time = max(w.world_time, event.world_time)
        if self.store:
            self.store.append_event(event)

        # macro: a faction-scale mobilization arriving (e.g. police raid) -- narrate, discharge threat
        if event.type == "faction_mobilize":
            fid = event.payload.get("faction")
            self.last_traces["_director"] = [("director.arrived", 1.0,
                                              {"faction": fid, "place": event.location})]
            return self.last_traces

        # heat: crimes/threats/attacks raise the controlling faction's escalation accumulator
        if event.type in ("threat", "attack", "crime") and event.location:
            f = self.director.faction_controlling(event.location)
            if f:
                place = w.places.get(event.location, {})
                obs = place.get("surveillance_level", 0.3)
                sev = event.payload.get("severity", abs(event.appraisal.get("desirability", -0.5)))
                self.director.add_heat(f.faction_id, 0.25 * abs(sev) * (0.5 + obs), "observed_violence")

        observations = self.perception.filter(event, w)
        traces = {}
        #: Who actually took the claim in, for the common-knowledge layer. Collected
        #: from the loop below rather than recomputed, so the two cannot disagree
        #: about what people heard.
        took_in = []
        for obs in observations:
            agent = w.agents[obs.observer]
            self._catch_up(agent)  # bring a dormant agent's decay current before it reacts
            rt = []
            #: Reset per observer. It is only read where it was just assigned,
            #: but leaving it to carry over from the previous observer is a
            #: NameError on the first iteration and a wrong answer on the rest,
            #: waiting for whoever moves these blocks around next.
            belief = None

            # 2. Belief update (only for communicated/observed propositions)
            #
            # A question names a proposition without asserting it, so it must not
            # reach the belief system at all -- it is still perceived and encoded
            # below, because being asked is something that happened to you.
            prop = None if event.type == "question" else event.proposition
            # You do not learn anything by hearing yourself say it. Without this,
            # a character asserting something becomes surer of it -- their own
            # utterance arrives back as evidence from a fresh origin, which is a
            # provenance loop and turns repetition into proof.
            if obs.observer == event.actor:
                prop = None
            if prop is not None:
                # Seeing is not understanding. Attention decides whether this
                # observer took it in at all, and competence decides whether they
                # could identify it -- so four witnesses can end up holding four
                # different claims about one event, each first-hand.
                prop, interp_reasons = self.interpretation.interpret(
                    agent, event, prop, w, obs.quality, modality=obs.modality)
                rt += interp_reasons
                # Nobody takes in everything they are told. Past a day's budget a
                # character hears and forgets -- which is what stops a long-lived
                # world from becoming one shared memory. Only NEW claims cost
                # attention: being reminded of something you already hold is free.
                if prop is not None and prop.core_key() not in agent.beliefs:
                    if not topology.spend_attention(agent, w):
                        rt.append(("attention.exhausted",
                                   float(agent.attention_spent),
                                   {"budget": topology.attention_budget(agent),
                                    "dropped": str(prop),
                                    "note": "heard it, had no room left today"}))
                        prop = None
            if prop is not None:
                speaker = event.actor
                trust = agent.trust_in(speaker) if speaker else 0.3
                # media: credibility from channel; otherwise speaker competence in topic domain
                if event.type == "broadcast":
                    competence = event.payload.get("credibility", 0.5)
                    trust = event.payload.get("credibility", 0.5)
                elif event.type in self.WITNESSED_ACTS:
                    # SEEING IT IS NOT BEING TOLD IT. Every other proposition
                    # that reaches this point is testimony -- a claim, or a
                    # broadcast -- and is rightly discounted by how far the
                    # source is trusted. An act you watched is not: it is
                    # evidence about the world, and how much you trust the
                    # person who did it has nothing to do with whether it
                    # happened. Without this a character hit in front of a room
                    # believed it at p=0.52, because the runtime was asking how
                    # far they trusted their assailant's testimony.
                    #
                    # `obs.quality` still discounts it below, so a bad line of
                    # sight in a dark room is a poor witness, which is right.
                    trust = 1.0
                    competence = 0.95
                else:
                    # Competence is domain-specific: a doctor on medicine and a
                    # bartender on gossip are not equally credible. `domain` was
                    # read and then discarded in favour of a flat 0.5, so
                    # Agent.competence_in() -- and the education authored on every
                    # character -- had no effect on belief at all.
                    domain = event.payload.get("domain", "street")
                    speaker_agent = w.agents.get(speaker) if speaker else None
                    competence = (speaker_agent.competence_in(domain)
                                  if speaker_agent is not None else 0.5)
                origin = event.payload.get("origin_event", event.event_id)
                # Quality attenuates trust (partial hearing -> weaker evidence), and
                # so does how convinced the speaker still is: a claim relayed down a
                # long chain is asserted with less force and should persuade less.
                strength = float(event.payload.get("assertion_strength", 1.0))
                eff_trust = trust * obs.quality * max(0.0, min(1.0, strength))
                # AND WHO THEY BELIEVE, WHICH IS NOT THE SAME AS WHO THEY TRUST.
                # One character takes the radio as gospel and the neighbours as
                # noise; another is the exact reverse. That is a fact about a
                # person, not about the claim, and it was the one thing a pack
                # could not say.
                credence, credence_reason = self._source_credence(agent, event, obs, w)
                if credence != 1.0:
                    eff_trust *= credence
                    rt.append(credence_reason)
                existing = agent.beliefs.get(prop.core_key())
                prior_hops = None if existing is None else existing.hops
                belief, br = self.belief.update(
                    agent.beliefs, prop,
                    asserter_polarity=event.payload.get("asserter_polarity", prop.polarity),
                    trust=eff_trust, competence=competence,
                    skepticism=max(0.0, min(1.0, agent.skepticism + self.climate.modifiers(
                        event.location or agent.location)["skepticism"])),
                    claim_id=f"clm_{event.event_id}", origin_event=origin,
                    world_time=w.world_time, speaker=speaker)
                rt += br
                # Social distance from a first-hand source: always the SHORTEST
                # path known. Witnessing something, or hearing it on a channel, is
                # first-hand (0). A retold claim carries the teller's hop count.
                # Taking the minimum is what stops a rumour echoing back to its own
                # witness from relocating them away from what they saw.
                relayed = (event.payload.get("diffusion") or {}).get("hops")
                if relayed is None:
                    belief.hops = 0
                elif prior_hops is None:
                    belief.hops = relayed
                else:
                    belief.hops = min(prior_hops, relayed)

            if prop is not None:
                took_in.append((obs.observer, obs.quality))

            # WHAT THEY NOW THINK OF WHOEVER DID IT. Driven by the belief just
            # formed rather than by being in the room, which is what makes this
            # more than a reputation counter: the same line runs for somebody
            # who watched and for somebody who was merely told, and the second
            # one moves less because they believe it less.
            if self.standing.enabled and prop is not None and belief is not None:
                deltas, sr = self.standing.judge(agent, prop, belief.expected_prob)
                if deltas:
                    self.relationship.apply(
                        agent, [d for d in deltas if d.key.module == "relationship"], rt)
                    self.reputation.apply(
                        agent, [d for d in deltas if d.key.module == "reputation"], rt)
                    rt += sr

            # WHAT THEY LOOK LIKE TO THIS PERSON. Pure function of the tokens
            # and of what this observer is authored to be taken with, so writing
            # it on every perception is idempotent and costs nothing when no
            # pack authors `drawn_to` -- which is every pack.
            if event.actor and event.actor != agent.id:
                seen = w.agents.get(event.actor)
                if seen is not None:
                    pull = self.appearance.drawn_to(agent, seen, w)
                    if pull:
                        rel = agent.relationships.setdefault(event.actor, {})
                        if rel.get("attraction") != pull:
                            rel["attraction"] = pull
                            rt.append(("appearance.drawn_to", round(pull, 4), {
                                "observer": agent.id, "to": event.actor,
                                "note": "authored, not decided here: this "
                                        "character is taken with how that one "
                                        "looks"}))

            # WHEN ONE OF YOURS IS HURT. Attacking a keeper makes every other
            # keeper's belonging suddenly matter -- which is Tajfel's point and
            # the reason SocialIdentityEngine was written. It has been in the
            # runtime unreachable since then, because it asks the event which
            # identity is threatened and no event ever said: whether an event
            # threatens YOUR belonging depends on who you are, so it can only be
            # decided per observer, here.
            rt += self._identity_threat(agent, event)

            # 3. Memory encoding
            self._mem_counter += 1
            appraisal = event.appraisal
            valence = appraisal.get("desirability", 0.0) if appraisal else 0.0
            mtype = "commitment" if event.type == "promise" else "episodic"
            content = event.payload.get("summary") or f"{event.type} by {event.actor}"
            # WHAT THEY UNDERSTOOD, NOT WHAT HAPPENED. This used to store the
            # event's own proposition, so a character who demonstrably could not
            # identify what they saw -- the interpretation layer had just
            # coarsened `seal_breached(section, when=night_cycle)` down to
            # `when=None` for them -- still had the full, precise claim in an
            # episodic memory that `retrieve_memories` hands out. Belief and
            # recall disagreed about the same moment, and the API leaked the
            # detail the simulation had just decided they missed.
            #
            # A question is the exception, and it is not evidence either way: it
            # names a proposition without asserting it, and being asked about
            # something is what makes it retrievable later.
            remembered_prop = event.proposition if event.type == "question" else prop
            mem = Memory(memory_id=f"mem_{event.event_id}_{obs.observer}",
                         owner=agent.id, type=mtype, content=content,
                         proposition=remembered_prop,
                         importance=event.payload.get("importance", 0.5),
                         emotional_valence=valence, source_conf=obs.quality)
            rt += self.memory.encode(agent.memory, mem, w.world_time)

            # 4. Appraisal -> emotion -> PAD
            _, ar = self.affect.update(agent.affect, appraisal, dt)
            rt += ar

            traces[agent.id] = rt
            if self.store and self._projects(agent.id):
                # Targeted writes: this event changed at most one belief, added one
                # memory and moved affect. Rewriting the agent's entire projection
                # here made persistence dominate the event path.
                if prop is not None:
                    self.store.save_belief(agent.id, belief)
                self.store.save_memory(agent.id, mem)
                self.store.save_affect(agent.id, agent.affect)
                self.store.save_reason_trace(event.event_id, agent.id, rt)

        # WHAT THE PERSON WHO DID IT TAKES FROM HAVING DONE IT. The actor
        # perceives nothing here -- they are excluded from their own event -- but
        # they know what they did, and that is the only honest basis a character
        # has for guessing whether the next threat will land. Written here rather
        # than inside the observation loop for exactly that reason: it is not an
        # observation.
        if event.type in self.WITNESSED_ACTS:
            actor = w.agents.get(event.actor) if event.actor else None
            target_id = (event.payload or {}).get("target")
            if actor is not None and target_id:
                for reason in self.tom.note_own_act(
                        actor, target_id, event.type,
                        float((event.payload or {}).get("severity", 0.5))):
                    traces.setdefault(actor.id, []).append(reason)

        # Did this happen in front of enough people, in the open, that it is no
        # longer deniable? Asked once per event and after the fact, on the set of
        # people the perception layer says actually took it in -- so the two
        # cannot come to disagree about who was there.
        for reason in self.common_knowledge.observe(w, event, took_in):
            traces.setdefault("_common_knowledge", []).append(reason)

        # An undertaking becomes something that will be checked. Same witness
        # set as above, for the same reason: the people it was a promise to are
        # the people the perception layer says heard it.
        for reason in self.promises.record(w, event,
                                           [aid for aid, _q in took_in]):
            traces.setdefault("_promises", []).append(reason)

        if self.store:
            self.store.commit()   # one commit per event, not per observer

        # WITHIN A TICK, REASONS ACCUMULATE. This used to be a plain assignment,
        # which quietly threw away everything an earlier event in the same
        # `advance_time` had produced -- and `advance_time` fires many. Measured
        # on `market-square`: a week reported `climate.moved: 0` and
        # `common_knowledge.established: 0` while the layers demonstrably worked,
        # because those reasons are emitted per event and the next event erased
        # them. `_routine` and `_pursuit` went the same way, erased by the first
        # claim that diffusion delivered afterwards.
        #
        # A single `emit_event` still REPLACES, because "what did this event
        # cause" is the right answer there and accumulating across separate calls
        # would grow without bound.
        if self._collecting is None:
            self.last_traces = traces
        else:
            self._collect(traces)
        return traces

    #: How many entries one reason bucket keeps per tick. Accumulating without a
    #: bound was a real cost, not a theoretical one: at two thousand characters
    #: one hour of world time produced 553,454 entries and 36 MB, and the tick
    #: went from 141 ms to over 300. Generous enough that a designer watching a
    #: scene sees all of it, and a run past it says by how much.
    MAX_TRACE_ENTRIES_PER_KEY = 400

    def _collect(self, traces: dict) -> None:
        """Merge one event's reasons into the answer for the whole tick.

        ONLY THE LAYER BUCKETS ACCUMULATE. The `_`-prefixed keys -- climate,
        diffusion, pursuit, notes, promises, common knowledge -- are what a
        caller reads to find out what happened during a time advance, and they
        were the ones being erased by whichever event came last.

        The per-agent buckets answer a different question -- what did THIS event
        do to this character -- and have always answered for the most recent
        one. Accumulating those as well was my mistake, it cost half a million
        entries a tick at scale, and it answered nobody's question.
        """
        for key, entries in traces.items():
            if not key.startswith("_"):
                self.last_traces[key] = entries
                continue
            bucket = self.last_traces.setdefault(key, [])
            room = self.MAX_TRACE_ENTRIES_PER_KEY - len(bucket)
            if room > 0:
                bucket.extend(entries[:room])
            dropped = len(entries) - max(0, room)
            if dropped > 0:
                self._dropped_traces[key] = self._dropped_traces.get(key, 0) + dropped

    #: Events that can make a shared belonging feel unsafe. Violence against a
    #: person, not against a place or a reputation -- being robbed is frightening
    #: and being robbed *for what you are* is a different thing, which is the
    #: distinction this layer exists to carry.
    IDENTITY_THREAT_EVENTS = ("attack", "threat", "crime")

    #: How much of a claim survives, per observer, according to WHERE IT CAME
    #: FROM. Authored as `epistemic.source_trust` on a character; absent means
    #: 1.0 and changes nothing, which is why adding this left every shipped pack
    #: byte-identical.
    #:
    #: Looked up most specific first, and the first hit wins rather than
    #: multiplying: a character who distrusts City Radio specifically should not
    #: also be charged for distrusting radio in general.
    def _source_credence(self, observer, event, obs, world):
        """`(multiplier, reason)` -- how far this observer credits this source."""
        table = (getattr(observer, "epistemic", None) or {}).get("source_trust")
        if not table:
            return 1.0, None
        keys = []
        channel = (event.payload or {}).get("channel")
        if event.type == "broadcast" and channel:
            keys.append(str(channel))
            kind = ((getattr(world, "channels", None) or {}).get(channel) or {}).get("type")
            if kind:
                keys.append(str(kind))
            keys.append("broadcast")
        elif getattr(obs, "modality", None) == "media":
            keys.append("broadcast")
        elif event.type in self.WITNESSED_ACTS or event.actor is None:
            keys.append("witnessed")
        else:
            speaker = world.agents.get(event.actor) if event.actor else None
            for role in (getattr(speaker, "roles", None) or ()):
                name = role.get("role") if isinstance(role, dict) else role
                if name:
                    keys.append(str(name))
            keys.append("told")
        for key in keys:
            if key in table:
                value = max(0.0, min(2.0, float(table[key])))
                return value, ("belief.source_credence", round(value, 3), {
                    "observer": observer.id, "matched": key, "tried": keys,
                    "note": "how far this person credits this kind of source"})
        return 1.0, None

    #: How much of the remaining distance to "knows them well" ONE HOUR in the
    #: same room closes. At 0.01 it takes about seventy hours together to pass
    #: halfway: a few weeks of sharing a street, not an afternoon.
    #:
    #: Time and not events, and the first attempt was events. That version grew
    #: familiarity only while something was happening, so two people who shared
    #: a room all day and had a quiet week ended the week as strangers -- and it
    #: stopped entirely once a world saturated, which is exactly when a cast
    #: should be settling into knowing each other. Measured: 0.600 -> 0.631 on
    #: the first day and then nothing for six more.
    FAMILIARITY_PER_HOUR = 0.01

    #: Events whose proposition describes something the observer SAW HAPPEN,
    #: rather than something somebody asserted. Physical acts only: a claim and
    #: a broadcast are testimony and belong on the trust path.
    WITNESSED_ACTS = ("attack", "threat", "crime", "gift")

    def _identity_threat(self, observer, event) -> list:
        """Did this happen to one of ours?"""
        if getattr(event, "type", "") not in self.IDENTITY_THREAT_EVENTS:
            return []
        target_id = (getattr(event, "payload", None) or {}).get("target")
        target = self.world.agents.get(target_id) if target_id else None
        if target is None or target.id == observer.id:
            # Being attacked yourself is handled by every other layer in the
            # runtime. This one is only about the people watching.
            return []
        mine = {i.get("id") for i in (observer.identities or ()) if i.get("id")}
        theirs = {i.get("id") for i in (target.identities or ()) if i.get("id")}
        shared = sorted(mine & theirs)
        if not shared:
            return []

        reasons = []
        for identity_id in shared:
            proposals, boost = self.social_identity.on_event(
                observer, event, self._context(observer), identity=identity_id)
            for proposal in proposals:
                current = observer.identity_threat.get(identity_id, 0.0)
                severity = float((event.payload or {}).get("severity", 0.5))
                raised = min(1.0, current + proposal.amount * severity)
                observer.identity_threat[identity_id] = raised
                reasons.append(("identity.threatened", round(raised, 4), {
                    "observer": observer.id, "identity": identity_id,
                    "because": target.id, "event": event.type,
                    "was": round(current, 4),
                    "note": "somebody who shares this belonging was attacked"}))
            if boost:
                # The appraisal the engine returns is the group-based emotion:
                # this is felt as an offence against you, by the person who did
                # it, even though it did not happen to you.
                _, affect_reasons = self.affect.update(observer.affect, boost, 1.0)
                reasons += affect_reasons
        return reasons

    #: World hours for a threatened belonging to fade halfway. A day: alarm on
    #: behalf of your group is not a grudge, and a threat that never faded would
    #: mean one attack permanently rewrote which identity a character leads with
    #: -- which is personality drift by another route, and this runtime does not
    #: do that.
    IDENTITY_THREAT_HALF_LIFE_HOURS = 24.0

    def _grow_familiarity(self, world, dt_minutes: int) -> None:
        """Time spent in the same room, before anybody moves on.

        Run before routines, so the hours just elapsed are credited to where
        people actually spent them rather than to where they are about to go.
        Symmetric: knowing somebody is not one-sided.
        """
        hours = max(0.0, dt_minutes / 60.0)
        if hours <= 0.0:
            return
        share = 1.0 - (1.0 - self.FAMILIARITY_PER_HOUR) ** hours
        if share <= 0.0:
            return
        by_place = {}
        for agent in world.agents.values():
            if agent.location:
                by_place.setdefault(agent.location, []).append(agent)
        for together in by_place.values():
            if len(together) < 2:
                continue
            for one in together:
                for other in together:
                    if one is other:
                        continue
                    rel = one.relationships.setdefault(other.id, {})
                    known = float(rel.get("familiarity", 0.0))
                    if known < 0.999:
                        rel["familiarity"] = min(1.0, known + share * (1.0 - known))

    def _fade_identity_threat(self, agent, dt_minutes: int) -> None:
        if not agent.identity_threat or dt_minutes <= 0:
            return
        keep = 0.5 ** ((dt_minutes / 60.0) / self.IDENTITY_THREAT_HALF_LIFE_HOURS)
        for identity_id in list(agent.identity_threat):
            faded = agent.identity_threat[identity_id] * keep
            if faded < 0.01:
                del agent.identity_threat[identity_id]
            else:
                agent.identity_threat[identity_id] = faded

    def _projects(self, agent_id: str) -> bool:
        """Does this character get a resident SQL projection of their state?

        The ledger is authoritative regardless; this decides only whether the
        read-model is kept warm. Writing it for a cast of hundreds costs four
        fifths of the tick and buys nothing for characters nobody has met.
        """
        if self.projection_scope == "all":
            return True
        if self.projection_scope == "none":
            return False
        return agent_id in self._projected

    def project_for(self, *agent_ids) -> None:
        """Keep these characters' projections warm from now on."""
        self._projected.update(a for a in agent_ids if a)

    def _catch_up(self, agent):
        """Population LOD: apply deferred decay for a dormant agent up to now.

        Exact, not lossy: affect mood relaxes and emotions decay by exp(-dt/tau),
        and exp is composable, so one catch-up over the full elapsed dt yields the
        same state as having decayed every tick. No-op when LOD is off.
        """
        if not self.population_lod:
            return
        last = self._last_decay.get(agent.id, self.world.world_time)
        dt = self.world.world_time - last
        if dt > 0:
            self.affect.decay(agent.affect, dt)
            self._fade_identity_threat(agent, dt)
            self.memory.decay_and_consolidate(agent.memory, self.world.world_time)
        self._last_decay[agent.id] = self.world.world_time

    # ---------- periodic path (time advance) ----------
    def advance_time(self, delta: int):
        """Advance the world by `delta` minutes.

        Tick order matters and is deliberate:

          1. scheduled events that fall due in the window;
          2. the cast goes about its day (routines move people);
          3. social activity during the window (information diffusion);
          4. the effect of elapsed time on every agent (decay, consolidation);
          5. the macro layer (faction clocks, heat, mobilization).

        Diffusion must come before decay, not after: a retelling creates memories,
        and memory caps are enforced during consolidation. Running it afterwards
        left the tick ending over the cap -- the bound held only until the next
        tick, which is not a bound.
        """
        w = self.world
        # One answer for the whole tick, not for whichever event happened to be
        # last. See the note in `process_event`.
        self.last_traces = {}
        self._dropped_traces = {}
        self._collecting = True
        try:
            return self._advance(w, delta)
        finally:
            self._collecting = None
            for key, dropped in sorted(self._dropped_traces.items()):
                self.last_traces.setdefault(key, []).append(
                    ("trace.truncated", float(dropped), {
                        "bucket": key, "dropped": dropped,
                        "kept": self.MAX_TRACE_ENTRIES_PER_KEY,
                        "note": "more reasons this tick than one bucket keeps; "
                                "the count is exact"}))

    def _elapse(self, w, minutes: int) -> None:
        """Let `minutes` of world time pass over the cast, and nothing else.

        Time itself: expiries, the weather, hours spent in the same room, and the
        day's schedule. Not the social layers -- those run once per tick, after
        the window has been walked.

        Every step in here is composable, which is what makes walking a window in
        pieces give the same answer as taking it whole. Climate relaxation and
        familiarity growth are both `x += (target - x) * (1 - k**t)`, and
        `1 - k**(a+b)` is exactly the two applied in turn.
        """
        if minutes <= 0:
            return
        w.world_time += minutes
        # An engine that never answered has to stop holding a character. Done
        # before routines run, so the next block can issue a fresh intent rather
        # than finding the last one still open.
        for record in self.actions_out.expire(w.world_time):
            self.last_traces.setdefault("_actions", []).append(
                ("action.timed_out", 0.0, {"intent": record.intent.intent_id,
                                           "actor": record.intent.actor,
                                           "type": record.intent.type}))
        self.climate.step(w, minutes)
        self._grow_familiarity(w, minutes)
        rreasons = self.routine.step(w, self, minutes)
        if rreasons:
            self.last_traces.setdefault("_routine", []).extend(rreasons)

    def _advance(self, w, delta: int):
        target = w.world_time + delta
        # THE WINDOW IS WALKED IN ORDER, and this is not a refinement. Scheduled
        # events used to be processed first, in a batch, against the positions
        # everybody held at the START of the window -- so who witnessed an
        # incident depended on how large a step the caller happened to take. One
        # `advance_time(30)` made a character a witness to something that
        # happened at minute 20 in a room they had left at minute 10;
        # `advance_time(10)` then `advance_time(20)` did not. Both end at the
        # same place at the same time, and only one of them can be right about
        # the past.
        #
        # So: move the cast up to each moment something is scheduled to happen,
        # let it happen there, and carry on.
        due = sorted((e for e in w.scenario_events
                      if w.world_time < e.world_time <= target),
                     key=lambda e: (e.world_time, e.event_id))
        for e in due:
            self._elapse(w, e.world_time - w.world_time)
            self.process_event(e, dt=1.0)
            w.scenario_events.remove(e)
        # people go about their day first, then they talk: diffusion depends on who
        # is standing where, so moving after it would have everyone gossip with
        # yesterday's company.
        self._elapse(w, target - w.world_time)

        # Whoever has a reason to raise something goes and raises it. Before
        # diffusion, because a purposeful conversation should get the room before
        # the random ones do -- and after routines, because it needs people to
        # have arrived where they are going.
        preasons = self.pursuit.step(w, self, delta, player_id=self.player_id)
        if preasons:
            self.last_traces.setdefault("_pursuit", []).extend(preasons)

        # Anything left lying about gets picked up -- by whoever it was for, or
        # by somebody it was not. After pursuit, so a note left this tick is not
        # read in the same one, which would make it a conversation.
        # Whatever has come due is settled before anybody acts on today, so a
        # character who was let down last night meets the world knowing it.
        preasons2 = self.promises.step(w, self, delta)
        if preasons2:
            self.last_traces.setdefault("_promises", []).extend(preasons2)

        nreasons = self.notes.step(w, self, delta)
        if nreasons:
            self.last_traces.setdefault("_notes", []).extend(nreasons)

        # information moves through the society during the elapsed time
        freasons = self.diffusion.step(w, self, delta, player_id=self.player_id)
        if freasons:
            self.last_traces.setdefault("_diffusion", []).extend(freasons)

        # decay affect and memory. With population LOD on, only agents that are
        # emotionally engaged (active emotions) are decayed now; calm/dormant agents
        # are caught up lazily on access (exact via composable exponential decay),
        # turning an O(population) tick into O(active).
        for agent in w.agents.values():
            if self.population_lod and not agent.affect.active_emotions:
                continue
            # decay over time elapsed since this agent was last decayed, not the
            # raw window: a mid-window event may already have caught the agent up
            # (LOD), and double-counting that span would over-decay affect.
            dt = target - self._last_decay.get(agent.id, w.world_time)
            if dt > 0:
                self.affect.decay(agent.affect, dt)
                self._fade_identity_threat(agent, dt)
            dropped = self.memory.decay_and_consolidate(agent.memory, target)
            self._last_decay[agent.id] = target
            if self.store:
                self.store.save_affect(agent.id, agent.affect)
                for reason in dropped:
                    # consolidation replaced episodes with a summary: persist the
                    # summary and delete the originals, or the store keeps growing
                    # with memories the agent no longer has
                    self.store.delete_memories(agent.id, reason[2].get("dropped_ids", ()))
                    summary_id = reason[2].get("summary")
                    for m in agent.memory:
                        if m.memory_id == summary_id:
                            self.store.save_memory(agent.id, m)
        # Director advances faction clocks + heat and may schedule faction mobilizations.
        def _sched(world, etype, faction, latency):
            ev = Event(event_id=world.new_event_id(), world_time=world.world_time + latency,
                       type=etype, actor=faction.faction_id,
                       location=(faction.territory[0] if faction.territory else None),
                       payload={"faction": faction.faction_id})
            world.scenario_events.append(ev)
            return ev
        if self.store:
            self.store.commit()   # one commit per tick
        # the macro layer reacts last, to a world that has already talked
        dreasons = self.director.step(w, delta, _sched)
        if dreasons:
            self.last_traces.setdefault("_director", []).extend(dreasons)
        w.world_time = target

    # ---------- convenience: player speech as a claim event ----------
    def player_says(self, speaker_id, location, proposition: Proposition, *,
                    summary=None, appraisal=None, importance=0.5, domain="street"):
        ev = Event(event_id=self.world.new_event_id(), world_time=self.world.world_time,
                   type="claim", actor=speaker_id, location=location,
                   payload={"proposition": proposition.as_dict(), "summary": summary,
                            "appraisal": appraisal or {}, "importance": importance, "domain": domain})
        return self.process_event(ev)

    # ---------- context builder ----------
    def _ensure_tag(self, agent):
        agent.__dict__.setdefault("_global_seed", self.world.global_seed)
        agent.__dict__.setdefault("_world_lookup", lambda aid: self.world.agents.get(aid))

    def _context(self, agent, interlocutor=None):
        place = self.world.places.get(agent.location, {})
        # `threat_by_identity` was never passed, so IdentityEngine's `w_threat`
        # term -- a full quarter of what decides which identity is salient -- was
        # multiplied by zero in every world since it was written.
        sal_id, sal = self.identity.salience(
            agent, {}, threat_by_identity=agent.identity_threat)
        front_audience = sum(1 for o in self.world.agents.values()
                             if o.id != agent.id and o.location == agent.location)
        return {"interlocutor": interlocutor, "place": agent.location,
                "surveillance_level": place.get("surveillance_level", 0.0),
                "audience_size": front_audience, "salient_identity": sal_id,
                "salience": sal, "authority_legitimacy": 0.5,
                "public_role_formal": any(r.get("role") in ("role:bartender", "role:officer")
                                          for r in agent.roles),
                "player_owes": self._interlocutor_owes(agent, interlocutor)}

    def _interlocutor_owes(self, agent, interlocutor):
        if not interlocutor:
            return False
        for belief in agent.beliefs.values():
            prop = belief.proposition
            if prop.predicate != "economy:owes_amount":
                continue
            if prop.slots.get("debtor") == interlocutor and prop.slots.get("creditor") == agent.id:
                return belief.expected_prob >= 0.5
        return False

    # ---------- decision (Part B + C) ----------
    def style_for(self, agent, interlocutor, salient_identity=None):
        """How this character speaks to this person, in one place.

        There were three call sites computing this -- the decision path here and
        two in the SDK, for a direct answer and for a cover story -- and adding
        fear and respect to one of them changed the register in a scene driven
        through `decide` and left it untouched in the two paths a game actually
        hits most. Three copies of a calculation is three chances for them to
        disagree, and they had already begun to.

        `regard` is passed only with the standing layer on: without it fear and
        respect never move, so it would be a constant, and a constant that
        perturbs every line of dialogue is what "off is byte-identical" forbids.
        """
        regard = (agent.relationships.get(interlocutor)
                  if (self.standing.enabled and interlocutor) else None)
        return self.socioling.compute_style(
            agent, interlocutor=interlocutor, place=agent.location,
            salient_identity=salient_identity, affect_engine=self.affect,
            world=self.world, regard=regard, appearance=self.appearance)

    def decide(self, agent_id, interlocutor=None, situation=None):
        """Score the action catalog and select one, with full reason codes.
        `situation` may carry {injured, threatened, threat_severity} for reactive rules."""
        import dataclasses
        agent = self.world.agents[agent_id]
        self._ensure_tag(agent)
        ctx = self._context(agent, interlocutor)
        ctx.update(situation or {})
        sal_id = ctx["salient_identity"]
        active_vals = self.value.active_values(agent, sal_id, ctx,
                                               identity_values=self.world.identity_values)

        # weights (personality + salient identity) -- spec §3.4
        weights = {
            "exchange": 1.0 + 0.5 * agent.big_five.get("agreeableness", 0.5),
            "norm": 1.0 + 0.6 * agent.big_five.get("conscientiousness", 0.5),
            "relationship": 1.0 + 0.5 * agent.big_five.get("agreeableness", 0.5),
            "safety": 1.0 + 0.6 * active_vals.get("security", 0.4),
            "income": 1.0,
            "face": self.impression.weight(ctx),
            "tom": 1.0,
        }
        candidates = list(default_candidates(agent, ctx))

        # ---- reactive context + rules (trigger -> priority action, preempts deliberation) ----
        eid = self.world.new_event_id()
        backup = mobilization_candidate(agent, self.world, urgency=1.0, event_id=eid)
        rctx = dict(ctx)
        rctx["has_backup"] = backup is not None
        reactive_reasons = []
        fired = fire_reactive_rules(agent, rctx, self.reactive_rules,
                                    reactive_reasons)
        forced_action_id = None
        if fired:
            top = max(fired, key=lambda r: r.priority)
            forced_action_id = top.action_id
            reactive_reasons.append(("agency.reactive_fired", top.priority,
                                     {"rule": top.rule_id, "action": top.action_id, "reason": top.reason}))
            # ensure the triggered action exists as a candidate
            if forced_action_id == "mobilize_allies" and backup is not None:
                candidates.append(backup[0])
            elif forced_action_id == "flee" and not any(c.action_id == "flee" for c in candidates):
                from .actions import ActionDefinition, ActionOutcome
                candidates.append(ActionDefinition("flee", "flee", interlocutor, is_dialogue=False,
                                                   outcomes=[ActionOutcome("safety", +0.5, 0.8, source="escape")]))

        # ---- budget -> risk: set the Prospect reference point from liquid resources ----
        if self.policy.params.get("use_prospect"):
            ref = risk_reference_point(agent)
            new_c = []
            for c in candidates:
                c.outcomes = [dataclasses.replace(o, reference_point=ref) for o in c.outcomes]
                new_c.append(c)
            candidates = new_c
            reactive_reasons.append(("agency.risk_reference", round(ref, 3),
                                     {"interpretation": "below->risk-seeking, above->risk-averse"}))

        def term_providers(action):
            terms = []
            terms += self.exchange.value_terms(agent, action, ctx)
            terms += self.norm.value_terms(agent, action, ctx)
            terms += self.impression.value_terms(agent, action, ctx)
            if interlocutor:
                terms.append(self.tom.expected_reaction(agent, interlocutor, action.action_class, ctx))
            return terms

        def bias_providers(action):
            """Pushes rather than opinions -- see `PolicyEngine.score`."""
            if not interlocutor:
                return 0.0
            # What they think of you, as a reason to answer or to turn away.
            # Zero unless the standing layer is on, so a world that declines
            # this mechanic decides exactly as it did before.
            pushed = self.standing.bias_for(agent, action, interlocutor)
            # And what you LOOK like, which is a different question and is kept
            # a different one: standing is what you have DONE. Zero unless the
            # pack authors `appearance_reactions`.
            pushed += self.appearance.bias_for(
                agent, action, self.world.agents.get(interlocutor), self.world)
            return pushed

        tendencies = self.affect.action_tendencies(agent.affect)
        scored = self.policy.score(agent, candidates, weights=weights,
                                   term_providers=term_providers,
                                   action_tendencies=tendencies,
                                   bias_providers=bias_providers)

        # a fired reactive rule adds a priority floor and makes selection near-deterministic
        saved_T = self.policy.params["temperature"]
        try:
            if forced_action_id:
                for c in scored:
                    if c.action.action_id == forced_action_id:
                        c.utility += top.priority
                        c.contributions.append(("reactive_priority", round(top.priority, 3), 1.0,
                                                round(top.priority, 3)))
                scored.sort(key=lambda c: c.utility, reverse=True)
                self.policy.params["temperature"] = 0.05
            chosen, reasons = self.policy.select(agent, scored, event_id=eid,
                                                 world_time=self.world.world_time)
        finally:
            # Without this, an exception during selection left the temperature
            # pinned at 0.05 for the rest of the process, quietly turning every
            # later decision near-deterministic.
            self.policy.params["temperature"] = saved_T
        reasons = reactive_reasons + reasons
        self.last_traces[agent_id] = reasons
        return chosen, scored, reasons

    # ---------- the action bridge: what the engine reports back ----------
    def resolve_action(self, intent_id: str, status: str, *, detail: str = "") -> dict:
        """Apply what the engine says happened, and nothing else.

        The runtime is not the authority on whether a character crossed a room --
        the engine is, because the engine is what the player watched. So this
        applies the effect on SUCCEEDED and, on every other result, records that
        the intent did not happen and leaves the character where the player last
        saw them. That is the whole point of the exchange: the two worlds agree,
        including when they agree that nothing moved.
        """
        record = self.actions_out.resolve(intent_id, status,
                                          world_time=self.world.world_time,
                                          detail=detail)
        intent = record.intent
        agent = self.world.agents.get(intent.actor)
        reasons = [("action.resolved", 1.0 if record.applied else 0.0,
                    {"intent": intent.intent_id, "actor": intent.actor,
                     "type": intent.type, "status": record.status,
                     "detail": record.detail})]
        if record.applied and intent.type == "MOVE_TO" and agent is not None:
            reasons.extend(self.routine.perform_move(
                self.world, self, agent, intent.params["place"],
                activity=intent.params.get("activity", "")))
        self.last_traces.setdefault("_actions", []).extend(reasons)
        return {"intent": intent.as_dict(), "status": record.status,
                "applied": record.applied, "reasons": reasons}

    # ---------- mobilization: call allies; schedule their arrival with latency ----------
    def mobilize(self, caller_id, *, urgency=1.0):
        """Resolve who responds and schedule their arrivals (latency). Returns the responder list."""
        caller = self.world.agents[caller_id]
        self._ensure_tag(caller)
        eid = self.world.new_event_id()
        backup = mobilization_candidate(caller, self.world, urgency=urgency, event_id=eid)
        if backup is None:
            return {"responders": [], "reasons": [("agency.no_allies", 0.0, {})]}
        _, responses = backup
        reasons, responders = [], []
        for r in responses:
            tag = "will_come" if r.will_come else "declines"
            reasons.append(("agency.ally_response", r.probability,
                            {"ally": r.ally_id, "p": r.probability, "latency": r.latency, "outcome": tag}))
            if r.will_come:
                responders.append(r)
                arrive = Event(event_id=self.world.new_event_id(),
                               world_time=self.world.world_time + r.latency, type="ally_arrives",
                               actor=r.ally_id, location=caller.location,
                               payload={"summary": f"{r.ally_id} arrives to back up {caller_id}",
                                        "caller": caller_id})
                self.world.scenario_events.append(arrive)
        self.last_traces[caller_id] = reasons
        return {"responders": responders, "reasons": reasons}

    # ---------- speaking: the one path a committed claim reaches the world by --

    #: How many bystanders can overhear one exchange. Matches the diffusion
    #: layer's figure, because it is the same physical fact about a room.
    EARSHOT = 3

    def earshot(self, speaker, addressee: str) -> list:
        """Who is close enough to hear this exchange, deterministically."""
        others = sorted(a.id for a in self.world.agents.values()
                        if a.location == speaker.location
                        and a.id not in (speaker.id, addressee))
        if not others:
            return [addressee]
        seed = derive_seed(self.world.global_seed, speaker.id, addressee,
                           self.world.world_time, "earshot")
        start = int(seeded_uniform(seed) * len(others))
        nearby = [others[(start + i) % len(others)]
                  for i in range(min(self.EARSHOT, len(others)))]
        return [addressee, *nearby]

    def domain_for(self, proposition) -> str:
        """Which competence applies to this claim, per the world's declaration."""
        declared = getattr(self.world, "predicate_domains", None) or {}
        return declared.get(proposition.predicate, "street")

    def spoken_origin(self, agent, move) -> str:
        """Which incident a spoken claim traces back to.

        The origin travels with the claim, not with the mouth it came out of. A
        lie is the exception and has no evidential ancestor, so it names the
        speaker AND the claim -- keyed on the clock instead, one liar repeating
        one lie became several independent sources.
        """
        own = self.world.agents[agent.id].beliefs.get(move.proposition.core_key())
        if move.honesty != "lie" and own is not None and own.primary_origin:
            return own.primary_origin
        return f"said_{agent.id}_{move.proposition.core_key()}"

    def carried(self, realizer, text: str, plan) -> bool:
        """Did these words actually make the claim the runtime committed to?

        `realizer` must be the one that produced `text`. Asking the provider
        about a line the FALLBACK wrote reads a flag left over from a call that
        never returned, which is how a thrown provider came to void a commitment
        the authored phrasing had expressed perfectly well.
        """
        if not plan.moves:
            return True
        reported = getattr(realizer, "expressed_commitment", None)
        if reported is not None:
            return bool(reported)
        from . import grounding
        return all(grounding.expresses(text, move.proposition, self.world)
                   for move in plan.moves if move.is_factual)

    def asserts_a_fact(self, plan) -> bool:
        return any(move.is_factual for move in plan.moves)

    def write_the_line(self, plan, provider_reasons: list):
        """Produce the sentence, and say who wrote it.

        Returns `(text, realizer, raw_provider_output, failed)`. In `controlled`
        release a plan that asserts something never reaches the provider at all:
        the guarantee is that the player reads the sentence the runtime wrote
        for this claim, and a sentence that was never asked for cannot disagree
        with it.
        """
        deterministic = self.fallback_realizer
        if self.semantic_release == "controlled":
            # EVERY released line, not only the ones the PLAN calls factual.
            # Gating on the plan was the mistake: a plan that asserts nothing does
            # not make a provider's answer assert nothing. Asked to write a
            # greeting, a model is free to add "He hides behind where drinks are
            # served" -- an indirect description of a protected place, in a turn
            # the runtime had classified as safe because it committed to no fact.
            # A guarantee that depends on the provider staying inside its brief
            # is not a guarantee.
            return deterministic.realize(plan, plan.style), deterministic, None, False
        try:
            text = self.realizer.realize(plan, plan.style)
            return text, self.realizer, text, False
        except ProviderError as exc:
            provider_reasons.append(("provider.failure", 1.0, {
                "provider": type(self.realizer).__name__, "error": str(exc)}))
            # The wording is lost; the commitment is not. It is only void if the
            # PACK cannot express it, which is a fact about the pack.
            return deterministic.realize(plan, plan.style), deterministic, "", True

    def speak_aloud(self, agent, moves, addressee: str) -> list:
        """Emit what was committed as a real claim event, and say who heard it.

        THERE IS ONE OF THESE, and there used to be one and a half. The SDK's
        answer path emitted the claim; `Runtime.say()` -- the deliberation path,
        and a public entry point -- realised a line, validated it and returned
        the text, and stopped. A character reached through the lower API could
        therefore tell somebody something in a room full of people and nobody
        learned anything, which is precisely the defect this runtime exists to
        remove, reintroduced through a second door.

        Only the COMMITMENT is emitted. The provider's wording is presentation
        and never reaches the belief system, which is what makes the text layer
        replaceable without changing the simulation.
        """
        spoken = []
        for move in moves:
            if not move.is_factual or move.proposition is None:
                continue
            strength = {"certain": 1.0, "probable": 0.8, "uncertain": 0.55}.get(
                move.certainty, 0.8)
            event = Event(
                self.world.new_event_id(), self.world.world_time, "claim",
                actor=agent.id, location=agent.location,
                payload={"proposition": move.proposition.as_dict(),
                         # A conversation is not a public announcement.
                         "audience": self.earshot(agent, addressee),
                         "summary": f"{agent.id} said so to {addressee}",
                         "importance": 0.45,
                         "assertion_strength": strength,
                         "domain": self.domain_for(move.proposition),
                         "spoken": {"addressee": addressee, "act": move.act,
                                    "certainty": move.certainty,
                                    "honesty": move.honesty},
                         "origin_event": self.spoken_origin(agent, move)})
            traces = self.process_event(event)
            spoken.append({
                "proposition": move.proposition.core_key(),
                "rendered": move.rendered(),
                "certainty": move.certainty,
                "honesty": move.honesty,
                "heard_by": sorted(o for o in traces if o != agent.id
                                   and not o.startswith("_"))})
        return spoken

    # ---------- speech (dialogue stack: plan -> realize -> validate) ----------
    def say(self, agent_id, interlocutor=None, conv_id=None):
        agent = self.world.agents[agent_id]
        self._ensure_tag(agent)
        chosen, scored, dreasons = self.decide(agent_id, interlocutor)
        ctx = self._context(agent, interlocutor)

        conv = self.conversations.setdefault(
            conv_id or f"conv_{agent_id}_{interlocutor}",
            ConversationState(conv_id or "conv", [agent_id, interlocutor]))

        style = self.style_for(agent, interlocutor,
                               salient_identity=ctx["salient_identity"])

        goal = (agent.goals[0]["content"] if agent.goals else "interact")
        plan = self.planner.plan(agent, conv, chosen, addressee=interlocutor, style=style,
                                 goal=goal, world_seed=self.world.global_seed,
                                 world_time=self.world.world_time)
        plan.request_id = f"say:{agent.id}:{self.world.world_time}:{conv.turn_count}"

        recent = list(conv.recent_lines)
        # buffered generation + validation loop (review P0.6)
        text, verdict = None, None
        raw_provider_output = None
        fallback_used = False
        wrote_it = self.fallback_realizer
        for attempt in range(2):
            # The same decision the SDK path makes, in the same place: who writes
            # a sentence that carries a fact, and what a thrown provider costs.
            text, wrote_it, raw_provider_output, _failed = self.write_the_line(
                plan, dreasons)
            authored = getattr(wrote_it, "is_deterministic", False)
            res = self.validator.check(text, plan, agent, recent,
                                       canon_mode=CANON_OFF if authored else None)
            verdict = res.verdict
            dreasons += res.reasons
            # Same distinction as the answer path: a repetition is a quality
            # objection and must not decide whether a commitment reaches the
            # world. Only an unsafe line sends the turn to a deflection.
            if verdict != ACCEPT and not is_unsafe(res):
                for spare in self.fallback_realizer.variants(plan, plan.style):
                    if spare == text:
                        continue
                    retry = self.validator.check(spare, plan, agent, recent,
                                                 canon_mode=CANON_OFF)
                    if retry.verdict == ACCEPT:
                        dreasons.append(("dialogue.reworded", 1.0,
                                         {"was": text, "now": spare}))
                        text, verdict, wrote_it = spare, retry.verdict, self.fallback_realizer
                        break
                else:
                    dreasons.append(("dialogue.released_anyway", 1.0, {
                        "verdict": verdict,
                        "note": "a quality objection, not a safety one"}))
                    verdict = ACCEPT
            if verdict == ACCEPT:
                break
            if verdict == REJECT_HARD:
                # fall back to a safe deflection template -- and drop the authored
                # phrasing, or `_lookup` returns it again and the deflection is a
                # no-op wearing a different act name.
                plan.dialogue_act = plan.fallback_template_id
                plan.phrasing = {}
        else:
            fallback_used = True
            plan = type(plan)(speaker=agent.id, addressee=interlocutor,
                              dialogue_act="deflect", goal=goal, style=plan.style)
            text = self.fallback_realizer.realize(plan, plan.style)
            res = self.validator.check(text, plan, agent, recent, canon_mode=CANON_OFF)
            verdict = res.verdict
            dreasons += res.reasons
        conv.recent_lines.append(text)
        del conv.recent_lines[:-5]  # shared, bounded, persisted anti-repeat window

        # AND THE ROOM HEARS IT. Without this the deliberation path was a second
        # speech pipeline that produced text and no consequence.
        expressed = self.carried(wrote_it, text, plan)
        if not expressed and not fallback_used and plan.moves:
            spare = self.fallback_realizer.realize(plan, plan.style)
            if spare != text and self.carried(self.fallback_realizer, spare, plan):
                recheck = self.validator.check(spare, plan, agent, recent,
                                               canon_mode=CANON_OFF)
                if recheck.verdict == ACCEPT:
                    dreasons.append(("dialogue.wording_replaced", 1.0, {
                        "provider_said": text, "released": spare,
                        "committed": list(plan.allowed_facts)}))
                    text, verdict, expressed = spare, recheck.verdict, True
        spoken = self.speak_aloud(
            agent, () if (fallback_used or not expressed) else plan.moves,
            interlocutor)
        if spoken:
            dreasons.append(("dialogue.spoken", float(len(spoken)),
                             {"spoken": spoken}))
        self.last_traces[agent_id] = dreasons
        if self.store and hasattr(self.store, "save_provider_call"):
            import hashlib
            import json
            prompt_data = {
                "speaker": plan.speaker,
                "addressee": plan.addressee,
                "act": plan.dialogue_act,
                "allowed_facts": plan.allowed_facts,
                "avoid_topics": plan.avoid_topics,
                "style": plan.style,
            }
            prompt_hash = hashlib.sha256(
                json.dumps(prompt_data, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            self.store.save_provider_call(
                turn_id=f"{conv.conv_id}:{conv.turn_count}",
                world_time=self.world.world_time,
                provider=type(self.realizer).__name__,
                model_id=getattr(self.realizer, "model_id", "deterministic-template"),
                prompt_hash=prompt_hash,
                raw_output=raw_provider_output if raw_provider_output is not None else text,
                accepted_output=text if verdict == ACCEPT else "",
                validation_result=verdict,
                data={"plan": prompt_data, "reasons": dreasons, "fallback_used": fallback_used},
            )
        return {"text": text, "act": plan.dialogue_act, "style": plan.style,
                "utility": round(chosen.utility, 3), "verdict": verdict,
                "spoken": spoken,
                "salient_identity": ctx["salient_identity"], "reasons": dreasons}
