// `usc/distortion.py`. How a claim changes shape as it is passed along.
//
// This used to be a coin flip that inverted a claim: either the rumour survived
// intact or it became its own negation. That is not what happens to information
// in a society. Allport & Postman (1947), following Bartlett (1932), identified
// three processes that operate together every time a story is retold --
// levelling (detail drops out, by far the largest effect), sharpening (what
// survives grows), assimilation (the story drifts toward the teller's own
// world). Inversion is rare, which is exactly why the coin flip was wrong.
//
// Two properties make this epistemically interesting rather than merely noisy: a
// distorted claim is a DIFFERENT proposition with a different canonical key, so
// the listener forms a genuinely separate belief and a town can end up
// confidently believing something that never happened -- while the claim still
// carries the ORIGINAL origin, so it stays one source that is now wrong.
#pragma once

#include <algorithm>
#include <cmath>
#include <cctype>
#include <cstdio>
#include <cstdlib>
#include <optional>
#include <string>
#include <tuple>
#include <vector>

#include "usc/agent.hpp"
#include "usc/determinism.hpp"
#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/pysum.hpp"
#include "usc/routine.hpp"
#include "usc/world.hpp"

namespace usc {

inline constexpr const char* LEVELLING = "levelling";
inline constexpr const char* SHARPENING = "sharpening";
inline constexpr const char* ASSIMILATION = "assimilation";
inline constexpr const char* INVERSION = "inversion";

/// Relative frequency of each process. Levelling dominates, which is Allport &
/// Postman's central finding: retelling mostly LOSES information rather than
/// changing it.
inline const OrderedMap<double>& default_distortion_weights() {
    static const OrderedMap<double>* table = [] {
        auto* fresh = new OrderedMap<double>();
        (*fresh)[LEVELLING] = 0.55;
        (*fresh)[SHARPENING] = 0.20;
        (*fresh)[ASSIMILATION] = 0.20;
        (*fresh)[INVERSION] = 0.05;
        return fresh;
    }();
    return *table;
}

/// How much a quantity grows when sharpened. Modest on purpose: runaway
/// exaggeration over several hops comes from repetition, not from one big step.
inline constexpr double SHARPEN_FACTOR = 1.5;

/// `seed.hex()` -- lowercase, no separators. It is fed straight back into
/// `derive_seed` as a string, so the encoding is part of the answer.
inline std::string seed_hex(const std::vector<std::uint8_t>& seed) {
    static const char* digits = "0123456789abcdef";
    std::string out;
    out.reserve(seed.size() * 2);
    for (std::uint8_t byte : seed) {
        out += digits[byte >> 4];
        out += digits[byte & 0x0F];
    }
    return out;
}

/// `^-?\d+(?:[.,]\d+)?$` -- an integer or a decimal, with either separator.
inline bool looks_numeric(const std::string& text) {
    std::size_t at = 0;
    if (at < text.size() && text[at] == '-') ++at;
    std::size_t digits_before = 0;
    while (at < text.size() && std::isdigit(static_cast<unsigned char>(text[at]))) {
        ++at; ++digits_before;
    }
    if (digits_before == 0) return false;
    if (at == text.size()) return true;
    if (text[at] != '.' && text[at] != ',') return false;
    ++at;
    std::size_t digits_after = 0;
    while (at < text.size() && std::isdigit(static_cast<unsigned char>(text[at]))) {
        ++at; ++digits_after;
    }
    return digits_after > 0 && at == text.size();
}

struct Distortion {
    Proposition proposition;
    std::string kind;
    Json detail = Json::object();
};

namespace detail_ {

/// `str(value or "")` -- Python TRUTHINESS, not a null check. A slot holding the
/// number 0 becomes the empty string and is therefore not numeric, which is a
/// real behaviour and not an accident worth tidying.
inline std::string truthy_str(const Json& value) {
    if (value.is_null()) return "";
    if (value.kind() == Json::Kind::Bool) return value.as_bool() ? "True" : "";
    if (value.is_number()) return value.as_double() == 0.0 ? "" : value.py_str();
    if (value.kind() == Json::Kind::String) return value.as_string();
    return value.py_str();
}

inline std::vector<std::string> slot_order(const Proposition& proposition) {
    const PredicateSpec* spec = predicate_catalog().find(proposition.predicate);
    if (spec && !spec->slots.empty()) return spec->slots;
    std::vector<std::string> names;
    for (const auto& entry : proposition.slots) names.push_back(entry.first);
    std::sort(names.begin(), names.end());
    return names;
}

inline bool looks_like(const Json& value, const std::string& prefix) {
    return value.kind() == Json::Kind::String
        && value.as_string().rfind(prefix, 0) == 0;
}

inline std::string kind_for(const std::vector<std::uint8_t>& seed,
                            const OrderedMap<double>& weights) {
    // `sum(max(0.0, w) for w in weights.values()) or 1.0` -- compensated, and
    // falling back to 1.0 when every weight is zero or negative.
    PySum total;
    for (const auto& entry : weights) total.add(std::max(0.0, entry.second));
    double denominator = total.value();
    if (denominator == 0.0) denominator = 1.0;

    double draw = seeded_uniform(seed) * denominator;
    double running = 0.0;
    for (const char* kind : {LEVELLING, SHARPENING, ASSIMILATION, INVERSION}) {
        running += std::max(0.0, weights.get(kind, 0.0));
        // `<=`, not `<`. UNOBSERVABLE in practice and ported faithfully anyway:
        // the two differ only when the draw lands exactly on a cumulative
        // boundary, and `draw` is `uniform * total` where uniform is a 64-bit
        // integer over 2^64. A mutation to `<` is not caught by any case here,
        // and inventing one that hits the boundary would be inventing a seed
        // rather than testing behaviour.
        if (draw <= running) return kind;
    }
    return LEVELLING;
}

/// Drop a detail. The FIRST slot is the subject of the claim and is kept:
/// losing it would not make the story vaguer, it would make it about nobody.
inline std::optional<std::pair<Proposition, Json>> level(
        const Proposition& proposition, const std::vector<std::uint8_t>& seed) {
    std::vector<std::string> order = slot_order(proposition);
    std::vector<std::string> droppable;
    for (std::size_t i = 1; i < order.size(); ++i) {
        const Json* value = proposition.slots.find(order[i]);
        if (value && !value->is_null()) droppable.push_back(order[i]);
    }
    if (droppable.empty()) return std::nullopt;

    std::size_t index = static_cast<std::size_t>(seeded_uniform(seed) * droppable.size())
                      % droppable.size();
    const std::string& name = droppable[index];
    Proposition out = proposition;
    Json lost = *out.slots.find(name);
    out.slots[name] = Json();

    Json why = Json::object();
    why["lost_detail"] = name;
    why["was"] = lost;
    return std::make_pair(out, why);
}

/// Quantities grow in the telling.
inline std::optional<std::pair<Proposition, Json>> sharpen(
        const Proposition& proposition, const std::vector<std::uint8_t>& seed) {
    // Insertion order, NOT catalogue order -- `proposition.slots.items()`.
    std::vector<std::string> numeric;
    for (const auto& entry : proposition.slots)
        if (looks_numeric(truthy_str(entry.second))) numeric.push_back(entry.first);

    if (!numeric.empty()) {
        std::size_t index = static_cast<std::size_t>(seeded_uniform(seed) * numeric.size())
                          % numeric.size();
        const std::string& name = numeric[index];
        std::string original = truthy_str(*proposition.slots.find(name));
        std::replace(original.begin(), original.end(), ',', '.');
        double grown = std::strtod(original.c_str(), nullptr) * SHARPEN_FACTOR;
        double was = std::strtod(original.c_str(), nullptr);

        std::string value;
        if (was == std::floor(was) && std::isfinite(was)) {
            // `str(int(grown))` -- Python's int() TRUNCATES toward zero.
            value = std::to_string(static_cast<long long>(grown));
        } else {
            char buffer[64];
            std::snprintf(buffer, sizeof buffer, "%.2f", grown);
            value = buffer;
        }
        Proposition out = proposition;
        Json before = *out.slots.find(name);
        out.slots[name] = Json(value);

        Json why = Json::object();
        why["exaggerated"] = name;
        why["from"] = before;
        why["to"] = value;
        return std::make_pair(out, why);
    }

    if (!proposition.degree.is_null()) {
        double degree = std::min(1.0, proposition.degree.as_double() * SHARPEN_FACTOR);
        Proposition out = proposition;
        Json before = out.degree;
        out.degree = Json(degree);
        Json why = Json::object();
        why["exaggerated"] = std::string("degree");
        why["from"] = before;
        why["to"] = degree;
        return std::make_pair(out, why);
    }
    return std::nullopt;
}

/// People the speaker knows best -- who they would confuse a stranger with.
inline std::vector<std::string> familiar_agents(const Agent& speaker, const World& world,
                                                const std::string& exclude) {
    std::vector<std::pair<double, std::string>> ranked;
    for (const auto& entry : speaker.relationships) {
        if (entry.first == exclude || entry.first == speaker.id) continue;
        if (!world.agents.contains(entry.first)) continue;
        ranked.emplace_back(entry.second.get("familiarity", 0.0)
                            + entry.second.get("liking", 0.0), entry.first);
    }
    // `sorted(..., reverse=True)` over (score, id) TUPLES: a tie is broken by
    // the id, descending. Not by insertion order -- this is one of the few
    // places in the runtime where the id itself decides an outcome.
    std::sort(ranked.begin(), ranked.end(),
              [](const auto& a, const auto& b) { return b < a; });

    std::vector<std::string> out;
    for (const auto& entry : ranked) {
        if (entry.first <= 0.0) continue;
        out.push_back(entry.second);
        if (out.size() == 3) break;
    }
    return out;
}

/// Places the speaker's own day takes them to.
inline std::vector<std::string> familiar_places(const Agent& speaker,
                                                const Routine* routine,
                                                const std::string& exclude) {
    std::vector<std::string> seen;
    if (routine) {
        for (const RoutineBlock& block : routine->blocks()) {
            if (block.place == exclude) continue;
            if (std::find(seen.begin(), seen.end(), block.place) != seen.end()) continue;
            seen.push_back(block.place);
        }
    }
    std::string here = speaker.location().is_null() ? "" : speaker.location().py_str();
    if (!here.empty() && here != exclude
        && std::find(seen.begin(), seen.end(), here) == seen.end())
        seen.push_back(here);
    if (seen.size() > 3) seen.resize(3);
    return seen;
}

/// The story drifts toward people and places the teller actually knows.
inline std::optional<std::pair<Proposition, Json>> assimilate(
        const Proposition& proposition, const Agent& speaker, const World& world,
        const Routine* routine, const std::vector<std::uint8_t>& seed) {
    struct Candidate {
        std::string name;
        std::vector<std::string> options;
        std::string category;
    };
    std::vector<Candidate> candidates;
    for (const auto& entry : proposition.slots) {
        if (looks_like(entry.second, "agent:")) {
            auto familiar = familiar_agents(speaker, world, entry.second.as_string());
            if (!familiar.empty()) candidates.push_back({entry.first, familiar, "person"});
        } else if (looks_like(entry.second, "place:")) {
            auto familiar = familiar_places(speaker, routine, entry.second.as_string());
            if (!familiar.empty()) candidates.push_back({entry.first, familiar, "place"});
        }
    }
    if (candidates.empty()) return std::nullopt;

    std::size_t index = static_cast<std::size_t>(seeded_uniform(seed) * candidates.size())
                      % candidates.size();
    const Candidate& chosen = candidates[index];
    std::vector<std::uint8_t> pick_seed = derive_seed(seed_hex(seed), chosen.name, 0, 0, "pick");
    std::size_t which = static_cast<std::size_t>(seeded_uniform(pick_seed) * chosen.options.size())
                      % chosen.options.size();

    Proposition out = proposition;
    Json was = *out.slots.find(chosen.name);
    out.slots[chosen.name] = Json(chosen.options[which]);

    Json why = Json::object();
    why["assimilated"] = chosen.name;
    why["category"] = chosen.category;
    why["was"] = was;
    why["became"] = chosen.options[which];
    return std::make_pair(out, why);
}

inline std::optional<std::pair<Proposition, Json>> apply(
        const std::string& kind, const Proposition& proposition, const Agent& speaker,
        const World& world, const Routine* routine,
        const std::vector<std::uint8_t>& seed) {
    if (kind == LEVELLING) return level(proposition, seed);
    if (kind == SHARPENING) return sharpen(proposition, seed);
    if (kind == ASSIMILATION) return assimilate(proposition, speaker, world, routine, seed);
    if (kind == INVERSION) {
        Json why = Json::object();
        why["note"] = std::string("retold as its own opposite");
        return std::make_pair(proposition.negated(), why);
    }
    return std::nullopt;
}

}  // namespace detail_

/// The distorted claim, or nothing when nothing changed.
///
/// Never returns a proposition the speaker is protecting: a character must not
/// leak a secret by accidentally garbling a different claim into it.
inline std::optional<Distortion> distort(
        const Proposition& proposition, const Agent& speaker, const World& world,
        const std::vector<std::uint8_t>& seed,
        const OrderedMap<double>* weights = nullptr,
        const std::vector<std::string>& protected_keys = {},
        const Routine* routine = nullptr) {
    OrderedMap<double> merged = default_distortion_weights();
    if (weights) for (const auto& entry : *weights) merged[entry.first] = entry.second;

    std::string first = detail_::kind_for(
        derive_seed(seed_hex(seed), "kind", 0, 0, "distortion"), merged);

    std::vector<std::string> order = {first};
    for (const char* kind : {LEVELLING, SHARPENING, ASSIMILATION, INVERSION})
        if (first != kind) order.push_back(kind);

    for (std::size_t attempt = 0; attempt < order.size(); ++attempt) {
        auto result = detail_::apply(
            order[attempt], proposition, speaker, world, routine,
            derive_seed(seed_hex(seed), order[attempt],
                        static_cast<long long>(attempt), 0, "distortion"));
        if (!result) continue;
        const Proposition& changed = result->first;
        if (changed.core_key() == proposition.core_key()
            && changed.polarity == proposition.polarity) continue;   // nothing changed
        if (std::find(protected_keys.begin(), protected_keys.end(), changed.core_key())
            != protected_keys.end()) continue;   // would garble a claim into a secret
        return Distortion{changed, order[attempt], result->second};
    }
    return std::nullopt;
}

/// One line an inspector or a designer can read.
inline std::string describe(const std::string& kind, const Json& detail) {
    auto field = [&](const char* name) {
        const Json* found = detail.find(name);
        return found ? found->py_str() : "None";
    };
    if (kind == LEVELLING)
        return "the " + field("lost_detail") + " was forgotten (was " + field("was") + ")";
    if (kind == SHARPENING)
        return field("exaggerated") + " grew from " + field("from") + " to " + field("to");
    if (kind == ASSIMILATION)
        return field("was") + " became " + field("became") + " — a "
             + field("category") + " the teller knows";
    if (kind == INVERSION) return "retold as its own opposite";
    return kind;
}

}  // namespace usc
