// `usc/perception.py`. Who could perceive an event, and how well.
//
// Co-location plus environmental noise, plus media exposure for a broadcast.
// The output is quality-weighted, so a noisy bar yields partial hearing rather
// than either perfect hearing or none.
//
// THE SEEDED DRAW IS INSIDE A LOOP OVER A COLLECTION, which is the shape the
// conformance fixtures exist to catch. `world.occupants()` sorts by id for
// exactly this reason: without it, two implementations would hand the same
// jitter to different people and the same event would be heard differently in
// each -- once in a thousand ticks, and never attributable to this line.
#pragma once

#include <algorithm>
#include <string>
#include <vector>

#include "usc/determinism.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/world.hpp"

namespace usc {

class PerceptionEngine {
public:
    struct Params {
        double base_quality = 0.95;
    };

    PerceptionEngine() = default;
    explicit PerceptionEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    static constexpr const char* MODULE_ID = "perception";

    std::vector<Observation> filter(const Event& event, World& world) const {
        std::vector<Observation> out;
        const Json& place = world.places.at(event.location.py_str());
        const Json* noise_level = place.find("noise_level");
        double noise = noise_level ? noise_level->as_double() : 0.0;

        if (event.type == "broadcast") {
            const Json* channel = event.payload.find("channel");
            std::string channel_id = channel ? channel->py_str() : "None";
            for (const auto& entry : world.agents) {
                const Json* exposure = world.exposure(entry.second.id, channel_id);
                // `if exposure:` is a truthiness test: an empty record is not an
                // audience, and neither is one that was never written.
                if (!exposure || exposure->fields().empty()) continue;
                const Json* attention = exposure->find("attention");
                double quality = std::max(0.0, attention ? attention->as_double() : 0.5);
                out.push_back({entry.second.id, event.event_id, "media", quality, event});
            }
            return out;
        }

        // An event may name its audience: a word between two people in a crowded
        // square is heard by those nearby, not by everyone in the square.
        // Without it every retelling was perceived by the whole population of a
        // place, which is both wrong and quadratic in crowd size.
        const Json* audience = event.payload.find("audience");
        bool has_audience = audience && !audience->is_null();
        std::vector<std::string> named;
        if (has_audience)
            for (const Json& who : audience->items()) named.push_back(who.py_str());

        for (Agent* agent : world.occupants(event.location)) {
            if (!event.actor.is_null() && agent->id == event.actor.py_str()) continue;
            if (has_audience
                && std::find(named.begin(), named.end(), agent->id) == named.end())
                continue;
            std::vector<std::uint8_t> seed = derive_seed(
                world.global_seed, agent->id, event.event_id, world.world_time, MODULE_ID);
            double jitter = (seeded_uniform(seed) - 0.5) * 0.1;
            double quality = std::max(0.0, params_.base_quality * (1.0 - noise) + jitter);
            bool spoken = event.type == "claim" || event.type == "promise"
                       || event.type == "threat" || event.type == "question";
            out.push_back({agent->id, event.event_id, spoken ? "hearing" : "sight",
                           quality, event});
        }
        return out;
    }

private:
    Params params_;
};

}  // namespace usc
