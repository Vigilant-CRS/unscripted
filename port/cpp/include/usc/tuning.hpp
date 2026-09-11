// `usc/tuning.py`. One place to change how a world behaves, without changing the
// runtime.
//
// Seventy-nine numbers decide how this simulation feels, and exactly one engine
// -- diffusion -- ever read any of them from a world pack. Every other constant
// lived in the source, so a studio that wanted a gossipier town, longer memories
// or rarer distortion had to edit the SDK. That is the wrong seam: a world pack
// is content, and HOW THIS WORLD WORKS is content too -- a mediaeval village and
// a surveillance state are not the same simulation with different names in it.
//
// THREE RULES, AND THE FIRST IS THE ONE THAT MATTERS.
//
// An unknown key is an ERROR, never a shrug. A tuning value silently ignored
// because it was misspelled is the worst failure this file could have: the world
// behaves as though nothing was set, the author believes it was, and the gap
// between them is invisible. Every name is checked, and a near miss is named
// back.
//
// Types are checked, because a string where a number belongs would either crash
// deep inside a tick or, worse, compare as something unexpected.
//
// And nothing here changes what is POSSIBLE, only how much. No amount of tuning
// makes a character know something they were never told.
//
// WHAT THIS PORT HAS TO DO DIFFERENTLY, AND WHY IT IS SAFE. Python reads
// `engine.params` as a dictionary and gets the parameter names for free. C++ has
// no reflection, so the names live in an explicit table below -- and an explicit
// table is exactly the kind of copy that drifts. So the probe compares this
// table, name by name and value by value, against the live Python dictionaries.
// A parameter added to an engine and forgotten here fails a test rather than
// becoming a knob that silently does nothing, which is the failure this module
// exists to prevent in the first place.
#pragma once

#include <algorithm>
#include <cctype>
#include <cmath>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/pystr.hpp"
#include "usc/ordered_map.hpp"

namespace usc {

/// Which runtime parts may be tuned, and what each governs. The text is for
/// `usc tune`, so an author does not have to read source to find out what a knob
/// does.
inline const OrderedMap<std::string>& tunable() {
    static const OrderedMap<std::string>* table = [] {
        auto* fresh = new OrderedMap<std::string>();
        (*fresh)["belief"] = "how much a source's word is worth, and how fast a "
                             "repeated rumour stops counting";
        (*fresh)["memory"] = "how long things stay reachable, how much is kept, "
                             "how much interferes";
        (*fresh)["affect"] = "how hard an event hits a mood and how fast it relaxes";
        (*fresh)["diffusion"] = "how often people meet and talk, how far a claim "
                                "travels, and how often a detail is lost";
        (*fresh)["pursuit"] = "how often somebody acts on a goal, and whom they "
                              "reach for";
        (*fresh)["contagion"] = "how much of a speaker's mood moves to the listener";
        (*fresh)["notes"] = "how long a note lies unread, and how likely the wrong "
                            "person finds it";
        (*fresh)["promises"] = "how long a promise has, and what counts as keeping it";
        (*fresh)["common_knowledge"] = "how big a crowd has to be, and how public "
                                       "a place";
        (*fresh)["policy"] = "how decisively characters choose between options";
        (*fresh)["relationship"] = "how fast trust is gained and lost";
        (*fresh)["reputation"] = "how fast a reputation moves and fades";
        (*fresh)["identity"] = "what decides which identity somebody leads with";
        (*fresh)["socioling"] = "how strongly register follows education, role and mood";
        return fresh;
    }();
    return *table;
}

/// A permitted range, and whether each end is open.
///
/// The endpoints are held as JSON rather than as doubles, because the message
/// prints them and Python prints `0` for an int bound and `0.0` for a float one.
/// The table below is authored with both -- a count is an int, a probability is
/// a float -- and flattening that would change what an author reads.
struct Bound {
    Json low = Json(0.0);
    Json high;                 // null when unbounded
    bool low_open = false;
    bool high_open = false;
};

/// Where a value would crash the runtime or mean nothing. Deliberately loose
/// elsewhere: the point of this surface is that a studio can build a world that
/// does not resemble the reference packs.
inline const std::map<std::pair<std::string, std::string>, Bound>& tuning_ranges() {
    static const std::map<std::pair<std::string, std::string>, Bound>* table = [] {
        auto* fresh = new std::map<std::pair<std::string, std::string>, Bound>();
        auto set = [&](const char* engine, const char* key, Json low, Json high,
                       bool low_open, bool high_open) {
            (*fresh)[{engine, key}] = Bound{low, high, low_open, high_open};
        };
        const Json none;
        // A source's credibility is a probability, and the log-odds update takes
        // log(k / (1 - k)): neither endpoint exists.
        set("belief", "kappa_min", 0.0, 1.0, true, true);
        set("belief", "kappa_max", 0.0, 1.0, true, true);
        set("belief", "rho_correlated", 0.0, 1.0, false, true);
        set("belief", "provenance_limit", Json(1LL), none, false, false);
        // Time constants divide.
        set("affect", "tau_mood", 0.0, none, true, false);
        set("affect", "tau_emotion", 0.0, none, true, false);
        // Caps of zero silently discard everything they cap, which looks exactly
        // like a layer being broken.
        set("memory", "episodic_cap", Json(1LL), none, false, false);
        set("memory", "total_cap", Json(1LL), none, false, false);
        set("memory", "working_cap", Json(1LL), none, false, false);
        set("memory", "presentation_window", Json(1LL), none, false, false);
        set("notes", "max_per_place", Json(1LL), none, false, false);
        set("notes", "lifetime_minutes", Json(0LL), none, true, false);
        set("promises", "max_open_per_agent", Json(1LL), none, false, false);
        set("promises", "horizon_minutes", Json(0LL), none, true, false);
        set("pursuit", "interval_minutes", 0.0, none, true, false);
        set("diffusion", "max_hops", Json(1LL), none, false, false);
        set("diffusion", "bystanders", Json(0LL), none, false, false);
        set("diffusion", "fidelity_decay", 0.0, 1.0, true, false);
        set("diffusion", "distortion_prob", 0.0, 1.0, false, false);
        set("diffusion", "stifle_prob", 0.0, 1.0, false, false);
        set("diffusion", "min_confidence_to_tell", 0.0, 1.0, false, false);
        set("diffusion", "encounters_per_hour", 0.0, none, false, false);
        set("contagion", "transfer", 0.0, 1.0, false, false);
        set("contagion", "max_step", 0.0, 1.0, true, false);
        set("contagion", "min_tie", 0.0, none, false, false);
        // Two people who both know a thing are a conversation, not a crowd.
        // Three is the smallest honest number and the module says why; two is
        // the hard floor below which the word stops meaning anything.
        set("common_knowledge", "min_witnesses", Json(2LL), none, false, false);
        set("common_knowledge", "public_privacy", 0.0, 1.0, false, false);
        set("common_knowledge", "min_quality", 0.0, 1.0, false, false);
        set("promises", "kept_margin", 0.0, 1.0, false, false);
        set("pursuit", "min_confidence", 0.0, 1.0, false, false);
        set("pursuit", "max_per_tick", Json(0LL), none, false, false);
        set("policy", "temperature", 0.0, none, true, false);
        set("relationship", "eta_up", 0.0, none, false, false);
        set("relationship", "eta_down", 0.0, none, false, false);
        return fresh;
    }();
    return *table;
}

/// A tuning block that cannot be applied, naming what is wrong with it.
class TuningError : public std::invalid_argument {
public:
    explicit TuningError(const std::string& what) : std::invalid_argument(what) {}
};

/// The live parameters, engine by engine.
///
/// The stand-in for `getattr(core, name).params`. A caller fills it from the
/// engines it actually constructed, so a build without a layer simply has no
/// entry for it -- which is what `check` warns about rather than refusing.
using ParameterTable = OrderedMap<OrderedMap<Json>>;

namespace tuning_detail {

/// `type(value).__name__` -- the name Python would print.
///
/// Part of the message, not decoration: "must be a number, not a str" tells an
/// author they quoted a value, and "must be a number" leaves them guessing.
inline std::string py_type_name(const Json& value) {
    switch (value.kind()) {
        case Json::Kind::Null:   return "NoneType";
        case Json::Kind::Bool:   return "bool";
        case Json::Kind::Int:    return "int";
        case Json::Kind::Real:   return "float";
        case Json::Kind::String: return "str";
        case Json::Kind::Array:  return "list";
        case Json::Kind::Object: return "dict";
    }
    return "object";
}

/// `f"{low}"` for a bound that may have been written as an int or a float.
inline std::string number_text(double value) {
    if (value == std::floor(value) && std::fabs(value) < 1e15) {
        // Python prints an int bound as `1` and a float bound as `1.0`, and the
        // table above is written with both. The ranges that are conceptually
        // counts were authored as ints, so they print without a decimal point.
        return std::to_string(static_cast<long long>(value));
    }
    return Json::repr_double(value);
}

inline std::string range_text(const Bound& bound) {
    std::string left = (bound.low_open ? "greater than " : "at least ")
                     + bound.low.py_str();
    if (bound.high.is_null()) return left;
    std::string right = (bound.high_open ? "less than " : "at most ")
                      + bound.high.py_str();
    return left + " and " + right;
}

/// A "did you mean" for the commonest kind of mistake, which is a typo.
inline std::string near(const std::string& name,
                        const std::vector<std::string>& known) {
    std::string lowered = py_lower(name);
    std::replace(lowered.begin(), lowered.end(), '-', '_');

    std::vector<std::string> close;
    for (const std::string& candidate : known) {
        std::string other = py_lower(candidate);
        if (other.rfind(lowered.substr(0, 4), 0) == 0
            || lowered.rfind(other.substr(0, 4), 0) == 0)
            close.push_back(candidate);
    }
    if (close.empty()) return "";
    std::sort(close.begin(), close.end());
    if (close.size() > 3) close.resize(3);
    std::string joined;
    for (std::size_t i = 0; i < close.size(); ++i) {
        if (i) joined += ", ";
        joined += close[i];
    }
    return " Did you mean " + joined + "?";
}

inline std::string joined_sorted(const std::vector<std::string>& names) {
    std::vector<std::string> sorted = names;
    std::sort(sorted.begin(), sorted.end());
    std::string out;
    for (std::size_t i = 0; i < sorted.size(); ++i) {
        if (i) out += ", ";
        out += sorted[i];
    }
    return out;
}

inline std::vector<std::string> keys_of(const ParameterTable& table) {
    std::vector<std::string> names;
    for (const auto& entry : table) names.push_back(entry.first);
    return names;
}

inline std::vector<std::string> keys_of(const OrderedMap<Json>& table) {
    std::vector<std::string> names;
    for (const auto& entry : table) names.push_back(entry.first);
    return names;
}

}  // namespace tuning_detail

/// Validate a tuning block against a live parameter table. Returns warnings.
///
/// Throws on anything that would NOT take effect, which is the whole point:
/// silence here is indistinguishable from success.
inline std::vector<std::string> check(const Json& tuning, const ParameterTable& core) {
    if (tuning.kind() != Json::Kind::Object)
        throw TuningError("'tuning' must be an object, not a "
                          + tuning_detail::py_type_name(tuning));

    std::vector<std::string> tunable_names;
    for (const auto& entry : tunable()) tunable_names.push_back(entry.first);

    std::vector<std::string> warnings;
    for (const auto& block : tuning.fields()) {
        const std::string& engine_name = block.first;
        if (!tunable().contains(engine_name))
            throw TuningError("'tuning." + engine_name + "' is not a tunable part "
                              "of the runtime."
                              + tuning_detail::near(engine_name, tunable_names)
                              + " Tunable: "
                              + tuning_detail::joined_sorted(tunable_names) + ".");
        const OrderedMap<Json>* params = core.find(engine_name);
        if (!params) {
            warnings.push_back("tuning." + engine_name + ": this build has no "
                               "parameters for it; ignored");
            continue;
        }
        if (block.second.kind() != Json::Kind::Object)
            throw TuningError("'tuning." + engine_name + "' must be an object, not a "
                              + tuning_detail::py_type_name(block.second));

        std::vector<std::string> param_names = tuning_detail::keys_of(*params);
        for (const auto& setting : block.second.fields()) {
            const std::string& key = setting.first;
            const Json* current = params->find(key);
            if (!current)
                throw TuningError("'tuning." + engine_name + "." + key + "' is not "
                                  "a parameter of " + engine_name + "."
                                  + tuning_detail::near(key, param_names)
                                  + " It has: "
                                  + tuning_detail::joined_sorted(param_names) + ".");

            bool current_is_bool = current->kind() == Json::Kind::Bool;
            bool value_is_bool = setting.second.kind() == Json::Kind::Bool;
            if (current_is_bool && !value_is_bool)
                throw TuningError("'tuning." + engine_name + "." + key
                                  + "' must be true or false");
            if (!current_is_bool && current->is_number()) {
                if (value_is_bool || !setting.second.is_number())
                    throw TuningError("'tuning." + engine_name + "." + key
                                      + "' must be a number, not a "
                                      + tuning_detail::py_type_name(setting.second));
                auto bound = tuning_ranges().find({engine_name, key});
                if (bound != tuning_ranges().end()) {
                    double value = setting.second.as_double();
                    const Bound& limit = bound->second;
                    double low = limit.low.as_double();
                    bool too_low = limit.low_open ? value <= low : value < low;
                    bool too_high = !limit.high.is_null()
                        && (limit.high_open ? value >= limit.high.as_double()
                                            : value > limit.high.as_double());
                    if (too_low || too_high)
                        throw TuningError(
                            "'tuning." + engine_name + "." + key + "' is "
                            + setting.second.py_str() + "; it must be "
                            + tuning_detail::range_text(limit)
                            + ". Outside that it either crashes the runtime or "
                              "means nothing.");
                }
            }
        }
    }
    return warnings;
}

using TuningReason = Reason;

/// Apply a validated tuning block. Returns one reason per change.
///
/// Applied AFTER every engine is constructed, so a pack overrides the default
/// rather than racing it -- and the trace records what the world asked for, so a
/// scene behaving oddly does not require diffing a JSON file against the source.
inline std::vector<TuningReason> apply(ParameterTable& core, const Json& tuning) {
    if (tuning.kind() != Json::Kind::Object || tuning.fields().empty()) return {};
    check(tuning, core);

    std::vector<std::string> engines;
    for (const auto& entry : tuning.fields()) engines.push_back(entry.first);
    std::sort(engines.begin(), engines.end());

    std::vector<TuningReason> reasons;
    for (const std::string& engine_name : engines) {
        OrderedMap<Json>* params = core.find(engine_name);
        if (!params) continue;
        const Json& values = tuning.at(engine_name);
        std::vector<std::string> keys;
        for (const auto& entry : values.fields()) keys.push_back(entry.first);
        std::sort(keys.begin(), keys.end());

        for (const std::string& key : keys) {
            Json* slot = params->find(key);
            if (!slot) continue;
            Json was = *slot;
            *slot = values.at(key);
            // `was != value` -- and 1 and 1.0 compare EQUAL in Python, so a
            // pack restating an integer default as a float records no change.
            bool same = was.dump() == slot->dump()
                     || (was.is_number() && slot->is_number()
                         && was.as_double() == slot->as_double());
            if (same) continue;
            Json detail = Json::object();
            detail["engine"] = engine_name;
            detail["parameter"] = key;
            detail["default"] = was;
            detail["authored"] = *slot;
            reasons.push_back({"tuning.applied", 1.0, detail});
        }
    }
    return reasons;
}

/// Every knob, its current value and what its engine governs.
inline Json describe(const ParameterTable& core) {
    Json rows = Json::array();
    std::vector<std::string> engines;
    for (const auto& entry : tunable()) engines.push_back(entry.first);
    std::sort(engines.begin(), engines.end());

    for (const std::string& engine_name : engines) {
        const OrderedMap<Json>* params = core.find(engine_name);
        if (!params) continue;
        Json row = Json::object();
        row["engine"] = engine_name;
        row["governs"] = tunable().get(engine_name);
        std::vector<std::string> keys = tuning_detail::keys_of(*params);
        std::sort(keys.begin(), keys.end());
        Json values = Json::object();
        for (const std::string& key : keys) values.fields()[key] = *params->find(key);
        row["parameters"] = values;
        rows.push(row);
    }
    return rows;
}

}  // namespace usc
