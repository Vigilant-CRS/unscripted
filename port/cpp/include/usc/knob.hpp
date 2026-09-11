// How a tuning value reaches the engine it names.
//
// THE PROBLEM THIS SOLVES, STATED PLAINLY. Python applies a pack's `tuning`
// block by writing into `engine.params`, which IS the engine's storage: writing
// the dictionary changes the engine, and no binding is needed anywhere. C++ has
// no reflection. Each engine holds its parameters as typed members, so something
// has to say "the name `kappa0` means this member of that struct" -- and until
// it did, a `tuning` block was validated in C++ and then quietly went nowhere.
// That is the exact failure `tuning.py` exists to prevent: a knob an author sets
// and believes in, that does nothing.
//
// WHY THE TABLE LIVES BESIDE THE STRUCT, NOT IN ONE CENTRAL FILE. An explicit
// list of names is a copy, and a copy drifts. The mitigation is twofold: the
// list sits directly under the `Params` it describes, so adding a field and
// forgetting the knob is visible on one screen; and a probe compares every
// binding, name by name and value by value, against the live Python dictionary,
// so a forgotten one fails a test rather than becoming a knob that silently does
// nothing. This header holds only the mechanism, and includes no engine, so
// every engine can include it without a cycle.
//
// WHAT A KNOB MAY BE. Four kinds, because that is what Python has: a float, an
// integer, a boolean, and one table of weights (`diffusion.distortion_weights`).
// Nothing else is tunable, and a fifth kind should be added here rather than
// worked around at a call site.
#pragma once

#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/ordered_map.hpp"

namespace usc {

/// One tunable value of one engine: its name, and how to reach it in a live
/// `Params`. Exactly one of the member pointers is set.
template <class P>
struct Knob {
    const char* name = nullptr;
    double P::* real = nullptr;
    long long P::* whole = nullptr;
    bool P::* flag = nullptr;
    OrderedMap<double> P::* table = nullptr;

    /// The current value, as `engine.params[name]` would read in Python.
    Json read(const P& params) const {
        if (real)  return Json(params.*real);
        if (whole) return Json(params.*whole);
        if (flag)  return Json(params.*flag);
        if (table) {
            // Python's default is None, and a None default is what the runtime
            // reads as "use the built-in weights". An empty map means the same
            // thing here, so it reports as null rather than as an empty object:
            // `check` must see what Python would see.
            const OrderedMap<double>& weights = params.*table;
            if (weights.empty()) return Json();
            Json out = Json::object();
            for (const auto& one : weights) out[one.first] = Json(one.second);
            return out;
        }
        return Json();
    }

    /// Overwrite it from a value the validator has already accepted.
    ///
    /// The narrowing is deliberate and matches Python: a knob declared as a
    /// count takes `12` and `12.0` alike, because JSON does not distinguish
    /// them and an author writing `12.0` means twelve.
    void write(P& params, const Json& value) const {
        if (real)  { params.*real = value.as_double(params.*real); return; }
        if (whole) { params.*whole = value.kind() == Json::Kind::Real
                         ? static_cast<long long>(value.as_double())
                         : value.as_int(params.*whole); return; }
        if (flag)  { params.*flag = value.as_bool(params.*flag); return; }
        if (table) {
            OrderedMap<double>& weights = params.*table;
            weights.clear();
            if (value.kind() != Json::Kind::Object) return;
            for (const auto& one : value.fields())
                weights[one.first] = one.second.as_double();
        }
    }
};

/// `knob("kappa0", &Params::kappa0)` -- one overload per kind, so a binding
/// reads as a list of names and members and nothing else.
template <class P> Knob<P> knob(const char* name, double P::* member) {
    Knob<P> one; one.name = name; one.real = member; return one;
}
template <class P> Knob<P> knob(const char* name, long long P::* member) {
    Knob<P> one; one.name = name; one.whole = member; return one;
}
template <class P> Knob<P> knob(const char* name, bool P::* member) {
    Knob<P> one; one.name = name; one.flag = member; return one;
}
template <class P> Knob<P> knob(const char* name, OrderedMap<double> P::* member) {
    Knob<P> one; one.name = name; one.table = member; return one;
}

/// Every knob of one engine, as the parameter map Python would expose.
template <class E>
OrderedMap<Json> read_params(const E& engine) {
    OrderedMap<Json> out;
    for (const auto& one : E::knobs()) out[one.name] = one.read(engine.params());
    return out;
}

/// Write back whatever the tuning block changed. Names absent from `values` are
/// left alone, so this applies a partial block without disturbing the rest.
template <class E>
void write_params(E& engine, const OrderedMap<Json>& values) {
    for (const auto& one : E::knobs()) {
        const Json* found = values.find(one.name);
        if (found) one.write(engine.params(), *found);
    }
}

}  // namespace usc
