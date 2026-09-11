// `usc/events.py`. What happened, what was said, and what somebody perceived.
//
// The three are deliberately separate, and the distinction is the whole point of
// this runtime:
//
//   Event       the smallest authoritative unit -- what happened.
//   Claim       a communicated proposition -- what was SAID. It moves belief and
//               is never truth.
//   Observation one character's perception of an event, weighted by how well
//               they could actually perceive it.
//
// A claim is carried in an event's payload rather than being its own type,
// because "somebody asserted X" is itself a thing that happened and has to be
// perceivable, rememberable and passable on.
#pragma once

#include <optional>
#include <string>

#include "usc/json.hpp"
#include "usc/ontology.hpp"

namespace usc {

struct Event {
    long long event_id = 0;
    long long world_time = 0;
    /// "claim", "question", "threat", "gift", "broadcast", ...
    ///
    /// `claim` asserts its proposition and moves belief. `question` names one
    /// WITHOUT asserting it: heard, remembered and reacted to, never evidence.
    /// A port that treated the two alike would have characters convinced by
    /// being asked.
    std::string type;
    Json actor;
    Json location;
    Json payload;
    bool canonical = true;

    std::optional<Proposition> proposition() const {
        const Json* found = payload.find("proposition");
        if (!found || found->kind() != Json::Kind::Object) return std::nullopt;
        return Proposition::from_json(*found);
    }

    const Json& appraisal() const { return payload.at("appraisal"); }
};

struct Observation {
    std::string observer;
    long long event_id = 0;
    std::string modality;
    /// [0,1] signal quality after distance, noise and obstruction.
    double quality = 0.0;
    std::optional<Event> event;
};

}  // namespace usc
