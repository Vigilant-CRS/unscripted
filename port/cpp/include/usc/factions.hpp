// `usc/factions.py`. The macro layer: the society develops whether or not the
// player is watching.
//
// Progress clocks after Blades in the Dark, plus a heat accumulator and
// off-screen action. A faction is a collective agent with resources, standing,
// goals tracked on clocks, and heat; the Director advances them each step and,
// when heat crosses a threshold, mobilises a response -- which is the
// ally-response mechanic at faction scale.
//
// Social standing matters here too: a faction's INFLUENCE scales how fast its
// clocks fill and how quickly it mobilises.
#pragma once

#include <algorithm>
#include <functional>
#include <string>
#include <vector>

#include "usc/determinism.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/types.hpp"
#include "usc/world.hpp"

namespace usc {

struct ProgressClock {
    std::string name;
    long long size = 6;
    long long filled = 0;

    /// Returns true only on the tick that COMPLETES it, not on every tick
    /// afterwards -- so a completed clock announces itself once.
    bool tick(long long segments = 1) {
        long long before = filled;
        filled = std::min(size, filled + segments);
        return filled > before && filled >= size;
    }

    bool complete() const { return filled >= size; }

    Json as_json() const {
        Json out = Json::object();
        out["name"] = name;
        out["filled"] = filled;
        out["size"] = size;
        return out;
    }

    static ProgressClock from_json(const Json& doc) {
        ProgressClock out;
        out.name = doc.at("name").as_string();
        out.size = doc.at("size").as_int();
        const Json* filled = doc.find("filled");
        out.filled = filled ? filled->as_int() : 0;
        return out;
    }
};

struct Faction {
    std::string faction_id;
    double influence = 0.5;              // social standing of the faction [0,1]
    double resources = 0.5;
    double heat = 0.0;                   // [0,1] escalation accumulator
    std::vector<std::string> territory;  // place ids
    std::vector<std::string> goals;      // clock names
    OrderedMap<ProgressClock> clocks;

    /// Full precision, every mutable field: this is the persistence shape.
    /// Display code rounds for presentation separately.
    Json as_json() const {
        Json out = Json::object();
        out["faction_id"] = faction_id;
        out["influence"] = influence;
        out["resources"] = resources;
        out["heat"] = heat;
        Json where = Json::array();
        for (const std::string& one : territory) where.push(Json(one));
        out["territory"] = where;
        Json wants = Json::array();
        for (const std::string& one : goals) wants.push(Json(one));
        out["goals"] = wants;
        Json running = Json::object();
        for (const auto& entry : clocks) running.fields()[entry.first] = entry.second.as_json();
        out["clocks"] = running;
        return out;
    }

    static Faction from_json(const Json& doc) {
        Faction out;
        out.faction_id = doc.at("faction_id").as_string();
        const Json* influence = doc.find("influence");
        if (influence) out.influence = influence->as_double();
        const Json* resources = doc.find("resources");
        if (resources) out.resources = resources->as_double();
        const Json* heat = doc.find("heat");
        if (heat) out.heat = heat->as_double();
        for (const Json& one : doc.at("territory").items()) out.territory.push_back(one.py_str());
        for (const Json& one : doc.at("goals").items()) out.goals.push_back(one.py_str());
        const Json* clocks = doc.find("clocks");
        if (clocks && !clocks->is_null())
            for (const auto& entry : clocks->fields())
                out.clocks[entry.first] = ProgressClock::from_json(entry.second);
        return out;
    }
};

using DirectorReason = Reason;

class Director {
public:
    struct Params {
        double heat_decay = 0.02;
        double heat_threshold = 0.6;
        double clock_base_rate = 0.15;
        long long mobilize_latency = 20;
    };

    static constexpr const char* MODULE_ID = "director";

    Director() = default;
    explicit Director(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }

    void add_faction(const Faction& faction) { factions_[faction.faction_id] = faction; }
    OrderedMap<Faction>& factions() { return factions_; }
    const OrderedMap<Faction>& factions() const { return factions_; }

    void add_heat(const std::string& faction_id, double amount, const std::string& why,
                  std::vector<DirectorReason>* reasons = nullptr) {
        Faction* faction = factions_.find(faction_id);
        if (!faction) return;
        double before = faction->heat;
        faction->heat = clamp01(faction->heat + amount);
        if (!reasons) return;
        Json detail = Json::object();
        detail["faction"] = faction_id;
        detail["reason"] = why;
        detail["heat"] = py_round(faction->heat, 3);
        reasons->push_back({"director.heat", py_round(faction->heat - before, 3), detail});
    }

    /// The faction holding this place, or nothing. FIRST match in declaration
    /// order, so a place claimed by two factions belongs to whichever the pack
    /// listed first -- which is an authoring error the validator should catch,
    /// not something to resolve silently here.
    const Faction* faction_controlling(const std::string& place_id) const {
        for (const auto& entry : factions_)
            if (std::find(entry.second.territory.begin(), entry.second.territory.end(),
                          place_id) != entry.second.territory.end())
                return &entry.second;
        return nullptr;
    }

    /// Advance clocks and heat, fire threshold mobilisations and completions.
    ///
    /// `schedule` puts a future event on the world timeline. It is a callback
    /// rather than a dependency for the same reason `routine`'s is: the
    /// scheduler is not ported, and naming the seam beats faking it.
    std::vector<DirectorReason> step(
            World& world, long long delta,
            const std::function<void(const Faction&, long long latency)>& schedule) {
        std::vector<DirectorReason> reasons;
        for (auto& entry : factions_) {
            Faction& faction = entry.second;
            faction.heat = clamp01(faction.heat
                                   - params_.heat_decay * (static_cast<double>(delta) / 60.0));

            // Goals advance faster with influence and resources: this is what
            // "off-screen progress" means -- a well-connected, well-funded
            // faction gets things done while nobody is looking.
            double rate = params_.clock_base_rate * (0.5 + faction.influence)
                        * (0.5 + faction.resources);
            for (const std::string& name : faction.goals) {
                if (!faction.clocks.contains(name))
                    faction.clocks[name] = ProgressClock{name, 6, 0};
                ProgressClock& clock = *faction.clocks.find(name);
                std::vector<std::uint8_t> seed = derive_seed(
                    world.global_seed, faction.faction_id, name, world.world_time,
                    "clocktick");
                if (seeded_uniform(seed) >= rate) continue;

                bool completed = clock.tick(1);
                Json detail = Json::object();
                detail["faction"] = faction.faction_id;
                detail["clock"] = name;
                detail["filled"] = clock.filled;
                detail["size"] = clock.size;
                reasons.push_back({"director.clock", 1.0, detail});
                if (completed) {
                    Json done = Json::object();
                    done["faction"] = faction.faction_id;
                    done["clock"] = name;
                    reasons.push_back({"director.clock_complete", 1.0, done});
                }
            }

            if (faction.heat >= params_.heat_threshold) {
                // `int(...)` truncates. Influence makes a faction faster, so a
                // well-connected one answers sooner.
                long long latency = static_cast<long long>(
                    static_cast<double>(params_.mobilize_latency) * (1.5 - faction.influence));
                if (schedule) schedule(faction, latency);
                Json detail = Json::object();
                detail["faction"] = faction.faction_id;
                detail["latency"] = latency;
                detail["in_response_to"] = std::string("heat_threshold");
                reasons.push_back({"director.mobilize", py_round(faction.heat, 3), detail});
                faction.heat = clamp01(faction.heat - 0.4);   // mobilising discharges some
            }
        }
        return reasons;
    }

private:
    Params params_;
    OrderedMap<Faction> factions_;
};

}  // namespace usc
