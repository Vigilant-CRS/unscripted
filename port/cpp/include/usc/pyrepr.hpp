// Python's `repr()` and `str()` for the values a reason trace carries.
//
// The inspector prints a detail dict straight into a line of text, so the two
// implementations have to agree on how a dict, a string and above all a FLOAT
// look. That last one is the hard part and the reason this file exists.
//
// `repr(0.1)` is "0.1" and not "0.10000000000000001": CPython prints the
// SHORTEST decimal string that reads back as the same double. `printf("%g")`
// does not do that, `printf("%.17g")` does not do that, and getting it wrong
// means an inspector line that differs on almost every number. C++17's
// `std::to_chars` does exactly the right rounding, and what is left is Python's
// own choice of notation on top of it -- fixed or exponential, and the ".0" that
// tells a float from an int.
#pragma once

#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <string>
#include <system_error>

#include "usc/json.hpp"

namespace usc {

/// `repr(value)` for a finite double, and Python's names for the rest.
///
/// CPython formats the shortest round-tripping digits and then chooses notation
/// by where the decimal point falls: FIXED when `-4 < decpt <= 16`, exponential
/// otherwise. So `1e15` prints as `1000000000000000.0` and `1e16` as `1e+16`;
/// `0.0001` stays fixed and `1e-05` does not. Reproduced rather than
/// approximated, because an inspector line that agreed on the value and
/// disagreed on the notation would fail a comparison for no reason a reader
/// could act on.
inline std::string py_repr(double value) {
    // Exactly `Json`'s float repr, with Python's names for the specials rather
    // than JSON's: `nan` and `inf`, not `NaN` and `Infinity`.
    return Json::repr_double(value, false);
}

/// `repr(text)` -- Python prefers single quotes, and switches to double quotes
/// only when the string contains a single quote and no double one.
inline std::string py_repr(const std::string& text) {
    bool has_single = text.find('\'') != std::string::npos;
    bool has_double = text.find('"') != std::string::npos;
    char quote = (has_single && !has_double) ? '"' : '\'';
    std::string out(1, quote);
    for (char c : text) {
        if (c == '\\') out += "\\\\";
        else if (c == quote) { out += '\\'; out += c; }
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else out += c;
    }
    out += quote;
    return out;
}

/// `repr(value)` for anything a reason detail can hold.
inline std::string py_repr(const Json& value) {
    switch (value.kind()) {
        case Json::Kind::Null:   return "None";
        case Json::Kind::Bool:   return value.as_bool() ? "True" : "False";
        case Json::Kind::Int:    return std::to_string(value.as_int());
        case Json::Kind::Real:   return py_repr(value.as_double());
        case Json::Kind::String: return py_repr(value.as_string());
        case Json::Kind::Array: {
            bool tuple = value.is_tuple();
            std::string out = tuple ? "(" : "[";
            const std::vector<Json>& items = value.items();
            for (std::size_t i = 0; i < items.size(); ++i) {
                if (i) out += ", ";
                out += py_repr(items[i]);
            }
            // A ONE-element tuple keeps its trailing comma: `('x',)`.
            if (tuple && items.size() == 1) out += ",";
            return out + (tuple ? ")" : "]");
        }
        case Json::Kind::Object: {
            std::string out = "{";
            bool first = true;
            for (const auto& entry : value.fields()) {
                if (!first) out += ", ";
                first = false;
                out += py_repr(entry.first) + ": " + py_repr(entry.second);
            }
            return out + "}";
        }
    }
    return "None";
}

}  // namespace usc
