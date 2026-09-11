// `usc/ontology.py`. Typed propositions, the predicate catalogue, and the
// contradiction logic.
//
// The part that has to be exactly right is `core_key()`, because it is the
// identity a belief is filed under. Two implementations that build it
// differently do not disagree slightly -- they disagree about whether they are
// discussing the same claim, and every later number is then computed about
// something else.
//
// Three ways to get it wrong, all avoided here on purpose:
//   - slot order. Taken from the catalogue, not from the slot map, and falling
//     back to *sorted* names when the predicate is unknown -- which is what
//     Python's `sorted(self.slots)` does.
//   - a missing slot. `self.slots.get(s)` gives `None`, and the f-string writes
//     `None`, not an empty string.
//   - the qualifier suffix, which writes `None` for each absent field rather
//     than omitting it.
#pragma once

#include <algorithm>
#include <cmath>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/ordered_map.hpp"

namespace usc {

struct PredicateSpec {
    std::vector<std::string> slots;
    /// Index of the slot the others functionally determine, or none.
    std::optional<int> functional_in;

    /// What a pack's `canon.json` declares. Everything but the slots is optional
    /// -- a predicate that only names its slots is a complete declaration.
    static PredicateSpec from_json(const Json& doc) {
        PredicateSpec out;
        const Json* slots = doc.find("slots");
        if (slots) for (const Json& one : slots->items())
            out.slots.push_back(one.py_str());
        const Json* functional = doc.find("functional_in");
        if (functional && !functional->is_null())
            out.functional_in = static_cast<int>(functional->as_int());
        return out;
    }
};

/// Domain-neutral predicates that ship with the engine. Anything specific to
/// one world is registered from its pack at load time.
inline OrderedMap<PredicateSpec>& predicate_catalog() {
    static OrderedMap<PredicateSpec>* catalog = [] {
        auto* fresh = new OrderedMap<PredicateSpec>();
        (*fresh)["space:exactly_at"]        = {{"entity", "place"}, 1};
        (*fresh)["core:holds_role"]         = {{"agent", "role", "context"}, std::nullopt};
        (*fresh)["body:alive"]              = {{"agent"}, std::nullopt};
        (*fresh)["economy:owes_amount"]     = {{"debtor", "creditor", "amount"}, std::nullopt};
        (*fresh)["looking_for"]             = {{"seeker", "target"}, std::nullopt};
        (*fresh)["was_at"]                  = {{"agent", "place", "when"}, std::nullopt};
        (*fresh)["place:has_surveillance"]  = {{"place", "level"}, 1};
        (*fresh)["place:has_privacy"]       = {{"place", "level"}, 1};
        (*fresh)["place:has_noise"]         = {{"place", "level"}, 1};
        return fresh;
    }();
    return *catalog;
}

/// Where each non-core predicate came from, for error messages.
inline OrderedMap<std::string>& predicate_sources() {
    static auto* sources = new OrderedMap<std::string>();
    return *sources;
}

/// The names that ship with the engine, so `reset_predicates` knows what to keep.
inline const std::vector<std::string>& core_predicate_names() {
    static const std::vector<std::string> names = {
        "space:exactly_at", "core:holds_role", "body:alive", "economy:owes_amount",
        "looking_for", "was_at", "place:has_surveillance", "place:has_privacy",
        "place:has_noise"};
    return names;
}

/// Add a pack-declared predicate to the schema.
///
/// Idempotent for an identical definition, and it THROWS when a pack redefines
/// one incompatibly. That is not pedantry: slot order determines the canonical
/// core key a belief is filed under, so two packs silently disagreeing about a
/// predicate's shape would make their worlds' beliefs unmergeable, and the
/// symptom would appear far from the cause.
inline void register_predicate(const std::string& name, const PredicateSpec& spec,
                               const std::string& source = "world pack") {
    if (spec.slots.empty())
        throw std::invalid_argument("Predicate '" + name + "' from " + source
                                    + " declares no slots.");
    const PredicateSpec* existing = predicate_catalog().find(name);
    if (existing != nullptr
        && (existing->slots != spec.slots
            || existing->functional_in != spec.functional_in)) {
        const std::vector<std::string>& core = core_predicate_names();
        bool is_core = std::find(core.begin(), core.end(), name) != core.end();
        std::string origin = is_core ? "the engine core"
                                     : predicate_sources().get(name, "?");
        throw std::invalid_argument(
            "Predicate '" + name + "' from " + source + " conflicts with the "
            "definition from " + origin + ". Slot order defines the canonical "
            "proposition key, so the two cannot coexist.");
    }
    predicate_catalog()[name] = spec;
    const std::vector<std::string>& core = core_predicate_names();
    if (std::find(core.begin(), core.end(), name) == core.end())
        predicate_sources()[name] = source;
}

inline void register_predicates(const OrderedMap<PredicateSpec>& specs,
                                const std::string& source = "world pack") {
    for (const auto& entry : specs) register_predicate(entry.first, entry.second, source);
}

/// Drop pack-registered predicates, keeping the engine core. For tests.
inline void reset_predicates() {
    OrderedMap<PredicateSpec> kept;
    for (const std::string& name : core_predicate_names()) {
        const PredicateSpec* spec = predicate_catalog().find(name);
        if (spec) kept[name] = *spec;
    }
    predicate_catalog() = kept;
    predicate_sources().clear();
}

/// Declared mutually exclusive cores (C3).
inline const std::vector<std::pair<std::pair<std::string, std::string>,
                                   std::pair<std::string, std::string>>>& mutex_pairs() {
    static const std::vector<std::pair<std::pair<std::string, std::string>,
                                       std::pair<std::string, std::string>>> pairs = {
        {{"body:alive", "+"}, {"body:alive", "-"}}};
    return pairs;
}

/// Graded relevance across related predicates. 0 means the same predicate.
inline const std::map<std::pair<std::string, std::string>, int>& taxonomy_distance() {
    static const std::map<std::pair<std::string, std::string>, int> distances = {
        {{"was_at", "space:exactly_at"}, 1}};
    return distances;
}

struct Proposition {
    std::string predicate;
    OrderedMap<Json> slots;
    std::string polarity = "+";
    Json valid_start;                 // null when absent
    Json valid_end;
    Json spatial;
    Json degree;

    /// Slot names in catalogue order, or sorted when the predicate is unknown.
    std::vector<std::string> slot_names() const {
        const PredicateSpec* spec = predicate_catalog().find(predicate);
        if (spec && !spec->slots.empty()) return spec->slots;
        std::vector<std::string> names;
        for (const auto& entry : slots) names.push_back(entry.first);
        std::sort(names.begin(), names.end());     // Python's sorted(self.slots)
        return names;
    }

    /// Everything but polarity, canonically. The key a belief is stored under.
    std::string core_key() const {
        std::string out = predicate + "(";
        bool first = true;
        for (const std::string& name : slot_names()) {
            if (!first) out += ",";
            first = false;
            const Json* value = slots.find(name);
            out += name + "=" + (value ? value->py_str() : std::string("None"));
        }
        out += ")[" + valid_start.py_str() + "," + valid_end.py_str() + ","
             + spatial.py_str() + "]";
        return out;
    }

    std::string key() const { return polarity + core_key(); }

    Proposition negated() const {
        Proposition other = *this;
        other.polarity = (polarity == "+") ? "-" : "+";
        return other;
    }

    /// `Proposition.__str__`. Iterates the slot map in INSERTION order, not
    /// catalogue order -- unlike `core_key()`, which uses the catalogue. The
    /// difference is real and is preserved rather than tidied away: this string
    /// goes into reason traces, and making the two agree would change output
    /// the Python side produces today.
    std::string str() const {
        std::string args;
        bool first = true;
        for (const auto& entry : slots) {
            if (!first) args += ", ";
            first = false;
            args += entry.first + "=" + entry.second.py_str();
        }
        std::string sign = (polarity == "+") ? "" : "NOT ";
        return sign + predicate + "(" + args + ")";
    }

    Json as_json() const {
        Json out = Json::object();
        out["predicate"] = predicate;
        Json slot_map = Json::object();
        for (const auto& entry : slots) slot_map.fields()[entry.first] = entry.second;
        out["slots"] = slot_map;
        out["polarity"] = polarity;
        out["valid_start"] = valid_start;
        out["valid_end"] = valid_end;
        out["spatial"] = spatial;
        out["degree"] = degree;
        return out;
    }

    static Proposition from_json(const Json& doc) {
        Proposition out;
        out.predicate = doc.get("predicate").as_string();
        const Json* slot_map = doc.find("slots");
        if (slot_map) for (const auto& entry : slot_map->fields())
            out.slots[entry.first] = entry.second;
        const Json* polarity = doc.find("polarity");
        out.polarity = (polarity && !polarity->is_null()) ? polarity->as_string() : "+";
        out.valid_start = doc.get("valid_start");
        out.valid_end = doc.get("valid_end");
        out.spatial = doc.get("spatial");
        out.degree = doc.get("degree");
        return out;
    }
};

inline bool qualifiers_overlap(const Proposition& a, const Proposition& b) {
    if (!a.spatial.is_null() && !b.spatial.is_null()
        && a.spatial.py_str() != b.spatial.py_str()) return false;
    if (!a.valid_start.is_null() && !a.valid_end.is_null()
        && !b.valid_start.is_null() && !b.valid_end.is_null()) {
        if (a.valid_end.as_double() < b.valid_start.as_double()) return false;
        if (b.valid_end.as_double() < a.valid_start.as_double()) return false;
    }
    return true;
}

/// "C1", "C2", "C3" or "" for no contradiction.
inline std::string contradicts(const Proposition& a, const Proposition& b) {
    if (!qualifiers_overlap(a, b)) return "";
    if (a.core_key() == b.core_key() && a.polarity != b.polarity) return "C1";

    const PredicateSpec* spec = predicate_catalog().find(a.predicate);
    if (spec && spec->functional_in.has_value() && a.predicate == b.predicate
        && a.polarity == "+" && b.polarity == "+") {
        int value_index = *spec->functional_in;
        const std::vector<std::string>& names = spec->slots;
        if (value_index >= 0 && value_index < static_cast<int>(names.size())) {
            bool keys_agree = true;
            for (int i = 0; i < static_cast<int>(names.size()); ++i) {
                if (i == value_index) continue;
                const Json* one = a.slots.find(names[i]);
                const Json* two = b.slots.find(names[i]);
                std::string left = one ? one->py_str() : "None";
                std::string right = two ? two->py_str() : "None";
                if (left != right) { keys_agree = false; break; }
            }
            if (keys_agree) {
                const Json* one = a.slots.find(names[value_index]);
                const Json* two = b.slots.find(names[value_index]);
                std::string left = one ? one->py_str() : "None";
                std::string right = two ? two->py_str() : "None";
                if (left != right) return "C2";
            }
        }
    }

    for (const auto& pair : mutex_pairs()) {
        if (a.predicate == pair.first.first && a.polarity == pair.first.second
            && b.predicate == pair.second.first && b.polarity == pair.second.second) {
            // Same primary entity: the FIRST slot in insertion order, which is
            // what `list(a.slots.values())[:1]` takes.
            const auto* one = a.slots.first();
            const auto* two = b.slots.first();
            std::string left = one ? one->second.py_str() : std::string();
            std::string right = two ? two->second.py_str() : std::string();
            bool both_empty = !one && !two;
            if (both_empty || (one && two && left == right)) return "C3";
        }
    }
    return "";
}

inline double predicate_similarity(const std::string& a, const std::string& b,
                                   double lambda = 0.7) {
    if (a == b) return 1.0;
    const auto& distances = taxonomy_distance();
    auto found = distances.find({a, b});
    if (found == distances.end()) found = distances.find({b, a});
    if (found == distances.end()) return 0.0;
    return std::exp(-lambda * found->second);
}

inline double relevance(const Proposition& prop, const Proposition& topic,
                        double beta = 0.5) {
    double similarity = predicate_similarity(prop.predicate, topic.predicate);
    if (similarity == 0.0) return 0.0;

    std::vector<std::string> names;
    const PredicateSpec* spec = predicate_catalog().find(topic.predicate);
    if (spec && !spec->slots.empty()) {
        names = spec->slots;
    } else {
        // `list(topic.slots)` -- insertion order, NOT sorted. Different from
        // the fallback in `core_key()`, and deliberately so.
        for (const auto& entry : topic.slots) names.push_back(entry.first);
    }

    double argmatch = 1.0;
    if (!names.empty()) {
        double score = 0.0;
        for (const std::string& name : names) {
            const Json* wanted = topic.slots.find(name);
            if (!wanted || wanted->is_null()) { score += beta; continue; }   // wildcard
            const Json* have = prop.slots.find(name);
            if (have && have->py_str() == wanted->py_str()) score += 1.0;
        }
        argmatch = score / static_cast<double>(names.size());
    }

    double qualmatch = 1.0;
    if (!topic.spatial.is_null() && !prop.spatial.is_null()
        && topic.spatial.py_str() != prop.spatial.py_str()) qualmatch = 0.0;
    return similarity * argmatch * qualmatch;
}

}  // namespace usc
