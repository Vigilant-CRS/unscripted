// `usc/runtime.py`. The tick loop.
//
// Wires the knowledge spine -- perception, interpretation, belief, memory -- and
// affect for each event, collects reason traces, and advances the world. One pass
// per event; emotional feedback applies to the NEXT event, which is the
// deliberate simplification the spec names.
//
// WHAT IS NOT HERE: the store. Python's runtime writes every projection to
// SQLite as it goes, and that whole path is absent by design rather than by
// omission -- a console's save system belongs to the host, the snapshot layer
// hands it one opaque blob, and a header-only core with no dependencies has no
// business carrying a database. Every `if self.store:` branch in the reference
// is a write, never a read that changes an outcome, so the simulation this
// produces is the same one.
#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <string>
#include <vector>

#include "usc/actionbridge.hpp"
#include "usc/actions.hpp"
#include "usc/affect.hpp"
#include "usc/agency.hpp"
#include "usc/agent.hpp"
#include "usc/appearance.hpp"
#include "usc/belief.hpp"
#include "usc/climate.hpp"
#include "usc/common_knowledge.hpp"
#include "usc/contagion.hpp"
#include "usc/dialogue.hpp"
#include "usc/diffusion.hpp"
#include "usc/events.hpp"
#include "usc/factions.hpp"
#include "usc/interpretation.hpp"
#include "usc/memory.hpp"
#include "usc/notes.hpp"
#include "usc/ontology.hpp"
#include "usc/perception.hpp"
#include "usc/policy.hpp"
#include "usc/promises.hpp"
#include "usc/provider.hpp"
#include "usc/pursuit.hpp"
#include "usc/pyround.hpp"
#include "usc/reason.hpp"
#include "usc/relationship.hpp"
#include "usc/routine.hpp"
#include "usc/social.hpp"
#include "usc/sociolinguistics.hpp"
#include "usc/standing.hpp"
#include "usc/topology.hpp"
#include "usc/validator.hpp"
#include "usc/world.hpp"

namespace usc {

/// One tick's reasons, keyed by agent id or by a `_`-prefixed layer name.
using TraceMap = OrderedMap<std::vector<Reason>>;

class Runtime {
public:
    /// Events whose proposition describes something the observer SAW HAPPEN,
    /// rather than something somebody asserted. Physical acts only: a claim and
    /// a broadcast are testimony and belong on the trust path.
    static const std::vector<std::string>& witnessed_acts() {
        static const std::vector<std::string>* acts =
            new std::vector<std::string>{"attack", "threat", "crime", "gift"};
        return *acts;
    }

    /// Events that can make a shared belonging feel unsafe. Violence against a
    /// PERSON, not against a place or a reputation -- being robbed is
    /// frightening and being robbed for what you are is a different thing.
    static const std::vector<std::string>& identity_threat_events() {
        static const std::vector<std::string>* types =
            new std::vector<std::string>{"attack", "threat", "crime"};
        return *types;
    }

    /// How many entries one reason bucket keeps per tick. Accumulating without a
    /// bound was a real cost, not a theoretical one: at two thousand characters
    /// one hour of world time produced 553,454 entries and 36 MB, and the tick
    /// went from 141 ms to over 300.
    static constexpr long long MAX_TRACE_ENTRIES_PER_KEY = 400;

    /// How much of the remaining distance to "knows them well" ONE HOUR in the
    /// same room closes. At 0.01 it takes about seventy hours together to pass
    /// halfway: a few weeks of sharing a street, not an afternoon.
    ///
    /// TIME and not events, and the first attempt was events. That version grew
    /// familiarity only while something was happening, so two people who shared
    /// a room all day and had a quiet week ended it as strangers.
    static constexpr double FAMILIARITY_PER_HOUR = 0.01;

    /// World hours for a threatened belonging to fade halfway. A day: alarm on
    /// behalf of your group is not a grudge, and a threat that never faded would
    /// mean one attack permanently rewrote which identity a character leads with.
    static constexpr double IDENTITY_THREAT_HALF_LIFE_HOURS = 24.0;

    World& world;

    PerceptionEngine perception;
    InterpretationEngine interpretation;
    BeliefEngine belief;
    MemoryEngine memory;
    AffectEngine affect;
    RelationshipEngine relationship;
    ReputationEngine reputation;
    StandingEngine standing;
    AppearanceEngine appearance;
    IdentityEngine identity;
    ValueEngine value;
    SocialExchangeEngine exchange;
    SocialIdentityEngine social_identity;
    NormEngine norm;
    SocialNetworkEngine network;
    TheoryOfMindEngine tom;
    ImpressionManagementEngine impression;
    SociolinguisticEngine socioling;
    PolicyEngine policy;
    DialoguePlanner planner;
    Validator validator;
    TemplateRealizer realizer;
    /// The deterministic safety net every fallback path uses; it carries the
    /// same authored templates and slang as the primary realizer.
    TemplateRealizer fallback_realizer;
    RoutineEngine routine;
    OrderedMap<Routine> routines;
    ActionBridge actions_out;
    DiffusionEngine diffusion;
    ClimateEngine climate;
    PursuitEngine pursuit;
    ContagionEngine contagion;
    CommonKnowledgeEngine common_knowledge;
    NoteBoard notes;
    PromiseLedger promises;
    Director director;
    std::vector<ReactiveRule> reactive_rules = default_reactive_rules();

    OrderedMap<ConversationState> conversations;
    TraceMap last_traces;
    /// Population level-of-detail: defer per-tick decay for dormant agents and
    /// apply it lazily on access. EXACT, not approximate -- exponential decay is
    /// composable, so one catch-up over the full elapsed time equals many steps.
    bool population_lod = false;
    std::string player_id;

    explicit Runtime(World& setting)
        : world(setting),
          standing(setting.standing_conduct, false),
          validator(Validator::for_world(setting)),
          realizer(TemplateRealizer::for_world(setting)),
          fallback_realizer(TemplateRealizer::for_world(setting)),
          climate(setting.places, false),
          pursuit(false, false),
          contagion(false),
          common_knowledge(false),
          notes(false),
          promises(false) {
        for (const auto& entry : setting.agents)
            routines[entry.first] = Routine::from_json(entry.second.routine);
        for (const Json& declared : setting.factions) {
            Faction faction;
            faction.faction_id = declared.at("id").as_string();
            const Json* influence = declared.find("influence");
            faction.influence = influence ? influence->as_double() : 0.5;
            const Json* resources = declared.find("resources");
            faction.resources = resources ? resources->as_double() : 0.5;
            const Json* territory = declared.find("territory");
            if (territory) for (const Json& one : territory->items())
                faction.territory.push_back(one.py_str());
            const Json* goals = declared.find("goals");
            if (goals) for (const Json& goal : goals->items()) {
                faction.goals.push_back(goal.py_str());
                faction.clocks[goal.py_str()] = ProgressClock{goal.py_str(), 6};
            }
            director.add_faction(faction);
        }
        for (const auto& entry : setting.agents)
            last_decay_[entry.first] = setting.world_time;
        // THE SEED THE POLICY DRAWS FROM, captured here and not read live.
        //
        // Python tags every agent with `world.global_seed` in this constructor
        // and reads the tag back in `PolicyEngine.select`; the tag is written
        // with `setdefault`, so it is never refreshed. A caller that pins the
        // world's seed AFTER building the runtime -- which is exactly what the
        // conformance driver does -- therefore changes what diffusion, pursuit
        // and perception draw, and does NOT change what the policy draws.
        //
        // That is a wart, and it is reproduced rather than tidied: a fixture is
        // only evidence if the port agrees with the implementation that wrote
        // it, warts included. Fixing it belongs in both at once.
        tagged_seed_ = setting.global_seed;
    }

    /// The seed the policy draws from -- see the constructor.
    const std::string& tagged_seed() const { return tagged_seed_; }

    // ------------------------------------------------------------ event path --

    TraceMap process_event(const Event& event, double dt = 1.0) {
        // The room is already different by the time the claim lands in it, and
        // the trace says so: a designer watching a scene go wrong needs to see
        // the weather move, not infer it from a number three screens away.
        for (const Reason& reason : climate.react(event))
            last_traces["_climate"].push_back(reason);

        World& w = world;
        w.world_time = std::max(w.world_time, event.world_time);

        // A faction-scale mobilization arriving -- narrate, discharge threat.
        if (event.type == "faction_mobilize") {
            Json detail = Json::object();
            detail["faction"] = event.payload.get("faction");
            detail["place"] = event.location;
            last_traces["_director"] = {Reason{"director.arrived", 1.0, detail}};
            return last_traces;
        }

        // Heat: crimes, threats and attacks raise the controlling faction's
        // escalation accumulator.
        if ((event.type == "threat" || event.type == "attack" || event.type == "crime")
            && event.location.truthy()) {
            const Faction* faction = director.faction_controlling(event.location.py_str());
            if (faction) {
                const Json* place = w.places.find(event.location.py_str());
                const Json* seen = place ? place->find("surveillance_level") : nullptr;
                double observability = seen ? seen->as_double() : 0.3;
                const Json* severity = event.payload.find("severity");
                double sev = severity
                    ? severity->as_double()
                    : std::fabs(appraisal_number(event, "desirability", -0.5));
                director.add_heat(faction->faction_id,
                                  0.25 * std::fabs(sev) * (0.5 + observability),
                                  "observed_violence");
            }
        }

        std::vector<Observation> observations = perception.filter(event, w);
        TraceMap traces;
        /// Who actually took the claim in, for the common-knowledge layer.
        /// Collected from the loop below rather than recomputed, so the two
        /// cannot come to disagree about what people heard.
        std::vector<std::pair<std::string, double>> took_in;

        for (const Observation& obs : observations) {
            Agent* found = w.agents.find(obs.observer);
            if (!found) continue;
            Agent& agent = *found;
            catch_up_(agent);  // a dormant agent's decay, brought current
            std::vector<Reason> rt;
            /// Reset per observer. It is only read where it was just assigned,
            /// but letting it carry over from the previous observer is a wrong
            /// answer waiting for whoever moves these blocks around next.
            const Belief* formed = nullptr;

            // A QUESTION names a proposition without asserting it, so it must
            // not reach the belief system at all -- it is still perceived and
            // encoded below, because being asked is something that happened.
            std::optional<Proposition> prop;
            if (event.type != "question") prop = event.proposition();
            // You do not learn anything by hearing yourself say it. Without
            // this, a character asserting something becomes surer of it: their
            // own utterance arrives back as evidence from a fresh origin, which
            // is a provenance loop that turns repetition into proof.
            if (event.actor.truthy() && obs.observer == event.actor.py_str())
                prop.reset();

            if (prop) {
                // Seeing is not understanding.
                InterpretationEngine::Interpreted taken = interpretation.interpret(
                    agent, event, &*prop, w, obs.quality, obs.modality);
                for (const Reason& reason : taken.reasons) rt.push_back(reason);
                prop = taken.proposition;
                // Nobody takes in everything they are told. Past a day's budget
                // a character hears and forgets, which is what stops a
                // long-lived world becoming one shared memory. Only NEW claims
                // cost attention: being reminded is free.
                if (prop && !agent.beliefs.contains(prop->core_key())) {
                    if (!spend_attention(agent, w.world_time)) {
                        Json why = Json::object();
                        why["budget"] = attention_budget(agent);
                        why["dropped"] = prop->str();
                        why["note"] = std::string("heard it, had no room left today");
                        rt.push_back({"attention.exhausted",
                                      static_cast<double>(agent.attention_spent), why});
                        prop.reset();
                    }
                }
            }

            if (prop) {
                std::string speaker = event.actor.truthy() ? event.actor.py_str()
                                                           : std::string();
                double trust = speaker.empty() ? 0.3 : agent.trust_in(speaker);
                double competence = 0.5;
                if (event.type == "broadcast") {
                    const Json* credibility = event.payload.find("credibility");
                    competence = credibility ? credibility->as_double() : 0.5;
                    trust = competence;
                } else if (is_witnessed_act(event.type)) {
                    // SEEING IT IS NOT BEING TOLD IT. Every other proposition
                    // reaching this point is testimony and is rightly discounted
                    // by how far the source is trusted. An act you watched is
                    // not: how much you trust the person who did it has nothing
                    // to do with whether it happened. Without this a character
                    // hit in front of a room believed it at p=0.52, because the
                    // runtime was asking how far they trusted their assailant.
                    //
                    // `obs.quality` still discounts it below, so a bad line of
                    // sight in a dark room is a poor witness, which is right.
                    trust = 1.0;
                    competence = 0.95;
                } else {
                    // Competence is DOMAIN-SPECIFIC: a doctor on medicine and a
                    // bartender on gossip are not equally credible. The domain
                    // was read and then discarded in favour of a flat 0.5, so
                    // the education authored on every character had no effect on
                    // belief at all.
                    const Json* declared = event.payload.find("domain");
                    std::string domain = declared ? declared->py_str() : "street";
                    const Agent* teller = speaker.empty() ? nullptr
                                                          : w.agents.find(speaker);
                    competence = teller ? teller->competence_in(domain) : 0.5;
                }
                const Json* declared_origin = event.payload.find("origin_event");
                Json origin = declared_origin ? *declared_origin : Json(event.event_id);
                // Quality attenuates trust, and so does how convinced the
                // speaker still is: a claim relayed down a long chain is
                // asserted with less force and should persuade less.
                const Json* asserted = event.payload.find("assertion_strength");
                double strength = asserted ? asserted->as_double() : 1.0;
                double eff_trust = trust * obs.quality
                                 * std::max(0.0, std::min(1.0, strength));
                // AND WHO THEY BELIEVE, WHICH IS NOT WHO THEY TRUST. One
                // character takes the radio as gospel and the neighbours as
                // noise; another is the exact reverse. That is a fact about a
                // person, and it was the one thing a pack could not say.
                std::optional<Reason> credence_reason;
                double credence = source_credence(agent, event, obs, w, credence_reason);
                if (credence != 1.0) {
                    eff_trust *= credence;
                    if (credence_reason) rt.push_back(*credence_reason);
                }

                const Belief* existing = agent.beliefs.find(prop->core_key());
                std::optional<long long> prior_hops;
                if (existing) prior_hops = existing->hops;

                const Json* polarity = event.payload.find("asserter_polarity");
                std::string asserter = polarity && polarity->truthy()
                    ? polarity->py_str() : prop->polarity;
                Json where = event.location.truthy() ? event.location : agent.location();
                double skepticism = std::max(0.0, std::min(1.0,
                    agent.skepticism()
                    + climate.modifiers(where.py_str()).at("skepticism").as_double()));

                std::vector<Reason> br = belief.update(
                    agent.beliefs, *prop, asserter, eff_trust, competence, skepticism,
                    Json("clm_" + std::to_string(event.event_id)), origin,
                    w.world_time, speaker.empty() ? Json() : Json(speaker));
                for (const Reason& reason : br) rt.push_back(reason);

                Belief* held = agent.beliefs.find(prop->core_key());
                formed = held;
                if (held) {
                    // Social distance from a first-hand source: always the
                    // SHORTEST path known. Witnessing something, or hearing it
                    // on a channel, is first-hand. A retold claim carries the
                    // teller's hop count, and taking the minimum is what stops a
                    // rumour echoing back to its own witness from relocating
                    // them away from what they saw.
                    const Json* spread = event.payload.find("diffusion");
                    const Json* relayed = (spread && spread->kind() == Json::Kind::Object)
                        ? spread->find("hops") : nullptr;
                    if (!relayed || relayed->is_null()) held->hops = 0;
                    else if (!prior_hops) held->hops = relayed->as_int();
                    else held->hops = std::min(*prior_hops, relayed->as_int());
                }
            }

            if (prop) took_in.emplace_back(obs.observer, obs.quality);

            // WHAT THEY NOW THINK OF WHOEVER DID IT. Driven by the belief just
            // formed rather than by being in the room, which is what makes this
            // more than a reputation counter: the same line runs for somebody
            // who watched and for somebody who was merely told, and the second
            // moves less because they believe it less.
            //
            // The `standing.enabled()` half of this test is REDUNDANT and is
            // not catchable: `judge` refuses on its own when the layer is off,
            // and applying an empty delta list is a no-op. It stays because it
            // is in the Python, and because reading the guard here is how a
            // reader learns that this whole block is optional.
            if (standing.enabled() && prop && formed) {
                auto judged = standing.judge(agent, *prop, formed->expected_prob());
                if (!judged.first.empty()) {
                    std::vector<ProposedDelta> to_relationship, to_reputation;
                    for (const ProposedDelta& delta : judged.first) {
                        if (delta.key.module == "relationship") to_relationship.push_back(delta);
                        if (delta.key.module == "reputation") to_reputation.push_back(delta);
                    }
                    relationship.apply(agent, to_relationship, rt);
                    reputation.apply(agent, to_reputation, rt);
                    for (const Reason& reason : judged.second) rt.push_back(reason);
                }
            }

            // WHAT THEY LOOK LIKE TO THIS PERSON. A pure function of the tokens
            // and of what this observer is authored to be taken with, so writing
            // it on every perception is idempotent and costs nothing when no pack
            // authors `drawn_to` -- which is every pack.
            if (event.actor.truthy() && event.actor.py_str() != agent.id) {
                const Agent* seen = w.agents.find(event.actor.py_str());
                if (seen) {
                    double pull = appearance.drawn_to(&agent, *seen);
                    if (pull != 0.0) {
                        OrderedMap<double>& rel = agent.relationships[event.actor.py_str()];
                        const double* current = rel.find("attraction");
                        if (!current || *current != pull) {
                            rel["attraction"] = pull;
                            Json why = Json::object();
                            why["observer"] = agent.id;
                            why["to"] = event.actor;
                            why["note"] = std::string(
                                "authored, not decided here: this character is "
                                "taken with how that one looks");
                            rt.push_back({"appearance.drawn_to", py_round(pull, 4), why});
                        }
                    }
                }
            }

            // WHEN ONE OF YOURS IS HURT.
            for (const Reason& reason : identity_threat(agent, event))
                rt.push_back(reason);

            // Memory encoding.
            ++mem_counter_;
            const Json& appraisal = event.appraisal();
            double valence = 0.0;
            if (appraisal.truthy()) {
                const Json* desirability = appraisal.find("desirability");
                if (desirability) valence = desirability->as_double();
            }
            auto item = std::make_shared<MemoryItem>();
            item->memory_id = "mem_" + std::to_string(event.event_id) + "_" + obs.observer;
            item->owner = agent.id;
            item->type = event.type == "promise" ? "commitment" : "episodic";
            const Json* summary = event.payload.find("summary");
            item->content = (summary && summary->truthy())
                ? summary->py_str()
                : event.type + " by " + event.actor.py_str();
            // WHAT THEY UNDERSTOOD, NOT WHAT HAPPENED. This used to store the
            // event's own proposition, so a character who demonstrably could not
            // identify what they saw still had the full, precise claim in an
            // episodic memory the API hands out -- belief and recall disagreeing
            // about the same moment. A question is the exception: it names a
            // proposition without asserting it, and being asked about something
            // is what makes it retrievable later.
            item->proposition = event.type == "question" ? event.proposition() : prop;
            const Json* importance = event.payload.find("importance");
            item->importance = importance ? importance->as_double() : 0.5;
            item->emotional_valence = valence;
            item->source_conf = obs.quality;
            for (const Reason& reason : memory.encode(agent.memory, item, w.world_time))
                rt.push_back(reason);

            // Appraisal -> emotion -> PAD. The RETURN value is the list of
            // emotions that fired; the reason rows come out of the optional
            // parameter, and taking the return value for the trace put the raw
            // emotion names into it instead of `affect.emotion_fired`.
            affect.update(agent.affect, appraisal, dt, &rt);

            traces[agent.id] = rt;
        }

        // WHAT THE PERSON WHO DID IT TAKES FROM HAVING DONE IT. The actor
        // perceives nothing here -- they are excluded from their own event --
        // but they know what they did, and that is the only honest basis a
        // character has for guessing whether the next threat will land.
        if (is_witnessed_act(event.type) && !event.actor.is_null()) {
            Agent* actor = w.agents.find(event.actor.py_str());
            const Json* target_id = event.payload.find("target");
            if (actor != nullptr && target_id != nullptr && !target_id->is_null()) {
                const Json* severity = event.payload.find("severity");
                for (const Reason& reason : tom.note_own_act(
                        *actor, target_id->py_str(), event.type,
                        severity ? severity->as_double() : 0.5))
                    traces[actor->id].push_back(reason);
            }
        }

        // Did this happen in front of enough people, in the open, that it is no
        // longer deniable? Asked once per event and AFTER the fact, on the set
        // of people the perception layer says actually took it in.
        for (const Reason& reason : common_knowledge.observe(w, event, took_in))
            traces["_common_knowledge"].push_back(reason);

        // An undertaking becomes something that will be checked. The same
        // witness set, for the same reason.
        std::vector<std::string> heard;
        for (const auto& row : took_in) heard.push_back(row.first);
        for (const Reason& reason : promises.record(w, event, heard))
            traces["_promises"].push_back(reason);

        // WITHIN A TICK, REASONS ACCUMULATE. This used to be a plain assignment,
        // which quietly threw away everything an earlier event in the same time
        // advance had produced -- and a time advance fires many. Measured on
        // `market-square`: a week reported `climate.moved: 0` while the layer
        // demonstrably worked, because those reasons are emitted per event and
        // the next event erased them.
        //
        // A single `process_event` still REPLACES, because "what did this event
        // cause" is the right answer there and accumulating across separate
        // calls would grow without bound.
        if (!collecting_) last_traces = traces;
        else collect(traces);
        return traces;
    }

    // ----------------------------------------------------------- time advance --

    /// Advance the world by `delta` minutes.
    ///
    /// Tick order matters and is deliberate: scheduled events, then the cast
    /// goes about its day, then social activity, then the effect of elapsed time
    /// on every agent, then the macro layer.
    ///
    /// Diffusion must come BEFORE decay, not after: a retelling creates
    /// memories, and memory caps are enforced during consolidation. Running it
    /// afterwards left the tick ending over the cap -- the bound held only until
    /// the next tick, which is not a bound.
    void advance_time(long long delta) {
        // One answer for the whole tick, not for whichever event happened last.
        last_traces = TraceMap();
        dropped_traces_ = OrderedMap<long long>();
        collecting_ = true;
        advance(delta);
        collecting_ = false;
        std::vector<std::string> keys;
        for (const auto& entry : dropped_traces_) keys.push_back(entry.first);
        std::sort(keys.begin(), keys.end());
        for (const std::string& key : keys) {
            long long dropped = *dropped_traces_.find(key);
            Json why = Json::object();
            why["bucket"] = key;
            why["dropped"] = dropped;
            why["kept"] = MAX_TRACE_ENTRIES_PER_KEY;
            why["note"] = std::string("more reasons this tick than one bucket "
                                      "keeps; the count is exact");
            last_traces[key].push_back(
                {"trace.truncated", static_cast<double>(dropped), why});
        }
    }

    /// Player speech as a claim event.
    TraceMap player_says(const std::string& speaker_id, const Json& location,
                         const Proposition& proposition, const Json& summary = Json(),
                         const Json& appraisal = Json::object(),
                         double importance = 0.5,
                         const std::string& domain = "street") {
        Event ev;
        ev.event_id = world.new_event_id();
        ev.world_time = world.world_time;
        ev.type = "claim";
        ev.actor = speaker_id;
        ev.location = location;
        Json payload = Json::object();
        payload["proposition"] = proposition.as_json();
        payload["summary"] = summary;
        payload["appraisal"] = appraisal;
        payload["importance"] = importance;
        payload["domain"] = domain;
        ev.payload = payload;
        return process_event(ev);
    }

    /// Apply what the engine says happened, and nothing else.
    ///
    /// The runtime is not the authority on whether a character crossed a room --
    /// the engine is, because the engine is what the player watched. So this
    /// applies the effect on SUCCEEDED and, on every other result, records that
    /// the intent did not happen and leaves the character where the player last
    /// saw them. That is the whole point of the exchange: the two worlds agree,
    /// including when they agree that nothing moved.
    Json resolve_action(const std::string& intent_id, const std::string& status,
                        const std::string& detail = "") {
        ResolvedIntent record = actions_out.resolve(intent_id, status,
                                                    world.world_time, detail);
        const ActionIntent& intent = record.intent;
        Agent* agent = world.agents.find(intent.actor);
        Json why = Json::object();
        why["intent"] = intent.intent_id;
        why["actor"] = intent.actor;
        why["type"] = intent.type;
        why["status"] = record.status;
        why["detail"] = record.detail;
        std::vector<Reason> reasons = {
            {"action.resolved", record.applied ? 1.0 : 0.0, why}};
        if (record.applied && intent.type == "MOVE_TO" && agent) {
            const Json* activity = intent.params.find("activity");
            for (const Reason& reason : routine.perform_move(
                     world, *agent, intent.params.at("place").py_str(),
                     activity ? activity->py_str() : std::string(), std::nullopt,
                     on_arrival(), carried_mood()))
                reasons.push_back(reason);
        }
        for (const Reason& reason : reasons) last_traces["_actions"].push_back(reason);
        Json out = Json::object();
        out["intent"] = intent.as_json();
        out["status"] = record.status;
        out["applied"] = record.applied;
        Json rows = Json::array();
        for (const Reason& reason : reasons) rows.push(reason.as_json());
        out["reasons"] = rows;
        return out;
    }

    /// The context every decision, style and threat check is made against.
    Json context(Agent& agent, const std::string& interlocutor = "") {
        const Json* place = world.places.find(agent.location().py_str());
        Json ctx = Json::object();
        // `threat_by_identity` was never passed, so the identity engine's threat
        // term -- a full quarter of what decides which identity is salient -- was
        // multiplied by zero in every world since it was written.
        Json fits = Json::object();
        fits["comparative_fit"] = Json::object();
        fits["normative_fit"] = Json::object();
        std::string salient = identity.salience(agent, fits, agent.identity_threat);
        long long audience = 0;
        for (const auto& other : world.agents)
            if (other.first != agent.id
                && other.second.location().py_str() == agent.location().py_str())
                ++audience;
        const Json* surveillance = place ? place->find("surveillance_level") : nullptr;
        ctx["interlocutor"] = interlocutor.empty() ? Json() : Json(interlocutor);
        ctx["place"] = agent.location();
        ctx["surveillance_level"] = surveillance ? surveillance->as_double() : 0.0;
        ctx["audience_size"] = audience;
        ctx["salient_identity"] = salient;
        ctx["salience"] = agent.identity_salience.get(salient, 0.0);
        ctx["authority_legitimacy"] = 0.5;
        bool formal_role = false;
        for (const Json& role : agent.roles) {
            const Json* name = role.find("role");
            if (!name) continue;
            std::string which = name->py_str();
            if (which == "role:bartender" || which == "role:officer") formal_role = true;
        }
        ctx["public_role_formal"] = formal_role;
        ctx["player_owes"] = interlocutor_owes(agent, interlocutor);
        return ctx;
    }

    /// How this character speaks to this person, in one place.
    ///
    /// There were three call sites computing this, and adding fear and respect
    /// to one of them changed the register in a scene driven through `decide`
    /// and left it untouched in the two paths a game actually hits most.
    ///
    /// `regard` is passed only with the standing layer ON: without it fear and
    /// respect never move, so it would be a constant -- and a constant that
    /// perturbs every line of dialogue is what "off is byte-identical" forbids.
    StyleVector style_for(const Agent& agent, const std::string& interlocutor) const {
        const OrderedMap<double>* regard = nullptr;
        if (standing.enabled() && !interlocutor.empty())
            regard = agent.relationships.find(interlocutor);
        return socioling.compute_style(agent, interlocutor, agent.location(), &world,
                                       regard, &world.appearance_reactions, &appearance,
                                       true);
    }

    struct Decision {
        ActionCandidate chosen;
        std::vector<ActionCandidate> scored;
        std::vector<Reason> reasons;
    };

    /// Score the action catalogue and select one, with full reason codes.
    ///
    /// `situation` may carry {injured, threatened, threat_severity} for the
    /// reactive rules.
    Decision decide(const std::string& agent_id, const std::string& interlocutor = "",
                    const Json& situation = Json()) {
        Agent& agent = *world.agents.find(agent_id);
        Json ctx = context(agent, interlocutor);
        if (situation.kind() == Json::Kind::Object)
            for (const auto& entry : situation.fields()) ctx[entry.first] = entry.second;
        std::string salient = ctx.at("salient_identity").py_str();
        OrderedMap<double> active_vals =
            value.active_values(agent, salient, world.identity_values);

        // Weights: personality plus the salient identity.
        OrderedMap<double> weights;
        weights["exchange"] = 1.0 + 0.5 * agent.big_five.get("agreeableness", 0.5);
        weights["norm"] = 1.0 + 0.6 * agent.big_five.get("conscientiousness", 0.5);
        weights["relationship"] = 1.0 + 0.5 * agent.big_five.get("agreeableness", 0.5);
        weights["safety"] = 1.0 + 0.6 * active_vals.get("security", 0.4);
        weights["income"] = 1.0;
        weights["face"] = impression.weight(ctx);
        weights["tom"] = 1.0;

        std::vector<ActionDefinition> candidates = default_candidates(ctx);

        // Reactive context and rules: a trigger preempts deliberation.
        long long eid = world.new_event_id();
        std::optional<Mobilization> backup =
            mobilization_candidate(agent, world, 1.0, eid);
        Json rctx = ctx;
        rctx["has_backup"] = backup.has_value();
        std::vector<Reason> reactive_reasons;
        std::vector<ReactiveRule> fired =
            fire_reactive_rules(agent, rctx, reactive_rules, &reactive_reasons);

        std::string forced_action_id;
        double forced_priority = 0.0;
        if (!fired.empty()) {
            // `max(fired, key=priority)` -- the FIRST of a tie, because Python's
            // max keeps the earliest maximum.
            const ReactiveRule* top = &fired.front();
            for (const ReactiveRule& rule : fired)
                if (rule.priority > top->priority) top = &rule;
            forced_action_id = top->action_id;
            forced_priority = top->priority;
            Json why = Json::object();
            why["rule"] = top->rule_id;
            why["action"] = top->action_id;
            why["reason"] = top->reason;
            reactive_reasons.push_back({"agency.reactive_fired", top->priority, why});
            // Make sure the triggered action exists as a candidate.
            bool present = false;
            for (const ActionDefinition& one : candidates)
                if (one.action_id == forced_action_id) present = true;
            if (forced_action_id == "mobilize_allies" && backup)
                candidates.push_back(backup->action);
            else if (forced_action_id == "flee" && !present) {
                ActionDefinition flee;
                flee.action_id = "flee";
                flee.action_class = "flee";
                flee.target = interlocutor.empty() ? Json() : Json(interlocutor);
                flee.is_dialogue = false;
                ActionOutcome escape;
                escape.dimension = "safety";
                escape.delta = 0.5;
                escape.probability = 0.8;
                escape.source = "escape";
                flee.outcomes.push_back(escape);
                candidates.push_back(flee);
            }
        }

        // Budget to risk: set the prospect reference point from liquid resources.
        if (policy.params().use_prospect) {
            double ref = risk_reference_point(agent);
            for (ActionDefinition& one : candidates)
                for (ActionOutcome& outcome : one.outcomes)
                    outcome.reference_point = ref;
            Json why = Json::object();
            why["interpretation"] =
                std::string("below->risk-seeking, above->risk-averse");
            reactive_reasons.push_back({"agency.risk_reference", py_round(ref, 3), why});
        }

        auto term_providers = [&](const ActionDefinition& action) {
            std::vector<std::pair<std::string, double>> terms;
            for (const auto& t : exchange.value_terms(action, ctx)) terms.push_back(t);
            for (const auto& t : norm.value_terms(action, ctx)) terms.push_back(t);
            for (const auto& t : impression.value_terms(action, ctx)) terms.push_back(t);
            if (!interlocutor.empty())
                terms.push_back(tom.expected_reaction(agent, interlocutor,
                                                      action.action_class));
            return terms;
        };

        /// Pushes rather than opinions -- see `PolicyEngine::score`.
        auto bias_providers = [&](const ActionDefinition& action) {
            if (interlocutor.empty()) return 0.0;
            // What they think of you, as a reason to answer or to turn away.
            // Zero unless the standing layer is on, so a world that declines this
            // mechanic decides exactly as it did before.
            double pushed = standing.bias_for(agent, action, interlocutor);
            // And what you LOOK like, which is a different question and is kept a
            // different one: standing is what you have DONE.
            pushed += appearance.bias_for(&agent, action,
                                          world.agents.find(interlocutor),
                                          world.appearance_reactions);
            return pushed;
        };

        OrderedMap<double> tendencies = affect.action_tendencies(agent.affect);
        std::vector<ActionCandidate> scored = policy.score(
            candidates, weights, term_providers, tendencies, bias_providers, true);

        DecidingAgent decider;
        decider.id = agent.id;
        decider.global_seed = tagged_seed_;
        decider.big_five = agent.big_five;
        decider.affect = &agent.affect;

        // A fired reactive rule adds a priority floor and makes selection
        // near-deterministic.
        double saved_temperature = policy.params().temperature;
        if (!forced_action_id.empty()) {
            for (ActionCandidate& one : scored)
                if (one.action.action_id == forced_action_id) {
                    one.utility += forced_priority;
                    one.contributions.emplace_back("reactive_priority",
                                                   py_round(forced_priority, 3), 1.0,
                                                   py_round(forced_priority, 3));
                }
            std::stable_sort(scored.begin(), scored.end(),
                             [](const ActionCandidate& a, const ActionCandidate& b) {
                                 return a.utility > b.utility;
                             });
            policy.params().temperature = 0.05;
        }
        Decision out;
        try {
            auto picked = policy.select(decider, scored, eid, world.world_time);
            out.chosen = picked.first;
            out.reasons = picked.second;
        } catch (...) {
            // Without this, an exception during selection left the temperature
            // pinned at 0.05 for the rest of the process, quietly turning every
            // later decision near-deterministic.
            policy.params().temperature = saved_temperature;
            throw;
        }
        policy.params().temperature = saved_temperature;

        std::vector<Reason> reasons = reactive_reasons;
        for (const Reason& reason : out.reasons) reasons.push_back(reason);
        out.reasons = reasons;
        out.scored = scored;
        last_traces[agent_id] = reasons;
        return out;
    }

    struct Mobilized {
        std::vector<AllyResponse> responders;
        std::vector<Reason> reasons;
    };

    /// Resolve who responds and schedule their arrivals.
    Mobilized mobilize(const std::string& caller_id, double urgency = 1.0) {
        Agent& caller = *world.agents.find(caller_id);
        long long eid = world.new_event_id();
        std::optional<Mobilization> backup =
            mobilization_candidate(caller, world, urgency, eid);
        Mobilized out;
        if (!backup) {
            out.reasons.push_back({"agency.no_allies", 0.0, Json::object()});
            return out;
        }
        for (const AllyResponse& r : backup->responses) {
            Json why = Json::object();
            why["ally"] = r.ally_id;
            why["p"] = r.probability;
            why["latency"] = r.latency;
            why["outcome"] = std::string(r.will_come ? "will_come" : "declines");
            out.reasons.push_back({"agency.ally_response", r.probability, why});
            if (!r.will_come) continue;
            out.responders.push_back(r);
            Event arrive;
            arrive.event_id = world.new_event_id();
            arrive.world_time = world.world_time + r.latency;
            arrive.type = "ally_arrives";
            arrive.actor = r.ally_id;
            arrive.location = caller.location();
            Json payload = Json::object();
            payload["summary"] = r.ally_id + " arrives to back up " + caller_id;
            payload["caller"] = caller_id;
            arrive.payload = payload;
            world.scenario_events.push_back(arrive);
        }
        last_traces[caller_id] = out.reasons;
        return out;
    }

    struct Spoken {
        std::string text;
        std::string act;
        /// The plan's style, which is the ROUNDED dictionary and not the vector
        /// it came from -- that is what Python returns and what the realizer read.
        Json style;
        double utility = 0.0;
        std::string verdict;
        std::string salient_identity;
        std::vector<Reason> reasons;
    };

    /// Plan, realize, validate. Buffered generation: nothing unvalidated leaves.
    Spoken say(const std::string& agent_id, const std::string& interlocutor = "",
               const std::string& conv_id = "") {
        Agent& agent = *world.agents.find(agent_id);
        Decision decision = decide(agent_id, interlocutor);
        std::vector<Reason> dreasons = decision.reasons;
        Json ctx = context(agent, interlocutor);

        std::string key = conv_id.empty()
            ? "conv_" + agent_id + "_" + interlocutor : conv_id;
        if (!conversations.contains(key)) {
            ConversationState fresh;
            fresh.conv_id = conv_id.empty() ? "conv" : conv_id;
            fresh.participants = {agent_id, interlocutor};
            conversations[key] = fresh;
        }
        ConversationState& conv = *conversations.find(key);

        StyleVector style = style_for(agent, interlocutor);
        // `agent.goals[0]["content"] if agent.goals else "interact"`.
        std::string goal = "interact";
        if (!agent.goals.empty()) {
            const Json* content = agent.goals.front().find("content");
            if (content) goal = content->py_str();
        }
        DialoguePlan plan = planner.plan(agent, conv, decision.chosen, interlocutor,
                                         style, goal, world.global_seed,
                                         world.world_time);
        plan.request_id = "say:" + agent.id + ":" + std::to_string(world.world_time)
                        + ":" + std::to_string(conv.turn_count);

        std::vector<std::string> recent = conv.recent_lines;
        std::string text;
        std::string verdict;
        bool released = false;
        for (int attempt = 0; attempt < 2 && !released; ++attempt) {
            // Text we produced ourselves needs no canon parse-back. The
            // deterministic realizer never throws, so the provider-failure branch
            // Python carries has nothing to catch here -- an external provider
            // lives on the host side of the C ABI, and this is where its answer
            // would arrive.
            text = realizer.realize(plan, StyleVector::from_json(plan.style));
            std::string off = CANON_OFF;
            ValidationResult res = validator.check(text, plan, agent, recent, &off);
            verdict = res.verdict;
            for (const Json& reason : res.reasons) dreasons.push_back(as_reason(reason));
            // Same distinction as the answer path: a repetition is a QUALITY
            // objection and must not decide whether a commitment reaches the
            // world. Only an unsafe line sends the turn to a deflection.
            if (verdict != ACCEPT && !is_unsafe(res)) {
                bool reworded = false;
                for (const std::string& spare : fallback_realizer.variants(
                         plan, StyleVector::from_json(plan.style))) {
                    if (spare == text) continue;
                    ValidationResult retry =
                        validator.check(spare, plan, agent, recent, &off);
                    if (retry.verdict == ACCEPT) {
                        Json why = Json::object();
                        why["was"] = text;
                        why["now"] = spare;
                        dreasons.push_back({"dialogue.reworded", 1.0, why});
                        text = spare;
                        verdict = retry.verdict;
                        reworded = true;
                        break;
                    }
                }
                // Python's `for ... else`: no complete alternative wording, so the
                // line is released as it stands and the commitment survives.
                if (!reworded) {
                    Json why = Json::object();
                    why["verdict"] = verdict;
                    why["note"] = std::string("a quality objection, not a safety one");
                    dreasons.push_back({"dialogue.released_anyway", 1.0, why});
                    verdict = ACCEPT;
                }
            }
            if (verdict == ACCEPT) { released = true; break; }
            // Fall back to a safe deflection template -- and drop the authored
            // phrasing, or `lookup` returns it again and the deflection is a
            // no-op wearing a different act name.
            if (verdict == REJECT_HARD) {
                plan.dialogue_act = plan.fallback_template_id;
                plan.phrasing = Json::object();
            }
        }
        if (!released) {
            DialoguePlan safe;
            safe.speaker = agent.id;
            safe.addressee = interlocutor;
            safe.dialogue_act = "deflect";
            safe.goal = goal;
            safe.style = plan.style;
            plan = safe;
            text = fallback_realizer.realize(plan, StyleVector::from_json(plan.style));
            std::string off = CANON_OFF;
            ValidationResult res = validator.check(text, plan, agent, recent, &off);
            verdict = res.verdict;
            for (const Json& reason : res.reasons) dreasons.push_back(as_reason(reason));
        }

        conv.recent_lines.push_back(text);
        // `del conv.recent_lines[:-5]` -- a shared, bounded anti-repeat window.
        if (conv.recent_lines.size() > 5)
            conv.recent_lines.erase(conv.recent_lines.begin(),
                                    conv.recent_lines.end() - 5);
        last_traces[agent_id] = dreasons;

        Spoken out;
        out.text = text;
        out.act = plan.dialogue_act;
        out.style = plan.style;
        out.utility = py_round(decision.chosen.utility, 3);
        out.verdict = verdict;
        out.salient_identity = ctx.at("salient_identity").py_str();
        out.reasons = dreasons;
        return out;
    }

    /// Population LOD: apply a dormant agent's deferred decay up to now.
    ///
    /// Public because the SDK calls it before a character speaks or reacts --
    /// mood-congruent retrieval and an emotional reaction both need a current
    /// mood, and a dormant character has not been decayed since anyone last
    /// looked at them.
    void catch_up(Agent& agent) { catch_up_(agent); }

    const OrderedMap<long long>& last_decay() const { return last_decay_; }
    OrderedMap<long long>& last_decay() { return last_decay_; }

private:
    /// The validator emits Python TUPLES; everything else here emits a Reason.
    static Reason as_reason(const Json& row) {
        const std::vector<Json>& parts = row.items();
        return Reason{parts.at(0).py_str(), parts.at(1).as_double(), parts.at(2)};
    }

    static bool is_witnessed_act(const std::string& type) {
        const auto& acts = witnessed_acts();
        return std::find(acts.begin(), acts.end(), type) != acts.end();
    }

    static double appraisal_number(const Event& event, const char* field,
                                   double fallback) {
        const Json& appraisal = event.appraisal();
        const Json* found = appraisal.find(field);
        return found ? found->as_double() : fallback;
    }

    /// Merge one event's reasons into the answer for the whole tick.
    ///
    /// ONLY THE LAYER BUCKETS ACCUMULATE. The `_`-prefixed keys are what a
    /// caller reads to find out what happened during a time advance, and they
    /// were the ones being erased by whichever event came last. The per-agent
    /// buckets answer a different question -- what did THIS event do to this
    /// character -- and have always answered for the most recent one.
    void collect(const TraceMap& traces) {
        for (const auto& entry : traces) {
            if (entry.first.empty() || entry.first[0] != '_') {
                last_traces[entry.first] = entry.second;
                continue;
            }
            std::vector<Reason>& bucket = last_traces[entry.first];
            long long room = MAX_TRACE_ENTRIES_PER_KEY
                           - static_cast<long long>(bucket.size());
            if (room > 0) {
                std::size_t take = std::min(static_cast<std::size_t>(room),
                                            entry.second.size());
                bucket.insert(bucket.end(), entry.second.begin(),
                              entry.second.begin() + static_cast<long>(take));
            }
            long long dropped = static_cast<long long>(entry.second.size())
                              - std::max(0LL, room);
            if (dropped > 0)
                dropped_traces_[entry.first] = dropped_traces_.get(entry.first, 0)
                                             + dropped;
        }
    }

    /// `(multiplier, reason)` -- how far this observer credits this source.
    ///
    /// Looked up MOST SPECIFIC FIRST, and the first hit wins rather than
    /// multiplying: a character who distrusts City Radio specifically should not
    /// also be charged for distrusting radio in general.
    double source_credence(const Agent& observer, const Event& event,
                           const Observation& obs, const World& w,
                           std::optional<Reason>& why) const {
        const Json* table = observer.epistemic.find("source_trust");
        if (!table || !table->truthy()) return 1.0;

        std::vector<std::string> keys;
        const Json* channel = event.payload.find("channel");
        if (event.type == "broadcast" && channel && channel->truthy()) {
            keys.push_back(channel->py_str());
            const Json* declared = w.channels.find(channel->py_str());
            const Json* kind = declared ? declared->find("type") : nullptr;
            if (kind && kind->truthy()) keys.push_back(kind->py_str());
            keys.push_back("broadcast");
        } else if (obs.modality == "media") {
            keys.push_back("broadcast");
        } else if (is_witnessed_act(event.type) || !event.actor.truthy()) {
            keys.push_back("witnessed");
        } else {
            const Agent* speaker = w.agents.find(event.actor.py_str());
            if (speaker) for (const Json& role : speaker->roles) {
                Json name = role.kind() == Json::Kind::Object ? role.get("role") : role;
                if (name.truthy()) keys.push_back(name.py_str());
            }
            keys.push_back("told");
        }

        for (const std::string& key : keys) {
            const Json* found = table->find(key);
            if (!found) continue;
            double value = std::max(0.0, std::min(2.0, found->as_double()));
            Json detail = Json::object();
            detail["observer"] = observer.id;
            detail["matched"] = key;
            Json tried = Json::array();
            for (const std::string& one : keys) tried.push(one);
            detail["tried"] = tried;
            detail["note"] = std::string("how far this person credits this kind "
                                         "of source");
            why = Reason{"belief.source_credence", py_round(value, 3), detail};
            return value;
        }
        return 1.0;
    }

    /// Did this happen to one of ours?
    ///
    /// Attacking a keeper makes every other keeper's belonging suddenly matter.
    /// The engine that models it sat unreachable in the runtime for as long as it
    /// existed, because it asked the EVENT which identity was threatened and no
    /// event ever said: whether something threatens YOUR belonging depends on who
    /// you are, so it can only be decided per observer, here.
    std::vector<Reason> identity_threat(Agent& observer, const Event& event) {
        const auto& types = identity_threat_events();
        if (std::find(types.begin(), types.end(), event.type) == types.end()) return {};
        const Json* target_id = event.payload.find("target");
        const Agent* target = (target_id && target_id->truthy())
            ? world.agents.find(target_id->py_str()) : nullptr;
        // Being attacked yourself is handled by every other layer in the
        // runtime. This one is only about the people watching.
        if (!target || target->id == observer.id) return {};

        std::set<std::string> mine, theirs;
        for (const Json& one : observer.identities) {
            const Json* id = one.find("id");
            if (id && id->truthy()) mine.insert(id->py_str());
        }
        for (const Json& one : target->identities) {
            const Json* id = one.find("id");
            if (id && id->truthy()) theirs.insert(id->py_str());
        }
        std::vector<std::string> shared;
        for (const std::string& one : mine) if (theirs.count(one)) shared.push_back(one);
        if (shared.empty()) return {};

        std::vector<Reason> reasons;
        for (const std::string& identity_id : shared) {
            // Python passes `self._context(observer)` here and the engine never
            // reads it. Building it is not free, though: `context()` computes
            // identity salience and WRITES THE DISTRIBUTION onto the agent, so
            // dropping the unused argument silently left every bystander's
            // salience unset. Kept for the side effect, and said out loud
            // because an argument nobody reads is exactly what a reader would
            // delete next.
            context(observer);
            SocialIdentityEngine::Outcome outcome =
                social_identity.on_event(observer, event, identity_id);
            for (const ProposedDelta& proposal : outcome.proposals) {
                double current = observer.identity_threat.get(identity_id, 0.0);
                const Json* severity = event.payload.find("severity");
                double how_bad = severity ? severity->as_double() : 0.5;
                double raised = std::min(1.0, current + proposal.amount * how_bad);
                observer.identity_threat[identity_id] = raised;
                Json why = Json::object();
                why["observer"] = observer.id;
                why["identity"] = identity_id;
                why["because"] = target->id;
                why["event"] = event.type;
                why["was"] = py_round(current, 4);
                why["note"] = std::string("somebody who shares this belonging "
                                          "was attacked");
                reasons.push_back({"identity.threatened", py_round(raised, 4), why});
            }
            if (outcome.appraisal_boost.truthy()) {
                // The appraisal the engine returns is the GROUP-BASED emotion:
                // this is felt as an offence against you, by the person who did
                // it, even though it did not happen to you.
                affect.update(observer.affect, outcome.appraisal_boost, 1.0, &reasons);
            }
        }
        return reasons;
    }

    /// Time spent in the same room, before anybody moves on.
    ///
    /// Run BEFORE routines, so the hours just elapsed are credited to where
    /// people actually spent them rather than to where they are about to go.
    /// Symmetric: knowing somebody is not one-sided.
    void grow_familiarity(long long dt_minutes) {
        double hours = std::max(0.0, static_cast<double>(dt_minutes) / 60.0);
        if (hours <= 0.0) return;
        double share = 1.0 - std::pow(1.0 - FAMILIARITY_PER_HOUR, hours);
        if (share <= 0.0) return;
        OrderedMap<std::vector<Agent*>> by_place;
        for (auto& entry : world.agents)
            if (entry.second.location().truthy())
                by_place[entry.second.location().py_str()].push_back(&entry.second);
        for (auto& bucket : by_place) {
            if (bucket.second.size() < 2) continue;
            for (Agent* one : bucket.second) {
                for (Agent* other : bucket.second) {
                    if (one == other) continue;
                    OrderedMap<double>& rel = one->relationships[other->id];
                    double known = rel.get("familiarity", 0.0);
                    if (known < 0.999)
                        rel["familiarity"] = std::min(1.0, known + share * (1.0 - known));
                }
            }
        }
    }

    void fade_identity_threat(Agent& agent, long long dt_minutes) {
        if (agent.identity_threat.empty() || dt_minutes <= 0) return;
        double keep = std::pow(0.5, (static_cast<double>(dt_minutes) / 60.0)
                                        / IDENTITY_THREAT_HALF_LIFE_HOURS);
        std::vector<std::string> ids;
        for (const auto& entry : agent.identity_threat) ids.push_back(entry.first);
        for (const std::string& id : ids) {
            double faded = *agent.identity_threat.find(id) * keep;
            if (faded < 0.01) agent.identity_threat.erase(id);
            else agent.identity_threat[id] = faded;
        }
    }

    /// Population LOD: apply deferred decay for a dormant agent up to now.
    ///
    /// EXACT, not lossy. Mood relaxes and emotions decay by exp(-dt/tau), and
    /// exp is composable, so one catch-up over the full elapsed dt yields the
    /// same state as having decayed every tick. A no-op when LOD is off.
    void catch_up_(Agent& agent) {
        if (!population_lod) return;
        long long last = last_decay_.get(agent.id, world.world_time);
        long long dt = world.world_time - last;
        if (dt > 0) {
            affect.decay(agent.affect, dt);
            fade_identity_threat(agent, dt);
            memory.decay_and_consolidate(agent.memory, world.world_time);
        }
        last_decay_[agent.id] = world.world_time;
    }

    bool interlocutor_owes(const Agent& agent, const std::string& interlocutor) const {
        if (interlocutor.empty()) return false;
        for (const auto& entry : agent.beliefs) {
            const Proposition& prop = entry.second.proposition;
            if (prop.predicate != "economy:owes_amount") continue;
            const Json* debtor = prop.slots.find("debtor");
            const Json* creditor = prop.slots.find("creditor");
            if (debtor && debtor->py_str() == interlocutor
                && creditor && creditor->py_str() == agent.id)
                return entry.second.expected_prob() >= 0.5;
        }
        return false;
    }

    /// What a move tells the rest of the runtime.
    ///
    /// The routine engine hands over WHO moved, where to, where from and what
    /// they are doing, and leaves it to the caller to build an event out of it:
    /// the module that relocates a character has no ledger and should not own
    /// one. This is that ledger.
    RoutineEngine::RequestMove request_move() {
        return [this](const Agent& who, const std::string& place,
                      const std::string& origin, const std::string& activity,
                      long long start) {
            RoutineEngine::MoveRequest out;
            if (!actions_out.enabled) return out;
            out.bridged = true;
            if (actions_out.has_pending(who.id, "MOVE_TO")) return out;
            Json params = Json::object();
            params["place"] = place;
            params["from"] = origin;
            params["activity"] = activity;
            std::string reason = "routine block " + clock_string(start)
                               + (activity.empty() ? "" : " (" + activity + ")");
            out.issued = true;
            out.intent_id = actions_out.issue(who.id, "MOVE_TO", params, reason,
                                              world.world_time).intent_id;
            return out;
        };
    }

    RoutineEngine::CarriedMood carried_mood() {
        return [this](const std::string& from, const std::string& to) {
            return climate.carried(from, to);
        };
    }

    RoutineEngine::OnArrival on_arrival() {
        return [this](const Agent& who, const std::string& place,
                      const std::string& origin, const std::string& activity) {
            Event ev;
            ev.event_id = world.new_event_id();
            ev.world_time = world.world_time;
            ev.type = "move";
            ev.actor = who.id;
            ev.location = place;
            Json payload = Json::object();
            // `agent.public_name or agent.id` -- truthiness, so a character with
            // no public name is announced by their id rather than by nothing.
            payload["summary"] = (who.public_name.truthy() ? who.public_name.py_str()
                                                           : who.id)
                               + " arrives"
                               + (activity.empty() ? "" : " to " + activity);
            payload["importance"] = routine.params().arrival_importance;
            Json where = Json::object();
            where["from"] = origin;
            where["activity"] = activity;
            payload["routine"] = where;
            ev.payload = payload;
            this->process_event(ev);
        };
    }

    DiffusionRuntime diffusion_runtime() {
        DiffusionRuntime bridge;
        bridge.network = network;
        bridge.process_event = [this](const Event& event) { this->process_event(event); };
        bridge.climate_modifiers = [this](const std::string& place) {
            return climate.modifiers(place);
        };
        bridge.is_common = [this](const std::string& key, const std::string& a,
                                  const std::string& b) {
            return common_knowledge.is_common(key, {a, b});
        };
        bridge.contagion = [this](Agent& speaker, Agent& listener) {
            return contagion.between(speaker, listener);
        };
        bridge.routines = &routines;
        return bridge;
    }

    NoteRuntime note_runtime() {
        NoteRuntime bridge;
        bridge.fidelity_decay = diffusion.params().fidelity_decay;
        bridge.process_event = [this](const Event& event) { this->process_event(event); };
        bridge.routines = &routines;
        return bridge;
    }

    /// Let `minutes` of world time pass over the cast, and nothing else.
    ///
    /// Time itself: expiries, the weather, hours spent in the same room, and the
    /// day's schedule. Not the social layers -- those run once per tick, after
    /// the window has been walked. Every step in here is composable, which is
    /// what makes walking a window in pieces give the same answer as taking it
    /// whole: climate relaxation and familiarity growth are both
    /// `x += (target - x) * (1 - k**t)`, and `1 - k**(a+b)` is exactly the two
    /// applied in turn.
    void elapse(long long minutes) {
        if (minutes <= 0) return;
        World& w = world;
        w.world_time += minutes;
        // An engine that never answered has to stop holding a character. Done
        // before routines run, so the next block can issue a fresh intent rather
        // than finding the last one still open.
        for (const ResolvedIntent& record : actions_out.expire(w.world_time)) {
            Json why = Json::object();
            why["intent"] = record.intent.intent_id;
            why["actor"] = record.intent.actor;
            why["type"] = record.intent.type;
            last_traces["_actions"].push_back({"action.timed_out", 0.0, why});
        }
        for (const Reason& reason : climate.step(minutes))
            last_traces["_climate"].push_back(reason);
        grow_familiarity(minutes);
        for (const Reason& reason : routine.step(w, routines, minutes, on_arrival(),
                                                 carried_mood(), request_move()))
            last_traces["_routine"].push_back(reason);
    }

    void advance(long long delta) {
        World& w = world;
        long long target = w.world_time + delta;
        // THE WINDOW IS WALKED IN ORDER, and this is not a refinement. Scheduled
        // events used to be processed first, in a batch, against the positions
        // everybody held at the START of the window -- so who witnessed an
        // incident depended on how large a step the caller happened to take. One
        // 30-minute advance made a character a witness to something at minute 20
        // in a room they had left at minute 10; two steps of 10 and 20 did not.
        // Both end in the same place at the same time, and only one of them can
        // be right about the past.
        std::vector<Event> due;
        for (const Event& e : w.scenario_events)
            if (w.world_time < e.world_time && e.world_time <= target) due.push_back(e);
        std::stable_sort(due.begin(), due.end(),
                         [](const Event& a, const Event& b) {
                             if (a.world_time != b.world_time)
                                 return a.world_time < b.world_time;
                             return a.event_id < b.event_id;
                         });
        for (const Event& e : due) {
            elapse(e.world_time - w.world_time);
            process_event(e, 1.0);
            // `list.remove(e)` removes the FIRST equal element, which for these
            // events means the one with this event id.
            for (auto it = w.scenario_events.begin(); it != w.scenario_events.end(); ++it)
                if (it->event_id == e.event_id) { w.scenario_events.erase(it); break; }
        }
        // People go about their day first, then they talk: diffusion depends on
        // who is standing where, so moving after it would have everyone gossip
        // with yesterday's company.
        elapse(target - w.world_time);

        // Whoever has a reason to raise something goes and raises it. Before
        // diffusion, because a purposeful conversation should get the room
        // before the random ones do -- and after routines, because it needs
        // people to have arrived where they are going.
        DiffusionRuntime spread = diffusion_runtime();
        NoteRuntime paper = note_runtime();
        PursuitRuntime chase;
        chase.diffusion = &diffusion;
        chase.diffusion_runtime = &spread;
        chase.notes = &notes;
        chase.note_runtime = &paper;
        for (const Reason& reason : pursuit.step(w, chase, delta, player_id))
            last_traces["_pursuit"].push_back(reason);

        // Whatever has come due is settled before anybody acts on today, so a
        // character who was let down last night meets the world knowing it.
        PromiseRuntime kept;
        kept.exchange = exchange;
        kept.relationship = relationship;
        kept.reputation = reputation;
        for (const Reason& reason : promises.step(w, kept, delta))
            last_traces["_promises"].push_back(reason);

        // Anything left lying about gets picked up -- by whoever it was for, or
        // by somebody it was not. After pursuit, so a note left this tick is not
        // read in the same one, which would make it a conversation.
        for (const Reason& reason : notes.step(w, paper, delta))
            last_traces["_notes"].push_back(reason);

        // Information moves through the society during the elapsed time.
        for (const Reason& reason : diffusion.step(w, spread, delta, player_id))
            last_traces["_diffusion"].push_back(reason);

        // Decay affect and memory. With population LOD on, only agents that are
        // emotionally engaged are decayed now; calm ones are caught up lazily on
        // access, turning an O(population) tick into O(active).
        for (auto& entry : w.agents) {
            Agent& agent = entry.second;
            if (population_lod && agent.affect.active_emotions.empty()) continue;
            // Decay over the time elapsed since this agent was last decayed, not
            // the raw window: a mid-window event may already have caught the
            // agent up, and double-counting that span would over-decay affect.
            long long dt = target - last_decay_.get(agent.id, w.world_time);
            if (dt > 0) {
                affect.decay(agent.affect, dt);
                fade_identity_threat(agent, dt);
            }
            memory.decay_and_consolidate(agent.memory, target);
            last_decay_[agent.id] = target;
        }

        // The macro layer reacts last, to a world that has already talked.
        auto schedule = [&w](const Faction& faction, long long latency) {
            Event ev;
            ev.event_id = w.new_event_id();
            ev.world_time = w.world_time + latency;
            ev.type = "faction_mobilize";
            ev.actor = faction.faction_id;
            ev.location = faction.territory.empty() ? Json()
                                                    : Json(faction.territory.front());
            Json payload = Json::object();
            payload["faction"] = faction.faction_id;
            ev.payload = payload;
            w.scenario_events.push_back(ev);
        };
        for (const Reason& reason : director.step(w, delta, schedule))
            last_traces["_director"].push_back(reason);
        w.world_time = target;
    }

    std::string tagged_seed_;
    OrderedMap<long long> last_decay_;
    OrderedMap<long long> dropped_traces_;
    long long mem_counter_ = 0;
    bool collecting_ = false;
};

}  // namespace usc
