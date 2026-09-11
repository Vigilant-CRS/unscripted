// A JSON value, a parser and a writer -- and Python's `str()` for the same
// value, which is a separate thing and the reason this is one type.
//
// Two jobs that look unrelated and are not:
//
// 1. Reading a conformance fixture and writing the state back out to compare.
// 2. Being a proposition's slot value. Slots come from JSON in a world pack,
//    and `core_key()` interpolates them into a string with an f-string. So the
//    port needs Python's `str()` for a JSON value -- `None`, not `null`;
//    `True`, not `true`; `5.0`, not `5`. That string is the key a belief is
//    stored under. Get it wrong and two implementations disagree about whether
//    they are talking about the same proposition, which no amount of correct
//    arithmetic afterwards recovers from.
//
// Objects preserve insertion order (see `ordered_map.hpp`). That is not for
// tidiness: the state comparison walks both blobs, and a port that emits the
// same fields in a different order would be reported as identical only because
// the checker sorts keys -- while `core_key()`, which does not sort, would
// already have diverged.
#pragma once

#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/ordered_map.hpp"

namespace usc {

class Json;
using JsonObject = OrderedMap<Json>;

class Json {
public:
    enum class Kind { Null, Bool, Int, Real, String, Array, Object };

    Json() : kind_(Kind::Null) {}
    Json(std::nullptr_t) : kind_(Kind::Null) {}
    Json(bool value) : kind_(Kind::Bool), boolean_(value) {}
    Json(int value) : kind_(Kind::Int), integer_(value) {}
    Json(long long value) : kind_(Kind::Int), integer_(value) {}
    Json(double value) : kind_(Kind::Real), real_(value) {}
    Json(const char* value) : kind_(Kind::String), text_(value) {}
    Json(std::string value) : kind_(Kind::String), text_(std::move(value)) {}

    static Json array() { Json j; j.kind_ = Kind::Array; return j; }
    /// An array that came from a Python TUPLE.
    ///
    /// `json.dumps` writes a tuple and a list identically, so this changes
    /// nothing about a document -- but `repr` does not, and the inspector prints
    /// reason details with `repr`. Without the distinction a selection
    /// probability reads as `['greet', 0.689]` where Python shows
    /// `('greet', 0.689)`, and every inspector line carrying one differs.
    static Json tuple() { Json j; j.kind_ = Kind::Array; j.tuple_ = true; return j; }
    bool is_tuple() const { return kind_ == Kind::Array && tuple_; }
    static Json object() { Json j; j.kind_ = Kind::Object;
                           j.object_ = std::make_shared<JsonObject>(); return j; }

    Kind kind() const { return kind_; }
    bool is_null() const { return kind_ == Kind::Null; }
    bool is_number() const { return kind_ == Kind::Int || kind_ == Kind::Real; }

    /// Python's `if value:`, which is not `value is not None`. An empty
    /// declaration is no declaration -- a distinction the engine leans on in
    /// several places, and one a null check quietly gets wrong.
    bool truthy() const {
        switch (kind_) {
            case Kind::Null:   return false;
            case Kind::Bool:   return boolean_;
            case Kind::Int:    return integer_ != 0;
            case Kind::Real:   return real_ != 0.0;
            case Kind::String: return !text_.empty();
            case Kind::Array:  return !array_.empty();
            case Kind::Object: return object_ && !object_->empty();
        }
        return false;
    }

    bool as_bool(bool fallback = false) const {
        return kind_ == Kind::Bool ? boolean_ : fallback;
    }
    long long as_int(long long fallback = 0) const {
        if (kind_ == Kind::Int) return integer_;
        if (kind_ == Kind::Real) return static_cast<long long>(real_);
        return fallback;
    }
    double as_double(double fallback = 0.0) const {
        if (kind_ == Kind::Real) return real_;
        if (kind_ == Kind::Int) return static_cast<double>(integer_);
        return fallback;
    }
    const std::string& as_string() const& { return text_; }
    /// Deleted on an rvalue. `doc.get("k").as_string()` bound to a named
    /// reference dangles as soon as the full expression ends, which compiles
    /// and usually works -- and did work here, twice, until a sanitizer was
    /// pointed at it. Returning by value from a temporary costs one copy and
    /// removes the trap; `at()` returns a reference and costs nothing.
    std::string as_string() && { return text_; }

    /// Deleted on an RVALUE, for the same reason `as_string()` is.
    ///
    /// `for (const Json& one : f().items())` compiles, and in C++17 the
    /// temporary `f()` returned is destroyed before the loop body runs -- the
    /// range-for extends the lifetime of the range EXPRESSION and not of a
    /// temporary a sub-expression produced. This port hit that four times, and
    /// every one of them read as "the data is simply missing" rather than as a
    /// crash. Now it does not compile.
    std::vector<Json>& items() & { return array_; }
    const std::vector<Json>& items() const& { return array_; }
    std::vector<Json>& items() && = delete;
    const std::vector<Json>& items() const&& = delete;
    void push(Json value) { kind_ = Kind::Array; array_.push_back(std::move(value)); }

    /// `dict(other)` / `list(other)` -- a ONE-LEVEL copy.
    ///
    /// Assigning a Json ALIASES its object, exactly as `a = b` does for a Python
    /// dict: the fields live behind a shared pointer and writing through either
    /// name is visible through both. That is the faithful behaviour and it is
    /// also a trap, because C++ reads like value semantics. Anywhere Python
    /// writes `dict(x)` before mutating, this is the call.
    ///
    /// One level, like Python's: the nested values are still shared.
    Json copy() const {
        Json out = *this;
        if (object_) {
            out.object_ = std::make_shared<JsonObject>(*object_);
        }
        return out;
    }

    JsonObject& fields() & {
        if (!object_) { kind_ = Kind::Object; object_ = std::make_shared<JsonObject>(); }
        return *object_;
    }
    const JsonObject& fields() const& {
        static const JsonObject empty;
        return object_ ? *object_ : empty;
    }
    JsonObject& fields() && = delete;
    const JsonObject& fields() const&& = delete;
    Json& operator[](const std::string& key) { return fields()[key]; }
    const Json* find(const std::string& key) const {
        return object_ ? object_->find(key) : nullptr;
    }
    /// `d.get(key)` -- a COPY, like Python's. Safe to store, and a trap to
    /// iterate: `doc.get("cases").items()` binds a reference into a temporary
    /// that dies before the loop body runs. That compiles, and crashed. Use
    /// `at()` to walk a container.
    Json get(const std::string& key) const {
        const Json* found = find(key);
        return found ? *found : Json();
    }

    /// The value itself, by reference, or a shared null when absent. This is
    /// the one to use in a range-for.
    const Json& at(const std::string& key) const {
        static const Json nothing;
        const Json* found = find(key);
        return found ? *found : nothing;
    }

    /// What Python's `str()` gives for this value.
    ///
    /// Used inside `core_key()` and `Proposition.__str__`, so it is part of the
    /// runtime's behaviour rather than a debugging convenience.
    std::string py_str() const {
        switch (kind_) {
            case Kind::Null:   return "None";
            case Kind::Bool:   return boolean_ ? "True" : "False";
            case Kind::Int:    return std::to_string(integer_);
            case Kind::Real:   return repr_double(real_);
            case Kind::String: return text_;
            default:           return dump();
        }
    }

    std::string dump(int indent = -1) const {
        std::string out;
        write(out, indent, 0);
        return out;
    }

    /// A document this parser will not accept, with the byte it gave up at.
    ///
    /// The parser used to accept anything and quietly invent a value for it:
    /// `{"a":1` became `{"a":1}`, `[1,]` became `[1,0]`, and the bare word `wat`
    /// became `0`. At the C ABI this is the boundary that packs, tuning blocks
    /// and save files arrive over, so a truncated or corrupt document did not
    /// fail -- it arrived as different, plausible data. Every entry point in the
    /// ABI already turns an exception into a status code, so refusing is cheap
    /// and silence was not.
    struct Error : std::runtime_error {
        explicit Error(const std::string& why) : std::runtime_error(why) {}
    };

    static Json parse(const std::string& text) {
        std::size_t at = 0;
        Json value = parse_value(text, at);
        skip_space(text, at);
        // A value followed by anything else is not one document. Without this,
        // the parser read as far as it liked and threw the rest away.
        if (at != text.size()) fail("trailing content after the value", at);
        return value;
    }

    /// Python's `repr()` for a float: the shortest decimal that round-trips,
    /// in the notation Python chooses for it.
    ///
    /// `%.17g` always round-trips but prints `0.30000000000000004` for values
    /// Python shows as `0.3`, so a port emitting it produces a different
    /// *document* for an identical *number*. Shortest-round-trip is what both
    /// `json.dump` and `repr` use.
    ///
    /// The FIRST version of this searched `%g` for the shortest precision that
    /// round-trips, which gets the digits right and the notation wrong: `%g`
    /// switches to exponential at the precision it was given, so `1e15` came out
    /// as `1e+15` where Python writes `1000000000000000.0`. Probabilities and
    /// minutes never reached that far, so nothing caught it. CPython chooses by
    /// where the decimal point falls -- FIXED when `-4 < decpt <= 16` -- and that
    /// is what this does.
    static std::string repr_double(double value, bool json_names = true) {
        if (std::isnan(value)) return json_names ? "NaN" : "nan";
        if (std::isinf(value))
            return value > 0 ? (json_names ? "Infinity" : "inf")
                             : (json_names ? "-Infinity" : "-inf");

        std::string sign = std::signbit(value) ? "-" : "";
        double magnitude = std::fabs(value);
        if (magnitude == 0.0) return sign + "0.0";

        // Shortest round-trip digits in scientific form, so the digits and the
        // exponent come apart cleanly.
        char buffer[64];
        auto written = std::to_chars(buffer, buffer + sizeof buffer, magnitude,
                                     std::chars_format::scientific);
        std::string text(buffer, written.ptr);
        std::size_t e = text.find('e');
        std::string digits = text.substr(0, e);
        int exponent = std::stoi(text.substr(e + 1));
        // Written as a loop rather than `std::remove`: `<cstdio>` declares a
        // global `remove(const char*)`, and a translation unit that includes it
        // without `<algorithm>` picks the wrong one. `belief_probe.cpp` is such
        // a unit, and the error it produced named a file it does not use.
        std::string packed;
        for (char c : digits) if (c != '.') packed += c;
        digits = packed;
        // Where the point sits relative to the digit string: 1.5e2 has digits
        // "15" and decpt 3, which is "150.0".
        int decpt = exponent + 1;

        if (decpt > -4 && decpt <= 16) {
            if (decpt <= 0)
                return sign + "0."
                     + std::string(static_cast<std::size_t>(-decpt), '0') + digits;
            if (static_cast<std::size_t>(decpt) >= digits.size())
                return sign + digits
                     + std::string(static_cast<std::size_t>(decpt) - digits.size(), '0')
                     + ".0";
            return sign + digits.substr(0, static_cast<std::size_t>(decpt)) + "."
                 + digits.substr(static_cast<std::size_t>(decpt));
        }

        // Exponential. Python writes at least two exponent digits, always signed.
        std::string mantissa = digits.substr(0, 1);
        if (digits.size() > 1) mantissa += "." + digits.substr(1);
        int power = decpt - 1;
        char tail[16];
        std::snprintf(tail, sizeof tail, "e%c%02d", power < 0 ? '-' : '+',
                      power < 0 ? -power : power);
        return sign + mantissa + tail;
    }

private:
    Kind kind_;
    bool boolean_ = false;
    bool tuple_ = false;
    long long integer_ = 0;
    double real_ = 0.0;
    std::string text_;
    std::vector<Json> array_;
    std::shared_ptr<JsonObject> object_;

    static void skip_space(const std::string& s, std::size_t& at) {
        while (at < s.size() && (s[at] == ' ' || s[at] == '\t' ||
                                 s[at] == '\n' || s[at] == '\r')) ++at;
    }

    [[noreturn]] static void fail(const std::string& why, std::size_t at) {
        throw Error(why + " at byte " + std::to_string(at));
    }

    static void expect(const std::string& s, std::size_t& at, char wanted) {
        if (at >= s.size() || s[at] != wanted)
            fail(std::string("expected '") + wanted + "'", at);
        ++at;
    }

    static Json parse_value(const std::string& s, std::size_t& at) {
        skip_space(s, at);
        if (at >= s.size()) fail("no value", at);
        char c = s[at];
        if (c == '{') return parse_object(s, at);
        if (c == '[') return parse_array(s, at);
        if (c == '"') return Json(parse_string(s, at));
        if (s.compare(at, 4, "true") == 0)  { at += 4; return Json(true); }
        if (s.compare(at, 5, "false") == 0) { at += 5; return Json(false); }
        if (s.compare(at, 4, "null") == 0)  { at += 4; return Json(); }
        // Python's `json` writes these for non-finite floats, so a parser that
        // has to read back what the writer emits has to accept them.
        if (s.compare(at, 9, "-Infinity") == 0) {
            at += 9;
            return Json(-std::numeric_limits<double>::infinity());
        }
        if (s.compare(at, 8, "Infinity") == 0) {
            at += 8;
            return Json(std::numeric_limits<double>::infinity());
        }
        if (s.compare(at, 3, "NaN") == 0) {
            at += 3;
            return Json(std::numeric_limits<double>::quiet_NaN());
        }
        if (c == '-' || (c >= '0' && c <= '9')) return parse_number(s, at);
        fail("not a JSON value", at);
    }

    static Json parse_object(const std::string& s, std::size_t& at) {
        Json out = Json::object();
        expect(s, at, '{');
        skip_space(s, at);
        if (at < s.size() && s[at] == '}') { ++at; return out; }
        while (true) {
            skip_space(s, at);
            if (at >= s.size() || s[at] != '"') fail("expected a key", at);
            std::string key = parse_string(s, at);
            skip_space(s, at);
            expect(s, at, ':');
            out.fields()[key] = parse_value(s, at);
            skip_space(s, at);
            if (at >= s.size()) fail("unterminated object", at);
            if (s[at] == ',') { ++at; continue; }   // a trailing comma then
            if (s[at] == '}') { ++at; return out; } // fails at "expected a key"
            fail("expected ',' or '}'", at);
        }
    }

    static Json parse_array(const std::string& s, std::size_t& at) {
        Json out = Json::array();
        expect(s, at, '[');
        skip_space(s, at);
        if (at < s.size() && s[at] == ']') { ++at; return out; }
        while (true) {
            out.push(parse_value(s, at));           // `[1,]` fails here, on the
            skip_space(s, at);                      // value that is not there
            if (at >= s.size()) fail("unterminated array", at);
            if (s[at] == ',') { ++at; continue; }
            if (s[at] == ']') { ++at; return out; }
            fail("expected ',' or ']'", at);
        }
    }

    static unsigned parse_hex4(const std::string& s, std::size_t& at) {
        unsigned code = 0;
        for (int i = 0; i < 4; ++i) {
            if (at >= s.size()) fail("truncated \\u escape", at);
            char h = s[at++];
            unsigned digit;
            if (h >= '0' && h <= '9') digit = static_cast<unsigned>(h - '0');
            else if (h >= 'a' && h <= 'f') digit = static_cast<unsigned>(h - 'a' + 10);
            else if (h >= 'A' && h <= 'F') digit = static_cast<unsigned>(h - 'A' + 10);
            else fail("bad hex digit in \\u escape", at - 1);
            code = code * 16 + digit;
        }
        return code;
    }

    static std::string parse_string(const std::string& s, std::size_t& at) {
        std::string out;
        expect(s, at, '"');
        while (true) {
            if (at >= s.size()) fail("unterminated string", at);
            char c = s[at++];
            if (c == '"') return out;
            if (c != '\\') { out += c; continue; }
            if (at >= s.size()) fail("unterminated escape", at);
            char esc = s[at++];
            switch (esc) {
                case '"':  out += '"';  break;
                case '\\': out += '\\'; break;
                case '/':  out += '/';  break;
                case 'n': out += '\n'; break;
                case 't': out += '\t'; break;
                case 'r': out += '\r'; break;
                case 'b': out += '\b'; break;
                case 'f': out += '\f'; break;
                case 'u': {
                    unsigned code = parse_hex4(s, at);
                    // A SURROGATE PAIR IS ONE CHARACTER. Python's `json.dumps`
                    // escapes anything outside the BMP as two `\u` escapes by
                    // default, so an emoji arrived here as two lone surrogates
                    // and was encoded as six bytes of CESU-8 -- `ed a0 bd ed b8
                    // 80` where UTF-8 wants `f0 9f 98 80`. Valid input, invalid
                    // output, and the two implementations disagreed about the
                    // contents of a string.
                    if (code >= 0xD800 && code <= 0xDBFF && at + 1 < s.size()
                        && s[at] == '\\' && s[at + 1] == 'u') {
                        std::size_t probe = at + 2;
                        unsigned low = parse_hex4(s, probe);
                        if (low >= 0xDC00 && low <= 0xDFFF) {
                            at = probe;
                            code = 0x10000u + ((code - 0xD800u) << 10) + (low - 0xDC00u);
                        }
                    }
                    append_utf8(out, code);
                    break;
                }
                default: fail("unknown escape", at - 1);
            }
        }
    }

    static void append_utf8(std::string& out, unsigned code) {
        if (code < 0x80) { out += static_cast<char>(code); return; }
        if (code < 0x800) {
            out += static_cast<char>(0xC0 | (code >> 6));
            out += static_cast<char>(0x80 | (code & 0x3F));
            return;
        }
        if (code < 0x10000) {
            out += static_cast<char>(0xE0 | (code >> 12));
            out += static_cast<char>(0x80 | ((code >> 6) & 0x3F));
            out += static_cast<char>(0x80 | (code & 0x3F));
            return;
        }
        out += static_cast<char>(0xF0 | (code >> 18));
        out += static_cast<char>(0x80 | ((code >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((code >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (code & 0x3F));
    }

    /// JSON's number grammar, and only it. The previous version swept up any
    /// run of digits and signs, so `1e` parsed as 1.0 and `+1` -- which JSON
    /// does not have -- parsed as 1.
    static Json parse_number(const std::string& s, std::size_t& at) {
        std::size_t start = at;
        auto digit = [&](std::size_t where) {
            return where < s.size() && s[where] >= '0' && s[where] <= '9';
        };
        if (at < s.size() && s[at] == '-') ++at;
        if (!digit(at)) fail("expected a digit", at);
        if (s[at] == '0') ++at;                 // a leading zero stands alone;
        else while (digit(at)) ++at;            // "01" then fails as trailing content
        bool real = false;
        if (at < s.size() && s[at] == '.') {
            real = true;
            ++at;
            if (!digit(at)) fail("expected a digit after '.'", at);
            while (digit(at)) ++at;
        }
        if (at < s.size() && (s[at] == 'e' || s[at] == 'E')) {
            real = true;
            ++at;
            if (at < s.size() && (s[at] == '+' || s[at] == '-')) ++at;
            if (!digit(at)) fail("expected a digit in the exponent", at);
            while (digit(at)) ++at;
        }
        std::string token = s.substr(start, at - start);
        if (real) return Json(std::strtod(token.c_str(), nullptr));
        return Json(static_cast<long long>(std::strtoll(token.c_str(), nullptr, 10)));
    }

    void write(std::string& out, int indent, int depth) const {
        auto newline = [&](int level) {
            if (indent < 0) return;
            out += '\n';
            out.append(static_cast<std::size_t>(indent * level), ' ');
        };
        switch (kind_) {
            case Kind::Null:   out += "null"; return;
            case Kind::Bool:   out += boolean_ ? "true" : "false"; return;
            case Kind::Int:    out += std::to_string(integer_); return;
            case Kind::Real:   out += repr_double(real_); return;
            case Kind::String: write_string(out, text_); return;
            case Kind::Array: {
                if (array_.empty()) { out += "[]"; return; }
                out += '[';
                for (std::size_t i = 0; i < array_.size(); ++i) {
                    if (i) out += ',';
                    newline(depth + 1);
                    array_[i].write(out, indent, depth + 1);
                }
                newline(depth);
                out += ']';
                return;
            }
            case Kind::Object: {
                const JsonObject& obj = fields();
                if (obj.empty()) { out += "{}"; return; }
                out += '{';
                bool first = true;
                for (const auto& entry : obj) {
                    if (!first) out += ',';
                    first = false;
                    newline(depth + 1);
                    write_string(out, entry.first);
                    out += indent < 0 ? ":" : ": ";
                    entry.second.write(out, indent, depth + 1);
                }
                newline(depth);
                out += '}';
                return;
            }
        }
    }

    static void write_string(std::string& out, const std::string& text) {
        out += '"';
        for (unsigned char c : text) {
            switch (c) {
                case '"':  out += "\\\""; break;
                case '\\': out += "\\\\"; break;
                case '\n': out += "\\n"; break;
                case '\t': out += "\\t"; break;
                case '\r': out += "\\r"; break;
                default:
                    if (c < 0x20) {
                        char buf[8];
                        std::snprintf(buf, sizeof buf, "\\u%04x", c);
                        out += buf;
                    } else {
                        out += static_cast<char>(c);
                    }
            }
        }
        out += '"';
    }
};

}  // namespace usc
