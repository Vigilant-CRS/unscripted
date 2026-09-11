// `usc/diffusion.py`. How information actually moves through a society.
//
// Until this module existed, a character learned something only by being present
// when it happened. Nobody ever told anybody anything, and seventy-two simulated
// hours with the whole cast in one room changed nothing: four co-present agents
// knew a thing, and afterwards still exactly those four. That made the runtime's
// central claim untrue, and it made correlation discounting guard against a
// situation the engine could not produce -- ten people repeating one rumour
// requires a mechanism by which a second person ever repeats it.
//
// The design adds NO new belief machinery. A retelling is an ordinary `claim`
// event by the speaker at their location, so it flows through the existing
// perception -> belief -> memory -> affect path. Three things fall out for free:
// every retelling is a row in the ledger, bystanders overhear it weighted by the
// room's noise, and the claim carries the ORIGINAL origin rather than the teller
// -- so a rumour that reaches you through five mouths from one witness is still
// one witness.
//
// THE RUNTIME IS A SEAM, not a dependency. Python reaches through `runtime` for
// the climate, common-knowledge and contagion layers and for the event ledger.
// None of those is ported; all of them are OFF by default, and off is exactly
// neutral. So they are optional callbacks here, defaulting to the neutral
// behaviour, and the ledger is a callback the caller supplies. Faking them would
// be worse than naming them.
#pragma once

#include <algorithm>
#include <cmath>
#include <functional>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/content.hpp"
#include "usc/determinism.hpp"
#include "usc/distortion.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/medium.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/social.hpp"
#include "usc/topology.hpp"
#include "usc/world.hpp"
#include "usc/knob.hpp"

namespace usc {

using DiffusionReason = Reason;

/// What diffusion needs from the rest of the runtime.
///
/// Every hook is optional and every default is the behaviour with the
/// corresponding layer switched off -- which is the shipped default, and which
/// a test asserts is byte-identical rather than merely claimed.
struct DiffusionRuntime {
    SocialNetworkEngine network;
    /// The event ledger. Without it a retelling is computed and goes nowhere,
    /// which is useful for a probe and wrong for a game.
    std::function<void(const Event&)> process_event;
    /// `climate.modifiers(place)`: {"tempo": 1.0, "tell_threshold": 0.0} when off.
    std::function<Json(const std::string& place)> climate_modifiers;
    /// `common_knowledge.is_common(key, a, b)`: false when off.
    std::function<bool(const std::string& key, const std::string& speaker,
                       const std::string& listener)> is_common;
    /// `contagion.between(speaker, listener)`: nothing when off.
    std::function<std::vector<DiffusionReason>(Agent&, Agent&)> contagion;
    /// Routines, for the assimilation path in `distortion`.
    const OrderedMap<Routine>* routines = nullptr;
};

class DiffusionEngine {
public:
    struct Params {
        /// Chance a co-located, socially connected pair actually talks about
        /// something during one simulated hour.
        double encounters_per_hour = 0.35;
        /// Hard ceiling per step, so a crowded scene cannot make a tick O(n^2).
        long long max_encounters_per_tick = 48;
        /// A speaker only passes on what they actually believe.
        double min_confidence_to_tell = 0.60;
        /// Below this tie strength people do not chat unprompted.
        double min_tie = 0.05;
        /// How much conviction survives one retelling. Calibrated against serial
        /// reproduction (Bartlett 1932; Allport & Postman 1947): roughly two
        /// thirds of detail gone after five or six retellings, which 0.80 per
        /// hop reproduces -- 0.80^5 = 0.33.
        double fidelity_decay = 0.80;
        /// Chance a retelling changes the claim rather than passing it intact.
        /// Higher than the old value because most distortion is now gradual
        /// loss, which is common, rather than inversion, which is not.
        double distortion_prob = 0.18;
        /// Daley & Kendall stifling: chance a spreader loses interest after
        /// telling somebody who already knew. This is the mechanism that makes a
        /// rumour saturate on its own.
        double stifle_prob = 1.0;
        /// Whether NPCs gossip to the player unprompted. Off by default: it
        /// changes the feel of a scene and should be a deliberate choice.
        bool include_player = false;
        /// Safety guard only. Termination is supposed to come from stifling,
        /// which models something; a hop limit models nothing. Kept high so it
        /// never binds, and so a pack that disables stifling still cannot
        /// circulate one claim forever.
        long long max_hops = 12;
        /// How many bystanders can overhear one exchange. A conversation is not
        /// a public announcement: without a bound every retelling was perceived
        /// by everyone present, which made a crowded scene quadratic and let
        /// gossip saturate a square instantly. Overhearing is how a player picks
        /// up rumours in a bar, so it stays on -- just bounded.
        long long bystanders = 3;
        /// Relative frequency of the four distortion processes. Empty means the
        /// defaults in `distortion.hpp`.
        OrderedMap<double> distortion_weights;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("encounters_per_hour", &Params::encounters_per_hour),
            knob("max_encounters_per_tick", &Params::max_encounters_per_tick),
            knob("min_confidence_to_tell", &Params::min_confidence_to_tell),
            knob("min_tie", &Params::min_tie),
            knob("fidelity_decay", &Params::fidelity_decay),
            knob("distortion_prob", &Params::distortion_prob),
            knob("distortion_weights", &Params::distortion_weights),
            knob("stifle_prob", &Params::stifle_prob),
            knob("include_player", &Params::include_player),
            knob("max_hops", &Params::max_hops),
            knob("bystanders", &Params::bystanders),
        };
        return table;
    }

    static constexpr const char* MODULE_ID = "diffusion";

    DiffusionEngine() = default;
    explicit DiffusionEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    /// One diffusion pass over `delta_minutes` of world time.
    std::vector<DiffusionReason> step(World& world, DiffusionRuntime& runtime,
                                      long long delta_minutes,
                                      const std::string& player_id = "") {
        if (delta_minutes <= 0) return {};
        std::vector<DiffusionReason> reasons;
        double hours = static_cast<double>(delta_minutes) / 60.0;
        long long emitted = 0;

        for (const auto& entry : populated_places(world, player_id)) {
            const std::string& place_id = entry.first;
            const std::vector<Agent*>& occupants = entry.second;

            const Json& place = world.places.at(place_id);
            const Json* declared = place.find("gossip_factor");
            double gossip = declared ? declared->as_double() : 1.0;
            if (gossip <= 0.0) continue;

            // What it is like here scales how often people talk at all. Neutral
            // when the climate layer is off, so this multiplication changes
            // nothing -- which is the point of "off is exactly neutral".
            if (runtime.climate_modifiers) {
                Json mods = runtime.climate_modifiers(place_id);
                const Json* tempo = mods.find("tempo");
                gossip *= tempo ? tempo->as_double() : 1.0;
            }

            // Sample encounters; do NOT enumerate pairs. A crowd of n has
            // n*(n-1) ordered pairs, and walking them made a tick quadratic in
            // population. People do not each hold a conversation with everyone
            // present: the number of conversations grows with the size of the
            // room, not with its square.
            double expected = params_.encounters_per_hour * gossip * hours
                            * static_cast<double>(occupants.size());
            long long whole = static_cast<long long>(expected);   // int() truncates
            long long wanted = std::min(whole, params_.max_encounters_per_tick - emitted);
            double fraction = expected - static_cast<double>(whole);
            std::vector<std::uint8_t> frac_seed = derive_seed(
                world.global_seed, place_id, world.world_time,
                static_cast<long long>(occupants.size()), MODULE_ID, "fraction");
            if (seeded_uniform(frac_seed) < fraction) wanted += 1;
            if (wanted <= 0) continue;

            if (emitted + wanted >= params_.max_encounters_per_tick) {
                Json detail = Json::object();
                detail["cap"] = params_.max_encounters_per_tick;
                detail["place"] = place_id;
                detail["note"] = std::string("encounters deferred to the next tick");
                reasons.push_back({"diffusion.tick_capped",
                                   static_cast<double>(emitted + wanted), detail});
            }

            for (long long index = 0; index < wanted; ++index) {
                auto [speaker, listener] = participants(world, occupants, place_id, index);
                if (!speaker) continue;
                double tie = tie_strength(runtime, *speaker, *listener);
                if (tie < params_.min_tie) {
                    Json detail = Json::object();
                    detail["speaker"] = speaker->id;
                    detail["listener"] = listener->id;
                    reasons.push_back({"diffusion.no_tie", tie, detail});
                    continue;
                }
                if (tell(world, runtime, *speaker, *listener, place_id, reasons))
                    emitted += 1;
            }
        }
        return reasons;
    }

    /// Say this particular thing to this particular person.
    ///
    /// The public half of `tell`: somebody with a reason supplies the topic, and
    /// everything after -- the topology gate, distortion, the claim event,
    /// earshot, provenance, hops -- is the same code the random path runs. A
    /// purposeful conversation must not be a second kind of conversation.
    bool tell_about(World& world, DiffusionRuntime& runtime, Agent& speaker,
                    Agent& listener, const std::string& place_id,
                    const std::string& key, std::vector<DiffusionReason>& reasons,
                    const Medium* medium = nullptr) {
        Belief* belief = speaker.beliefs.find(key);
        if (!belief) return false;
        return deliver(world, runtime, speaker, listener, place_id, key, *belief,
                       reasons, medium);
    }

    /// Beliefs this speaker holds confidently and is not withholding.
    ///
    /// Ranked by how much it is on their mind: confidence margin weighted by how
    /// recently it moved. Protected propositions never appear -- a secret is not
    /// gossip, and that filter is the same one the dialogue planner uses.
    std::vector<std::pair<double, std::string>> tellable(
            const Agent& speaker, const World& world,
            const std::set<std::string>& protect, double threshold_shift = 0.0) const {
        double floor = params_.min_confidence_to_tell + threshold_shift;
        std::vector<std::pair<double, std::string>> candidates;
        for (const auto& entry : speaker.beliefs) {
            if (protect.count(entry.first)) continue;
            const Belief& belief = entry.second;
            double probability = belief.expected_prob();
            double confidence = std::max(probability, 1.0 - probability);
            if (confidence < floor) continue;
            if (!belief.spreading) continue;      // lost interest in passing it on
            if (belief.hops >= params_.max_hops) continue;
            long long since = world.world_time
                            - (belief.txn_time.is_number() ? belief.txn_time.as_int() : 0);
            double recency = 1.0 / (1.0 + std::max(0LL, since) / 240.0);
            candidates.emplace_back(confidence * (0.4 + 0.6 * recency), entry.first);
        }
        // `sort(key=lambda c: (-c[0], c[1]))` -- by score descending, then by
        // the proposition key ascending. Fully determined, so stability does not
        // arise; the key breaks every tie.
        std::sort(candidates.begin(), candidates.end(),
                  [](const auto& a, const auto& b) {
                      if (a.first != b.first) return a.first > b.first;
                      return a.second < b.second;
                  });
        return candidates;
    }

private:
    /// Who can hear this exchange: the listener, plus a few people nearby.
    std::vector<std::string> audience(World& world, const Agent& speaker,
                                      const Agent& listener,
                                      const std::string& place_id) const {
        std::vector<std::string> others;
        for (const auto& entry : world.agents) {
            const Agent& one = entry.second;
            if (one.location().py_str() != place_id) continue;
            if (one.id == speaker.id || one.id == listener.id) continue;
            others.push_back(one.id);
        }
        std::sort(others.begin(), others.end());
        long long limit = std::max(0LL, params_.bystanders);
        if (others.empty() || limit == 0) return {listener.id};

        std::vector<std::uint8_t> seed = derive_seed(
            world.global_seed, speaker.id, listener.id, world.world_time,
            MODULE_ID, "audience");
        std::size_t start = static_cast<std::size_t>(seeded_uniform(seed) * others.size());
        std::vector<std::string> out = {listener.id};
        std::size_t take = std::min<std::size_t>(static_cast<std::size_t>(limit), others.size());
        for (std::size_t i = 0; i < take; ++i)
            out.push_back(others[(start + i) % others.size()]);
        return out;
    }

    /// Deterministically pick who is talking to whom in this encounter.
    std::pair<Agent*, Agent*> participants(World& world,
                                           const std::vector<Agent*>& occupants,
                                           const std::string& place_id,
                                           long long index) const {
        if (occupants.size() < 2) return {nullptr, nullptr};
        std::vector<std::uint8_t> speaker_seed = derive_seed(
            world.global_seed, place_id, world.world_time, index, MODULE_ID, "speaker");
        std::vector<std::uint8_t> listener_seed = derive_seed(
            world.global_seed, place_id, world.world_time, index, MODULE_ID, "listener");

        std::size_t which = static_cast<std::size_t>(
            seeded_uniform(speaker_seed) * occupants.size()) % occupants.size();
        Agent* speaker = occupants[which];
        std::vector<Agent*> others;
        for (Agent* one : occupants) if (one->id != speaker->id) others.push_back(one);
        std::size_t pick = static_cast<std::size_t>(
            seeded_uniform(listener_seed) * others.size()) % others.size();
        return {speaker, others[pick]};
    }

    /// Places with at least two people in them, occupants sorted by id.
    OrderedMap<std::vector<Agent*>> populated_places(World& world,
                                                     const std::string& player_id) const {
        OrderedMap<std::vector<Agent*>> places;
        for (auto& entry : world.agents) {
            Agent& one = entry.second;
            if (!player_id.empty() && one.id == player_id) continue;
            // `if agent.location:` -- truthiness, so somebody nowhere is nowhere.
            if (one.location().is_null() || one.location().py_str().empty()) continue;
            places[one.location().py_str()].push_back(&one);
        }
        OrderedMap<std::vector<Agent*>> out;
        for (auto& entry : places) {
            if (entry.second.size() < 2) continue;
            std::sort(entry.second.begin(), entry.second.end(),
                      [](const Agent* a, const Agent* b) { return a->id < b->id; });
            out[entry.first] = entry.second;
        }
        return out;
    }

    /// How likely these two are to swap news at all.
    double tie_strength(DiffusionRuntime& runtime, const Agent& speaker,
                        const Agent& listener) const {
        double strength = runtime.network.tie_strength(speaker, listener.id);
        double bridge = runtime.network.bridge_score(speaker);
        return clamp01(0.7 * strength + 0.3 * bridge);
    }

    bool tell(World& world, DiffusionRuntime& runtime, Agent& speaker, Agent& listener,
              const std::string& place_id, std::vector<DiffusionReason>& reasons) {
        double shift = 0.0;
        if (runtime.climate_modifiers) {
            Json mods = runtime.climate_modifiers(place_id);
            const Json* threshold = mods.find("tell_threshold");
            if (threshold) shift = threshold->as_double();
        }
        std::set<std::string> protect = protected_keys(secrets_of(speaker));
        auto candidates = tellable(speaker, world, protect, shift);
        if (candidates.empty()) return false;

        // Deterministically pick among the top few, so a speaker does not repeat
        // the single most salient item to everyone they meet.
        std::vector<std::uint8_t> seed = derive_seed(
            world.global_seed, speaker.id, listener.id, world.world_time,
            MODULE_ID, "topic");
        std::size_t top = std::min<std::size_t>(3, candidates.size());
        std::size_t which = static_cast<std::size_t>(seeded_uniform(seed) * top) % top;
        const std::string& key = candidates[which].second;
        Belief* belief = speaker.beliefs.find(key);
        if (!belief) return false;
        return deliver(world, runtime, speaker, listener, place_id, key, *belief, reasons);
    }

    static std::vector<Secret> secrets_of(const Agent& speaker) {
        std::vector<Secret> out;
        for (const Json& row : speaker.secrets) out.push_back(Secret::from_json(row));
        return out;
    }

    bool deliver(World& world, DiffusionRuntime& runtime, Agent& speaker, Agent& listener,
                 const std::string& place_id, const std::string& key, Belief& belief,
                 std::vector<DiffusionReason>& reasons,
                 const Medium* medium = nullptr) {
        // Nobody says out loud what the two of them already watched a crowd find
        // out. Categorical, unlike the Daley-Kendall coin below: that one models
        // a spreader losing interest, this one models there being nothing left
        // to tell.
        if (runtime.is_common && runtime.is_common(key, speaker.id, listener.id)) {
            Json detail = Json::object();
            detail["speaker"] = speaker.id;
            detail["listener"] = listener.id;
            detail["proposition"] = key;
            detail["note"] = std::string("both were there when it became public");
            reasons.push_back({"common_knowledge.not_news", 0.0, detail});
            return false;
        }

        // Would they pass THIS to THIS person, here? Restricted things stay
        // inside their circle, shop talk bores outsiders, and some claims do not
        // circulate in some places at all. This is what keeps a large cast from
        // converging on one shared memory.
        auto [weight, why] = may_pass_on(world.predicates, belief.proposition,
                                         speaker, listener, Json(place_id));
        if (weight <= 0.0) {
            Json detail = Json::object();
            detail["speaker"] = speaker.id;
            detail["listener"] = listener.id;
            for (const auto& field : why.second.fields())
                detail.fields()[field.first] = field.second;
            reasons.push_back({why.first, 0.0, detail});
            return false;
        }
        std::vector<std::uint8_t> gate = derive_seed(
            world.global_seed, speaker.id, listener.id, world.world_time,
            MODULE_ID, "topology");
        if (seeded_uniform(gate) > weight) {
            Json detail = Json::object();
            detail["speaker"] = speaker.id;
            detail["listener"] = listener.id;
            for (const auto& field : why.second.fields())
                detail.fields()[field.first] = field.second;
            reasons.push_back({"diffusion.not_worth_telling", weight, detail});
            return false;
        }

        bool listener_knew = listener.beliefs.contains(key);
        bool asserted_positive = belief.expected_prob() >= 0.5;

        // What gets retold may not be what was heard. A distorted claim becomes
        // a DIFFERENT proposition with its own canonical key, so the listener
        // forms a separate belief and a town can end up confidently believing
        // something that never happened. It still carries the true origin, so it
        // stays one source that is now wrong.
        Proposition told = belief.proposition;
        Json distortion_kind;
        Json distortion_detail = Json::object();
        std::vector<std::uint8_t> distort_seed = derive_seed(
            world.global_seed, speaker.id, listener.id, world.world_time,
            MODULE_ID, "distort");
        // A leaner medium loses more. This is the one number media richness
        // theory actually buys, and it lands on the levelling the distortion
        // layer already implements rather than on a new mechanism.
        double distortion_prob = params_.distortion_prob
                               * (medium ? medium->distortion_scale() : 1.0);
        if (seeded_uniform(distort_seed) < distortion_prob) {
            const Routine* routine = nullptr;
            if (runtime.routines) routine = runtime.routines->find(speaker.id);
            // ONE set, named. Writing `vector(f(x).begin(), f(x).end())` builds
            // two separate temporaries and takes an iterator from each, which is
            // undefined behaviour -- and here it SPUN FOREVER rather than
            // crashing, which is the failure mode that costs the most to find.
            const std::set<std::string> protect = protected_keys(secrets_of(speaker));
            auto outcome = distort(
                belief.proposition, speaker, world,
                derive_seed(world.global_seed, speaker.id, listener.id,
                            world.world_time, MODULE_ID, "distort-kind"),
                params_.distortion_weights.empty() ? nullptr : &params_.distortion_weights,
                std::vector<std::string>(protect.begin(), protect.end()),
                routine);
            if (outcome) {
                told = outcome->proposition;
                distortion_kind = Json(outcome->kind);
                distortion_detail = outcome->detail;
                if (outcome->kind == INVERSION) asserted_positive = !asserted_positive;
            }
        }
        bool distorted = !distortion_kind.is_null();

        // The origin travels with the claim, NOT the teller. This is the whole
        // point: five mouths relaying one witness is still one witness.
        const std::string* primary = belief.primary_origin();
        std::string origin = primary ? *primary : ("origin:" + speaker.id + ":" + key);
        long long hops = belief.hops + 1;

        // Nobody overhears a phone call, which is exactly why a call is where a
        // secret goes -- and why a claim made on one leaves no bystanders
        // holding it afterwards.
        std::vector<std::string> heard_by;
        if (!medium || medium->audience)
            heard_by = audience(world, speaker, listener, place_id);

        // Conviction lost along the chain. This used to be computed, written
        // into the payload and never read -- a documented parameter with no
        // effect. The evidential weight of the assertion is scaled by it, so a
        // fifth-hand rumour genuinely persuades less than a first-hand one.
        double strength = std::pow(params_.fidelity_decay, static_cast<double>(hops));
        // A voice with no face behind it is harder to weigh, and everybody knows
        // it. The listener's discount for the channel, not a claim that phones
        // lie.
        if (medium) strength *= medium->trust_factor;

        Json payload = Json::object();
        payload["proposition"] = told.as_json();
        payload["asserter_polarity"] = std::string(asserted_positive ? "+" : "-");
        payload["origin_event"] = origin;
        payload["summary"] = (speaker.public_name.is_null()
                                  ? speaker.id : speaker.public_name.py_str())
                           + " passes on what they heard";
        payload["importance"] = 0.35;
        payload["domain"] = std::string("gossip");
        Json listeners = Json::array();
        for (const std::string& one : heard_by) listeners.push(Json(one));
        payload["audience"] = listeners;
        payload["medium"] = medium ? medium->name : std::string("in_person");
        Json trace = Json::object();
        trace["speaker"] = speaker.id;
        trace["listener"] = listener.id;
        trace["hops"] = hops;
        trace["distorted"] = distorted;
        trace["distortion_kind"] = distortion_kind;
        trace["distortion_detail"] = distortion_detail;
        trace["fidelity"] = py_round(strength, 4);
        payload["diffusion"] = trace;
        payload["assertion_strength"] = py_round(strength, 4);

        Event event;
        event.event_id = world.new_event_id();
        event.world_time = world.world_time;
        event.type = "claim";
        event.actor = Json(speaker.id);
        event.location = Json(place_id);
        event.payload = payload;
        if (runtime.process_event) runtime.process_event(event);

        // Daley & Kendall (1964): a spreader who meets somebody already informed
        // stops spreading. Without it, termination came from an arbitrary hop
        // cap and the rumour reached everybody; with it, saturation is an
        // outcome of the model rather than a number somebody picked.
        if (listener_knew) {
            std::vector<std::uint8_t> stifle_seed = derive_seed(
                world.global_seed, speaker.id, listener.id, world.world_time,
                MODULE_ID, "stifle");
            if (seeded_uniform(stifle_seed) < params_.stifle_prob) {
                belief.spreading = false;
                Json detail = Json::object();
                detail["speaker"] = speaker.id;
                detail["listener"] = listener.id;
                detail["proposition"] = belief.proposition.str();
                detail["note"] = std::string(
                    "told someone who already knew; stopped spreading this");
                reasons.push_back({"diffusion.stifled", static_cast<double>(hops), detail});
            }
        }

        // A conversation is not only an exchange of claims. Whoever spoke was in
        // some mood while they did it, and a little of it stays with the
        // listener. Placed here, after the claim has landed, because it is a
        // consequence of the exchange rather than a condition on it.
        if (runtime.contagion)
            for (DiffusionReason& row : runtime.contagion(speaker, listener))
                reasons.push_back(std::move(row));

        Json detail = Json::object();
        detail["speaker"] = speaker.id;
        detail["listener"] = listener.id;
        detail["place"] = place_id;
        detail["proposition"] = told.str();
        detail["origin"] = origin;
        detail["hops"] = hops;
        detail["distorted"] = distorted;
        detail["note"] = std::string(
            "origin travels with the claim; repeats from it stay discounted");
        reasons.push_back({"diffusion.told", static_cast<double>(hops), detail});

        if (distorted) {
            Json why = Json::object();
            why["speaker"] = speaker.id;
            why["kind"] = distortion_kind;
            why["heard"] = belief.proposition.str();
            why["retold"] = told.str();
            why["what_changed"] = describe(distortion_kind.py_str(), distortion_detail);
            for (const auto& field : distortion_detail.fields())
                why.fields()[field.first] = field.second;
            reasons.push_back({"diffusion.distorted", 1.0, why});
        }
        return true;
    }

    Params params_;
};

}  // namespace usc
