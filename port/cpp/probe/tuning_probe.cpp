// Dump every tunable parameter the C++ runtime exposes, and what a tuning block
// does to them. Read by `tuning_probe.py`, which computes the same thing in
// Python and compares name for name, order for order and value for value.
//
// It exists because the binding in `knob.hpp` is an explicit list of names, and
// an explicit list is exactly the kind of copy that drifts. A parameter added to
// an engine and forgotten in its `knobs()` table would otherwise become a knob a
// pack sets in vain -- which is the failure `tuning.py` was written to prevent,
// and which this port had for as long as the block reached no engine at all.
#include <cstdio>
#include <string>

#include "usc/json.hpp"
#include "usc/sdk.hpp"
#include "usc/tuning_bind.hpp"

namespace {

/// The table as JSON, with the engines and their knobs in declaration order --
/// the order is part of what is compared, not incidental to it.
usc::Json as_json(const usc::ParameterTable& table) {
    usc::Json out = usc::Json::object();
    for (const auto& engine : table) {
        usc::Json values = usc::Json::object();
        for (const auto& one : engine.second) values[one.first] = one.second;
        out[engine.first] = values;
    }
    return out;
}

usc::Json reasons_as_json(const std::vector<usc::TuningReason>& reasons) {
    usc::Json out = usc::Json::array();
    // `Reason::as_json` is the Python tuple, which is what a trace exports and
    // therefore what must be compared -- not a shape invented for this probe.
    for (const usc::TuningReason& one : reasons) out.push(one.as_json());
    return out;
}

}  // namespace

int main(int argc, char** argv) {
    usc::World world;

    // Second argument, when present, is a tuning block to apply. Without it the
    // probe reports the defaults, which is the comparison that catches a
    // forgotten binding.
    usc::Json block;
    if (argc > 1) block = usc::Json::parse(argv[1]);
    world.tuning = block.is_null() ? usc::Json::object() : block;

    usc::RuntimeConfig config;
    usc::UnscriptedRuntime runtime(config, world);

    usc::Json out = usc::Json::object();
    out["parameters"] = as_json(usc::tuning_parameters(runtime.core));
    const std::vector<usc::TuningReason>* trace =
        runtime.core.last_traces.find("_tuning");
    out["reasons"] = trace ? reasons_as_json(*trace) : usc::Json::array();
    std::printf("%s\n", out.dump().c_str());
    return 0;
}
