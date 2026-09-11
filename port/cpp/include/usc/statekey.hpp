// `usc/statekey.py`. Typed cross-cutting deltas.
//
// State changes do not get written where they are decided. A module proposes a
// delta and the owning module validates and applies it, which is why `fear` can
// be produced by the standing layer and still be owned by `relationship`.
//
// The constructor list is short and one entry on it is a scar:
// `relationship_delta` takes the field by name because for a long time only
// `trust` and `liking` had one. `fear`, `respect` and `dependence` had no way to
// be written at all -- which is a fair part of why three values read by four
// engines were produced by nothing.
#pragma once

#include <optional>
#include <string>

namespace usc {

struct StateKey {
    std::string module;                       // owning module, e.g. "relationship"
    std::string field;                        // "trust", "liking", ...
    std::string entity_id;                    // owner agent
    std::optional<std::string> subject_id;    // the other party
    std::optional<std::string> dimension;     // for reputation dimensions

    bool operator==(const StateKey& other) const {
        return module == other.module && field == other.field
            && entity_id == other.entity_id && subject_id == other.subject_id
            && dimension == other.dimension;
    }
};

struct ProposedDelta {
    StateKey key;
    double amount = 0.0;
    std::string reason;
    std::string source_module;
};

inline ProposedDelta trust_delta(const std::string& owner, const std::string& subject,
                                 double amount, const std::string& reason,
                                 const std::string& source) {
    return {{"relationship", "trust", owner, subject, std::nullopt},
            amount, reason, source};
}

inline ProposedDelta liking_delta(const std::string& owner, const std::string& subject,
                                  double amount, const std::string& reason,
                                  const std::string& source) {
    return {{"relationship", "liking", owner, subject, std::nullopt},
            amount, reason, source};
}

/// Any relationship dimension by name -- including whatever a pack authors.
inline ProposedDelta relationship_delta(const std::string& owner, const std::string& subject,
                                        const std::string& field, double amount,
                                        const std::string& reason,
                                        const std::string& source) {
    return {{"relationship", field, owner, subject, std::nullopt},
            amount, reason, source};
}

inline ProposedDelta reputation_delta(const std::string& subject, const std::string& audience,
                                      const std::string& dimension, double amount,
                                      const std::string& reason,
                                      const std::string& source) {
    return {{"reputation", "degree", audience, subject, dimension},
            amount, reason, source};
}

inline ProposedDelta identity_threat(const std::string& owner, const std::string& identity_id,
                                     double amount, const std::string& reason,
                                     const std::string& source) {
    return {{"identity", "threat", owner, identity_id, std::nullopt},
            amount, reason, source};
}

}  // namespace usc
