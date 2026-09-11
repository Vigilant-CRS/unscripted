// Python's string semantics, for the handful of places the engine leans on them.
//
// The reason this is a header rather than a call to `std::tolower` at each site:
// `std::tolower` works on BYTES. A place labelled "Tür" is three characters in
// Python and four bytes here, and byte-wise lowering leaves the "Ü" alone -- so
// the alias index would file it under "tÜr", the parser would look for "tuer",
// and the room would be unreachable. That failure is silent, it only shows up in
// packs authored outside English, and it was found by putting one umlaut in a
// probe case.
#pragma once

#include <cctype>
#include <string>
#include <vector>

namespace usc {

/// `str.lower()` over ASCII and the Latin-1 supplement.
///
/// That range is where German and every western European name lives. The
/// two-byte UTF-8 forms C3 80..C3 9E map to C3 A0..C3 BE; C3 97 is the
/// multiplication sign and is not a letter. Beyond that range -- Greek,
/// Cyrillic, the Turkish dotted I -- this and Python part company, and a pack
/// authored in one of those scripts needs this table extended rather than
/// trusted.
inline std::string py_lower(const std::string& text) {
    std::string out;
    out.reserve(text.size());
    for (std::size_t i = 0; i < text.size(); ++i) {
        unsigned char c = static_cast<unsigned char>(text[i]);
        if (c == 0xC3 && i + 1 < text.size()) {
            unsigned char next = static_cast<unsigned char>(text[i + 1]);
            if (next >= 0x80 && next <= 0x9E && next != 0x97) {
                out += static_cast<char>(0xC3);
                out += static_cast<char>(next + 0x20);
            } else {
                out += text[i];
                out += text[i + 1];
            }
            ++i;
            continue;
        }
        out += static_cast<char>(std::tolower(c));
    }
    return out;
}

inline bool py_space(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

/// `str.strip()` -- whitespace at both ends.
inline std::string py_strip(const std::string& text) {
    std::size_t begin = 0;
    while (begin < text.size() && py_space(text[begin])) ++begin;
    std::size_t end = text.size();
    while (end > begin && py_space(text[end - 1])) --end;
    return text.substr(begin, end - begin);
}

/// `str.split()` with no argument: runs of whitespace, no empty parts.
inline std::vector<std::string> py_split(const std::string& text) {
    std::vector<std::string> out;
    std::string current;
    for (char c : text) {
        if (py_space(c)) {
            if (!current.empty()) { out.push_back(current); current.clear(); }
        } else {
            current += c;
        }
    }
    if (!current.empty()) out.push_back(current);
    return out;
}

/// `re.split(r"(?<=[.!?])\s+", text)` -- a lookbehind split, so the terminator
/// stays with the sentence it ended and the whitespace after it disappears.
/// Never returns an empty list: a string with no break is one sentence.
inline std::vector<std::string> py_split_sentences(const std::string& text) {
    std::vector<std::string> out;
    std::size_t start = 0;
    std::size_t index = 0;
    while (index < text.size()) {
        if ((text[index] == '.' || text[index] == '!' || text[index] == '?')
            && index + 1 < text.size() && py_space(text[index + 1])) {
            std::size_t stop = index + 1;
            std::size_t after = stop;
            while (after < text.size() && py_space(text[after])) ++after;
            out.push_back(text.substr(start, stop - start));
            start = after;
            index = after;
            continue;
        }
        ++index;
    }
    out.push_back(text.substr(start));
    return out;
}

inline void py_replace_all(std::string& text, const std::string& from,
                           const std::string& to) {
    if (from.empty()) return;
    std::size_t at = 0;
    while ((at = text.find(from, at)) != std::string::npos) {
        text.replace(at, from.size(), to);
        at += to.size();
    }
}

}  // namespace usc
