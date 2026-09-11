// `usc/climate.py`. Not who anyone is, but what it is like here.
//
// `CONCEPT.md` has said for a long time that traits are fixed -- relationships
// move, who somebody is does not -- and that is the right call: a personality
// that drifts under play is how every character in a long game converges on the
// same one. But it left a real thing unmodelled. A PLACE CAN CHANGE ITS MIND
// ABOUT STRANGERS. After a killing in the square, the square gets quieter,
// people are slower to pass things on, and a stranger asking questions is
// trusted less. Nobody's personality changed. The weather did.
//
// Three numbers, each with one job: `candour` (how readily what is known here
// gets passed on), `suspicion` (how much a claim is discounted for coming from
// outside), `openness` (how readily a stranger is spoken to at all).
//
// OFF BY DEFAULT, AND OFF IS BYTE-IDENTICAL. Every modifier is exactly neutral,
// nothing is stored, and a run reproduces the snapshot it produced before this
// module existed -- asserted by test rather than promised.
//
// WHY THIS IS THE HONEST VERSION OF "CULTURE SPREADS": it does not make anybody
// kinder or crueller. It changes the ambient conditions they read from where
// they are, which is a claim the runtime can support. Anything stronger would be
// personality drift wearing a different hat.
#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <string>
#include <vector>

#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/types.hpp"

namespace usc {

/// How far a full swing of one disposition can move the thing it governs. Small
/// on purpose: this is weather, and weather does not rewrite a world.
inline constexpr double TEMPO_SWING = 0.45;        // +-45% of the encounter rate
inline constexpr double THRESHOLD_SWING = 0.12;    // +-0.12 on a 0.60 threshold
inline constexpr double SKEPTICISM_SWING = 0.18;   // +-0.18 on a [0,1] skepticism
inline constexpr double STRANGER_SWING = 0.15;     // +-0.15 on a stranger's trust

/// World hours for a disturbance to decay halfway back to the authored
/// baseline. A day and a bit: long enough that a player feels it for the rest of
/// a session, short enough that a world is not permanently marked by one bad
/// afternoon.
inline constexpr double HALF_LIFE_HOURS = 30.0;

/// How much of where somebody came from arrives with them. THE WHOLE SPREADING
/// MECHANISM, and it is a person walking through a door rather than an abstract
/// pull between adjacent rooms.
///
/// An earlier version drifted every place toward its neighbours by the clock,
/// which produced the same picture and modelled the wrong thing: two rooms
/// joined by a door nobody uses would have converged anyway, and a room emptied
/// by a curfew would have kept absorbing its neighbours' mood.
inline constexpr double CARRIED_PER_ARRIVAL = 0.055;

/// Ceiling on how much one room can be moved by arrivals in a single step, so a
/// shift change cannot import a whole district's mood at once.
inline constexpr double MAX_CARRIED_PER_STEP = 0.22;

/// Neutral in every direction: what `modifiers()` returns when the layer is off,
/// and what every arithmetic path collapses to.
inline Json neutral_modifiers() {
    Json out = Json::object();
    out["tempo"] = 1.0;
    out["tell_threshold"] = 0.0;
    out["skepticism"] = 0.0;
    out["stranger_trust"] = 0.0;
    return out;
}

struct Climate {
    double candour = 0.5;
    double suspicion = 0.5;
    double openness = 0.5;

    Json as_json() const {
        Json out = Json::object();
        out["candour"] = py_round(candour, 4);
        out["suspicion"] = py_round(suspicion, 4);
        out["openness"] = py_round(openness, 4);
        return out;
    }

    void blend(const Climate& other, double weight) {
        candour = clamp01(candour + (other.candour - candour) * weight);
        suspicion = clamp01(suspicion + (other.suspicion - suspicion) * weight);
        openness = clamp01(openness + (other.openness - openness) * weight);
    }
};

/// What a place is like when nothing has happened.
///
/// Derived from what packs already declare, so an existing world gets a sensible
/// climate without anybody authoring one: a gossipy market is candid, a place
/// under surveillance is guarded, a private room is closed to strangers. A pack
/// may state it outright and that wins.
inline Climate baseline_for(const Json& place) {
    const Json* authored = place.find("climate");
    if (authored && authored->kind() == Json::Kind::Object) {
        auto value = [&](const char* key, double fallback) {
            const Json* found = authored->find(key);
            return clamp01(found ? found->as_double() : fallback);
        };
        return {value("candour", 0.5), value("suspicion", 0.5), value("openness", 0.5)};
    }
    auto value = [&](const char* key, double fallback) {
        const Json* found = place.find(key);
        return found ? found->as_double() : fallback;
    };
    double gossip = value("gossip_factor", 1.0);
    double surveillance = value("surveillance_level", 0.3);
    double privacy = value("privacy_level", 0.3);
    return {clamp01(0.30 + 0.30 * gossip - 0.25 * surveillance),
            clamp01(0.35 + 0.35 * surveillance),
            clamp01(0.65 - 0.45 * privacy)};
}

/// What moves the weather, at full severity.
///
/// Keyed on the event types the runtime ACTUALLY emits -- `threat` and `crime`
/// rather than the verbs a player types. Guessing the names here would have
/// produced a layer that ran, reported, and never once moved.
inline const OrderedMap<std::array<double, 3>>& climate_reactions() {
    static const OrderedMap<std::array<double, 3>>* table = [] {
        auto* fresh = new OrderedMap<std::array<double, 3>>();
        (*fresh)["attack"]           = {-0.22, +0.26, -0.24};
        (*fresh)["threat"]           = {-0.14, +0.16, -0.18};
        (*fresh)["crime"]            = {-0.18, +0.22, -0.20};
        (*fresh)["faction_mobilize"] = {-0.10, +0.14, -0.12};
        (*fresh)["discredit"]        = {-0.04, +0.20, -0.06};
        (*fresh)["promise"]          = {+0.06, -0.04, +0.10};
        (*fresh)["ally_arrives"]     = {+0.04, +0.02, +0.06};
        return fresh;
    }();
    return *table;
}

using ClimateReason = Reason;

class ClimateEngine {
public:
    static constexpr const char* MODULE_ID = "climate";

    ClimateEngine() = default;

    ClimateEngine(const Json& places, bool enabled) : enabled_(enabled) {
        for (const auto& entry : places.fields()) {
            baselines_[entry.first] = baseline_for(entry.second);
            now_[entry.first] = *baselines_.find(entry.first);
        }
    }

    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }

    Climate at(const std::string& place_id) const {
        const Climate* found = now_.find(place_id);
        return found ? *found : Climate{};
    }

    /// The four numbers the rest of the runtime asks for.
    ///
    /// Expressed as DEVIATIONS FROM NEUTRAL, so a caller can apply them without
    /// knowing anything about this module -- and so that "off" is exactly the
    /// same arithmetic as "average".
    Json modifiers(const std::string& place_id) const {
        if (!enabled_) return neutral_modifiers();
        Climate climate = at(place_id);
        Json out = Json::object();
        // A candid place talks more often, which is the speed of the thing.
        out["tempo"] = 1.0 + TEMPO_SWING * (climate.candour - 0.5) * 2.0;
        // A guarded place makes people surer before they pass something on.
        out["tell_threshold"] = -THRESHOLD_SWING * (climate.candour - 0.5) * 2.0;
        // A suspicious place discounts what it is told.
        out["skepticism"] = SKEPTICISM_SWING * (climate.suspicion - 0.5) * 2.0;
        // A closed place gives a stranger less to work with.
        out["stranger_trust"] = STRANGER_SWING * (climate.openness - 0.5) * 2.0;
        return out;
    }

    /// Let an event move the weather where it happened.
    std::vector<ClimateReason> react(const Event& event) {
        if (!enabled_) return {};
        if (event.location.is_null()) return {};
        const std::string place_id = event.location.py_str();
        Climate* climate = now_.find(place_id);
        if (!climate) return {};
        const std::array<double, 3>* deltas = climate_reactions().find(event.type);
        if (!deltas) return {};

        // `payload.get("severity", payload.get("importance", 0.5))` -- and
        // absolute, so an importance recorded as negative still closes a place
        // rather than opening it.
        const Json* severity_field = event.payload.find("severity");
        if (!severity_field) severity_field = event.payload.find("importance");
        double severity = severity_field ? std::fabs(severity_field->as_double()) : 0.5;
        severity = clamp01(severity);

        Json before = climate->as_json();
        climate->candour = clamp01(climate->candour + (*deltas)[0] * severity);
        climate->suspicion = clamp01(climate->suspicion + (*deltas)[1] * severity);
        climate->openness = clamp01(climate->openness + (*deltas)[2] * severity);

        Json detail = Json::object();
        detail["place"] = place_id;
        detail["event"] = event.type;
        detail["before"] = before;
        detail["after"] = climate->as_json();
        return {{"climate.moved", severity, detail}};
    }

    /// A place forgets, slowly, back toward what the pack authored.
    ///
    /// Without this, one bad afternoon marks a world permanently. Spreading is
    /// NOT done here -- see `carried`, which happens when somebody walks.
    std::vector<ClimateReason> step(long long delta_minutes) {
        if (!enabled_ || delta_minutes <= 0) return {};
        double relax = 1.0 - std::pow(0.5, (static_cast<double>(delta_minutes) / 60.0)
                                            / HALF_LIFE_HOURS);
        for (auto& entry : now_) entry.second.blend(*baselines_.find(entry.first), relax);
        carried_this_step_.clear();
        return {};
    }

    /// Somebody walks out of one room and into another, bringing the mood.
    ///
    /// The answer to the obvious question about a player who is vile to one
    /// shopkeeper: the shopkeeper's own affect carries their ruined day into how
    /// they speak to the next customer, and THIS carries the room's mood with
    /// whoever leaves it. Deliberately weak and capped -- a shift change should
    /// not import a district's mood in one tick.
    std::vector<ClimateReason> carried(const std::string& from_place,
                                       const std::string& to_place) {
        if (!enabled_ || from_place == to_place) return {};
        Climate* source = now_.find(from_place);
        Climate* target = now_.find(to_place);
        if (!source || !target) return {};

        double already = carried_this_step_.get(to_place, 0.0);
        double room = MAX_CARRIED_PER_STEP - already;
        if (room <= 0.0) return {};
        double weight = std::min(CARRIED_PER_ARRIVAL, room);

        Json before = target->as_json();
        target->blend(*source, weight);
        carried_this_step_[to_place] = already + weight;

        Json detail = Json::object();
        detail["from"] = from_place;
        detail["to"] = to_place;
        detail["before"] = before;
        detail["after"] = target->as_json();
        return {{"climate.carried", weight, detail}};
    }

    Json as_json() const {
        Json out = Json::object();
        out["enabled"] = enabled_;
        // `sorted(self.now.items())` -- alphabetical, not insertion order, so a
        // snapshot does not depend on the order a pack listed its places.
        Json rows = Json::object();
        for (const std::string& place_id : sorted_places())
            rows.fields()[place_id] = now_.find(place_id)->as_json();
        out["now"] = rows;
        return out;
    }

    void restore(const Json& data) {
        const Json* rows = data.find("now");
        if (!rows || rows->kind() != Json::Kind::Object) return;
        for (const auto& entry : rows->fields()) {
            Climate* here = now_.find(entry.first);
            if (!here) continue;
            auto value = [&](const char* key) {
                const Json* found = entry.second.find(key);
                return found ? found->as_double() : 0.5;
            };
            here->candour = value("candour");
            here->suspicion = value("suspicion");
            here->openness = value("openness");
        }
    }

    /// What a designer wants to see: where it is tense, and how far from normal.
    Json report() const {
        Json rows = Json::array();
        for (const std::string& place_id : sorted_places()) {
            const Climate& climate = *now_.find(place_id);
            const Climate& base = *baselines_.find(place_id);
            double drift = std::max({std::fabs(climate.candour - base.candour),
                                     std::fabs(climate.suspicion - base.suspicion),
                                     std::fabs(climate.openness - base.openness)});
            Json row = climate.as_json();
            // `{"place": ..., **climate.as_dict(), ...}` -- `place` comes FIRST.
            Json ordered = Json::object();
            ordered["place"] = place_id;
            for (const auto& field : row.fields())
                ordered.fields()[field.first] = field.second;
            ordered["drift_from_baseline"] = py_round(drift, 3);
            rows.push(ordered);
        }
        return rows;
    }

private:
    std::vector<std::string> sorted_places() const {
        std::vector<std::string> names;
        for (const auto& entry : now_) names.push_back(entry.first);
        std::sort(names.begin(), names.end());
        return names;
    }

    bool enabled_ = false;
    OrderedMap<Climate> baselines_;
    OrderedMap<Climate> now_;
    OrderedMap<double> carried_this_step_;
};

}  // namespace usc
