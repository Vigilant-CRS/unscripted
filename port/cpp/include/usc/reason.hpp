// One reason entry: what happened, how much, and the detail behind it.
//
// Python writes these as three-element TUPLES -- `("belief.updated", 0.31, {...})`
// -- and every module in the runtime produces the same shape. Nineteen modules of
// this port had each declared their own struct for it, byte-identical to the
// other eighteen, which was harmless right up until the runtime had to collect
// all nineteen into one trace and needed nineteen conversions to do it.
//
// So there is one type, and the per-module names are aliases of it. They are kept
// rather than replaced wholesale because a signature that says `MemoryReason`
// says something a bare `Reason` does not, and because the alias costs nothing.
#pragma once

#include <string>

#include "usc/json.hpp"

namespace usc {

struct Reason {
    std::string code;
    double amount = 0.0;
    Json detail;

    /// The Python tuple, for anything that exports a trace.
    Json as_json() const {
        Json out = Json::array();
        out.push(code);
        out.push(amount);
        out.push(detail);
        return out;
    }
};

}  // namespace usc
