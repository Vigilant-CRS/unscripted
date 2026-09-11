// Where a pack's `tuning` block stops being a table and becomes the engines.
//
// `tuning.hpp` ports the VALIDATION and the arithmetic, and it does so against a
// `ParameterTable` -- a map of names to numbers -- because that is the shape
// Python works in: `engine.params` IS the engine's storage, so writing the map
// changes the engine and nothing further is needed.
//
// C++ has no reflection, so for a long time this port validated a tuning block
// correctly and then dropped it: the table was never filled from the engines and
// never written back. A knob an author sets, believes in, and that does nothing
// is precisely the failure `tuning.py` was written to prevent, so the gap was
// worse than a missing feature.
//
// This closes it. `tuning_parameters()` reads the live engines into the table
// `check` and `apply` already understand; `tuning_write_back()` puts the result
// where it does something. The names come from each engine's own `knobs()` table, which sits
// beside the `Params` it describes -- see `knob.hpp` for why there rather than
// here -- and a probe holds every one of them against the live Python
// dictionary, so a parameter added to an engine and forgotten cannot become a
// knob that silently does nothing.
//
// ONE DELIBERATE DIFFERENCE, AND IT IS NOT A SHORTCUT. Python stores whatever
// JSON handed it: `provenance_limit: 7.0` leaves a float in the dictionary. This
// port narrows to the member's type, so it stores 7. Everywhere the value is
// compared or added -- which is every count but two -- those are the same
// number and behave identically. The two exceptions are `notes.max_per_place`
// and `promises.max_open_per_agent`, which Python uses as SLICE bounds: a
// non-integral float raises `TypeError` mid-tick there, while this port truncates
// and carries on. Reproducing a Python crash is not worth porting, and
// `tuning.check` arguably ought to refuse a fractional count on both sides --
// that would be a change to the reference, not to this file, so it is written
// down here rather than done quietly.
#pragma once

#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/knob.hpp"
#include "usc/ordered_map.hpp"
#include "usc/runtime.hpp"
#include "usc/tuning.hpp"

namespace usc {

/// The live parameters of every tunable engine, in the order `tunable()`
/// declares them.
///
/// The stand-in for Python's `getattr(core, name).params`, and the order matters
/// for the same reason it matters there: a dictionary that reorders its keys
/// exports a different state.
inline ParameterTable tuning_parameters(const Runtime& core) {
    ParameterTable table;
    table["belief"]           = read_params(core.belief);
    table["memory"]           = read_params(core.memory);
    table["affect"]           = read_params(core.affect);
    table["diffusion"]        = read_params(core.diffusion);
    table["pursuit"]          = read_params(core.pursuit);
    table["contagion"]        = read_params(core.contagion);
    table["notes"]            = read_params(core.notes);
    table["promises"]         = read_params(core.promises);
    table["common_knowledge"] = read_params(core.common_knowledge);
    table["policy"]           = read_params(core.policy);
    table["relationship"]     = read_params(core.relationship);
    table["reputation"]       = read_params(core.reputation);
    table["identity"]         = read_params(core.identity);
    table["socioling"]        = read_params(core.socioling);
    return table;
}

/// Put a table back into the engines it was read from.
inline void tuning_write_back(Runtime& core, const ParameterTable& table) {
    auto put = [&table](const char* name, auto& engine) {
        const OrderedMap<Json>* values = table.find(name);
        if (values) write_params(engine, *values);
    };
    put("belief", core.belief);
    put("memory", core.memory);
    put("affect", core.affect);
    put("diffusion", core.diffusion);
    put("pursuit", core.pursuit);
    put("contagion", core.contagion);
    put("notes", core.notes);
    put("promises", core.promises);
    put("common_knowledge", core.common_knowledge);
    put("policy", core.policy);
    put("relationship", core.relationship);
    put("reputation", core.reputation);
    put("identity", core.identity);
    put("socioling", core.socioling);
}

/// Validate a pack's tuning block and apply it to a live runtime.
///
/// The whole point of the file, in one call, and it is `tuning.apply` in Python:
/// nothing here re-implements the rules -- `check` still throws on anything that
/// would not take effect, `apply` still decides what changed and in what order,
/// and this only carries the values in and out. Returns one reason per change,
/// for the trace, so a scene behaving oddly does not need somebody to diff a
/// JSON file against the source of the runtime.
inline std::vector<TuningReason> apply_tuning(Runtime& core, const Json& block) {
    if (block.is_null() || !block.truthy()) return {};
    ParameterTable table = tuning_parameters(core);
    std::vector<TuningReason> reasons = apply(table, block);
    tuning_write_back(core, table);
    return reasons;
}

}  // namespace usc
