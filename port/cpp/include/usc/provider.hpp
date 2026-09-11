// `usc/provider.py`. Turning a plan into text -- and surviving what a model
// sends back.
//
// The default `TemplateRealizer` is fully deterministic and register-aware, so
// the runtime operates with no external model at all. Its built-in templates
// express a STANCE -- evading, threatening, asking to be paid, greeting, having
// nothing to add -- and deliberately assert no world facts. There is no built-in
// `inform`: stating what is true about a world is the world's job, not the
// engine's. The default `inform` template used to read "the place was shut that
// night", a sentence about the reference scene's clinic, and every other pack
// inherited it -- so a character could assert something they did not believe and
// that was not true in their world.
//
// WHAT IS NOT HERE: the HTTP transport. A console build reaches a hosted model
// through the engine's own networking, not through a socket opened by a
// simulation core, and a header-only C++17 port with no dependencies has no
// business carrying an HTTP client. What IS here is `clean_reply`, because that
// is a SAFETY layer rather than a transport one: it decides what a chatty local
// model is allowed to have said, and a C++ build that cleaned differently would
// release text the Python build would have refused.
#pragma once

#include <algorithm>
#include <cctype>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/dialogue.hpp"
#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pystr.hpp"
#include "usc/sociolinguistics.hpp"
#include "usc/world.hpp"

namespace usc {

/// A text provider refused to produce a usable line.
class ProviderError : public std::runtime_error {
public:
    explicit ProviderError(const std::string& what) : std::runtime_error(what) {}
};

/// Deterministic, register-aware realizer.
class TemplateRealizer {
public:
    /// Output is authored text, so canon parse-back is unnecessary by construction.
    static constexpr bool IS_DETERMINISTIC = true;

    /// Stance templates: register variants that make no factual claim.
    static const OrderedMap<OrderedMap<std::string>>& default_templates() {
        static const OrderedMap<OrderedMap<std::string>>* table = [] {
            auto* fresh = new OrderedMap<OrderedMap<std::string>>();
            (*fresh)["evade"]["formal"] =
                "I am afraid that is not something I am able to discuss.";
            (*fresh)["evade"]["neutral"] = "Not sure that's any of your business.";
            (*fresh)["evade"]["vernacular"] = "Maybe. Why do you care?";
            (*fresh)["threaten"]["formal"] =
                "I would strongly advise you to reconsider your line of questioning.";
            (*fresh)["threaten"]["neutral"] = "Walk away while you still can.";
            (*fresh)["threaten"]["vernacular"] = "Back off. Now.";
            (*fresh)["request"]["formal"] =
                "I would be much obliged if you settled what you owe.";
            (*fresh)["request"]["neutral"] = "You still owe me. Time to pay.";
            (*fresh)["request"]["vernacular"] = "Where's my money?";
            (*fresh)["greet"]["formal"] = "Good evening.";
            (*fresh)["greet"]["neutral"] = "Evening.";
            (*fresh)["greet"]["vernacular"] = "Hey.";
            (*fresh)["deflect"]["formal"] = "I have nothing further to add.";
            (*fresh)["deflect"]["neutral"] = "I've got nothing for you.";
            (*fresh)["deflect"]["vernacular"] = "Nothin' to say.";
            return fresh;
        }();
        return *table;
    }

    OrderedMap<OrderedMap<std::string>> templates = default_templates();
    OrderedMap<std::string> slang;

    /// Did the words actually carry the commitment? A stance template does not.
    ///
    /// This matters because what is committed becomes a WORLD EVENT: without the
    /// flag a character could silently deflect to the player while the society
    /// heard them assert something, and the simulation and the sentence the
    /// player read would be describing different conversations.
    mutable bool expressed_commitment = true;

    TemplateRealizer() = default;

    /// A pack may override or extend any act template. The merge is PER ACT and
    /// per register: authoring one variant of `evade` leaves the other two alone.
    TemplateRealizer(const Json& authored, const Json& slang_lexicon) {
        for (const auto& act : authored.fields()) {
            // The act is created even when it authors NO variants: Python writes
            // `templates[act] = {**existing, **variants}`, so an empty override
            // leaves an empty act behind rather than doing nothing. It then falls
            // through to the deflection, which is a different sentence from the
            // one the engine's default for that act would have produced.
            OrderedMap<std::string>& variants = templates[act.first];
            for (const auto& variant : act.second.fields())
                variants[variant.first] = variant.second.py_str();
        }
        for (const auto& entry : slang_lexicon.fields())
            slang[entry.first] = entry.second.py_str();
    }

    /// Realizer carrying this world's authored templates and slang lexicon.
    static TemplateRealizer for_world(const World& world) {
        return TemplateRealizer(world.dialogue_templates, world.slang_lexicon);
    }

    static std::string register_for(double formality) {
        if (formality >= 0.6) return "formal";
        if (formality <= 0.3) return "vernacular";
        return "neutral";
    }

    /// Authored phrasing for this plan, if any, else the stance template.
    ///
    /// Returns false when there is neither, which is what tells `realize` that
    /// the commitment did NOT reach the words.
    bool lookup(const DialoguePlan& plan, const std::string& reg,
                std::string& out) const {
        // `if phrasing:` -- an EMPTY phrasing object falls through to the stance
        // templates, which is not the same as a missing one only because Python
        // treats both as false.
        if (plan.phrasing.truthy()) {
            for (const char* key : {reg.c_str(), "neutral"}) {
                const Json* found = plan.phrasing.find(key);
                // `phrasing.get(reg) or phrasing.get("neutral") or ...` -- an
                // authored empty string is skipped, not returned.
                if (found && found->truthy()) { out = found->py_str(); return true; }
            }
            // `next(iter(phrasing.values()), None)` -- the FIRST authored variant
            // in insertion order, whatever it is called. Note this one is NOT
            // truth-tested: an empty first value comes back as an empty string.
            const auto* first = plan.phrasing.fields().first();
            if (first) { out = first->second.py_str(); return true; }
            return false;
        }
        const OrderedMap<std::string>* variants = templates.find(plan.dialogue_act);
        if (!variants || variants->empty()) return false;   // `if not variants`
        const std::string* by_register = variants->find(reg);
        if (by_register && !by_register->empty()) { out = *by_register; return true; }
        // `variants.get(register) or variants.get("neutral")` -- with no third
        // operand the chain RETURNS the neutral variant even when it is empty,
        // and only a MISSING neutral gives None. The difference decides whether
        // the deflection fallback runs, which decides whether the commitment is
        // recorded as expressed.
        const std::string* by_neutral = variants->find("neutral");
        if (by_neutral) { out = *by_neutral; return true; }
        return false;
    }

    /// Every complete wording of this plan, best register first.
    ///
    /// For an anti-repeat retry to be safe it has to choose between COMPLETE
    /// realizations of the same commitment -- never between saying it and not.
    std::vector<std::string> variants(const DialoguePlan& plan,
                                      const StyleVector& style) const {
        // `dict(plan.phrasing or {}) or dict(self.templates.get(act) or {})` --
        // an EMPTY authored phrasing falls through to the stance variants.
        OrderedMap<std::string> source;
        for (const auto& entry : plan.phrasing.fields())
            source[entry.first] = entry.second.py_str();
        if (source.empty()) {
            const OrderedMap<std::string>* stance = templates.find(plan.dialogue_act);
            if (stance) source = *stance;
        }
        std::vector<std::string> out;
        std::string preferred = register_for(style.formality);
        std::vector<std::string> order = {preferred};
        for (const char* other : {"neutral", "formal", "vernacular"})
            if (preferred != other) order.push_back(other);
        for (const std::string& reg : order) {
            const std::string* line = source.find(reg);
            if (line == nullptr || line->empty()) continue;
            if (std::find(out.begin(), out.end(), *line) == out.end())
                out.push_back(*line);
        }
        return out;
    }

    std::string realize(const DialoguePlan& plan, const StyleVector& style) const {
        std::string reg = register_for(style.formality);
        std::string text;
        bool found = lookup(plan, reg, text);
        // DID THESE WORDS CARRY THE COMMITMENT -- not "was there a template".
        // A plan carrying facts, realised from a STANCE template because the pack
        // authored no phrasing for them, reported the commitment as expressed.
        bool authored = plan.phrasing.truthy();
        bool factual = false;
        for (const SemanticMove& move : plan.moves)
            if (move.is_factual()) { factual = true; break; }
        expressed_commitment = factual ? authored : true;
        if (!found) {
            // No authored phrasing and no stance template for this act: say
            // nothing factual rather than borrowing another world's sentence.
            const OrderedMap<std::string>* fallback = templates.find("deflect");
            text = fallback ? fallback->get(reg) : std::string();
        }

        // Slang substitution for in-group, low-formality speakers.
        if (!slang.empty() && style.slang_level > 0.3) {
            std::vector<std::string> words;
            for (const std::string& word : py_split(text)) {
                std::string key = py_lower(strip_punctuation(word));
                const std::string* replacement = slang.find(key);
                if (replacement) {
                    // `repl + w[len(key):]`. The tail is taken from the ORIGINAL
                    // word at the key's length, so a word with LEADING punctuation
                    // loses it -- ".money," becomes the replacement plus ",". That
                    // is what Python does and a port that tidied it up would
                    // disagree with a fixture that happens to contain one.
                    words.push_back(*replacement + word.substr(
                        std::min(key.size(), word.size())));
                } else {
                    words.push_back(word);
                }
            }
            text.clear();
            for (std::size_t i = 0; i < words.size(); ++i) {
                if (i) text += ' ';
                text += words[i];
            }
        }

        // Sentence-length pressure: a very low target keeps the first full
        // sentence. NOT cut at commas -- that makes fragments.
        //
        // AND NEVER ON A LINE THAT CARRIES A CLAIM. An authored answer reading
        // "Listen carefully. Place was shut that night." became "Listen
        // carefully." for an agitated speaker while the claim still propagated.
        // Style may choose between complete realizations; it may not remove what
        // the runtime committed to saying.
        if (!factual && style.mean_sentence_length < 7
                && text.find('.') != std::string::npos) {
            std::string first = text.substr(0, text.find('.'));
            first = py_strip(first);
            while (!first.empty() && first.back() == '.') first.pop_back();
            text = first + ".";
        }
        return text;
    }

private:
    /// `w.strip(".,!?")` -- both ends, any of those four, repeatedly.
    static std::string strip_punctuation(const std::string& word) {
        auto punctuation = [](char c) {
            return c == '.' || c == ',' || c == '!' || c == '?';
        };
        std::size_t begin = 0;
        while (begin < word.size() && punctuation(word[begin])) ++begin;
        std::size_t end = word.size();
        while (end > begin && punctuation(word[end - 1])) --end;
        return word.substr(begin, end - begin);
    }
};

/// The prompt and the clean-up an OpenAI-compatible chat endpoint needs.
///
/// The transport is the host's. These two functions are not, because they decide
/// what a model is TOLD and what it is allowed to have said.
namespace chat_realizer {

inline constexpr const char* SYSTEM =
    "You voice a single game NPC. Reply with EXACTLY ONE short in-character line "
    "of spoken dialogue and nothing else.\n"
    "Hard rules:\n"
    "- State EXACTLY what you are told to state. You are not choosing what to "
    "say; you are wording a decision that has already been made.\n"
    "- Say all of it, add nothing, and never invent names, places or events.\n"
    "- Never mention or hint at any avoid_topics.\n"
    "- Match the dialogue_act and style (formality, slang, brevity).\n"
    "- No narration, no quotes, no stage directions, no explanations, no lists, "
    "no meta commentary, no analysis, no 'Thinking'/'Answer' labels.\n"
    "- Output is one sentence the character actually says. /no_think";

/// Markers that mean the model echoed our scaffolding instead of speaking.
///
/// FOUR OF THESE SEVEN CAN NEVER MATCH, and that is a property of the reference
/// implementation rather than of this port. The markdown strip earlier in
/// `clean_reply` removes underscores, so by the time anything looks for
/// `dialogue_act`, `avoid_topics`, `allowed_facts` or `max_length` the text says
/// `dialogueact` and the rest. Only `addressee`, `agent:` and `{` still fire.
/// Reproduced, not repaired: a port that fixed it here would release text the
/// Python build rejects and refuse text it accepts, and the fix belongs in the
/// module both implementations are held to.
inline const std::vector<std::string>& scaffold_markers() {
    static const std::vector<std::string>* markers = new std::vector<std::string>{
        "dialogue_act", "avoid_topics", "allowed_facts", "addressee",
        "max_length", "agent:", "{"};
    return *markers;
}

namespace detail_ {

inline std::string lower_ascii(const std::string& text) {
    std::string out;
    for (char c : text) out += static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return out;
}

/// Case-insensitive find, ASCII. The Python patterns all carry `(?i)`.
inline std::size_t ifind(const std::string& haystack, const std::string& needle,
                         std::size_t from = 0) {
    std::string low = lower_ascii(haystack);
    return low.find(lower_ascii(needle), from);
}

/// `re.sub(r"<think>.*?</think>", " ", text, DOTALL|IGNORECASE)` -- NON-greedy,
/// so two blocks are removed separately rather than swallowing what lies between.
inline std::string drop_think_blocks(const std::string& text) {
    std::string out;
    std::size_t at = 0;
    while (true) {
        std::size_t open = ifind(text, "<think>", at);
        if (open == std::string::npos) break;
        std::size_t close = ifind(text, "</think>", open + 7);
        if (close == std::string::npos) break;
        out += text.substr(at, open - at);
        out += ' ';
        at = close + 8;
    }
    out += text.substr(at);
    return out;
}

/// `re.sub(r"</?think>", " ", IGNORECASE)` -- whatever tags the first pass left.
inline std::string drop_think_tags(const std::string& text) {
    std::string out;
    std::size_t at = 0;
    while (at < text.size()) {
        if (ifind(text.substr(at, 8), "</think>") == 0) { out += ' '; at += 8; continue; }
        if (ifind(text.substr(at, 7), "<think>") == 0) { out += ' '; at += 7; continue; }
        out += text[at];
        ++at;
    }
    return out;
}

/// One of the answer labels, at `at`, followed by optional space, a colon, and
/// optional space. Returns the length consumed, or 0.
///
/// Python's alternation is ORDERED and the pattern carries `\b` in front, so
/// "final answer" is tried BEFORE "answer" -- and matching the shorter one first
/// would leave the word "final" stranded at the head of the line.
inline std::size_t answer_label_at(const std::string& text, std::size_t at) {
    static const char* labels[] = {"final answer", "answer", "response", "reply",
                                   "output"};
    if (at > 0) {
        char before = text[at - 1];
        bool word = (before >= 'a' && before <= 'z') || (before >= 'A' && before <= 'Z')
                 || (before >= '0' && before <= '9') || before == '_';
        if (word) return 0;                                  // `\b`
    }
    for (const char* label : labels) {
        std::size_t length = std::strlen(label);
        if (ifind(text.substr(at, length), label) != 0) continue;
        std::size_t index = at + length;
        while (index < text.size() && py_space(text[index])) ++index;
        if (index >= text.size() || text[index] != ':') continue;
        ++index;
        while (index < text.size() && py_space(text[index])) ++index;
        return index - at;
    }
    return 0;
}

/// The whole line is nothing but a reasoning label.
inline bool is_label_line(const std::string& line) {
    static const char* labels[] = {"thinking process", "reasoning", "analysis",
                                   "thought", "note", "answer", "final answer",
                                   "response", "reply", "output"};
    for (const char* label : labels) {
        std::size_t length = std::strlen(label);
        if (ifind(line.substr(0, length), label) != 0) continue;
        std::size_t index = length;
        while (index < line.size() && py_space(line[index])) ++index;
        if (index < line.size() && line[index] == ':') ++index;
        while (index < line.size() && py_space(line[index])) ++index;
        if (index == line.size()) return true;
    }
    return false;
}

/// `text.strip('"')` then `.strip("'")` -- each strips ALL of that character
/// from both ends, which is not the same as removing one matched pair.
inline std::string strip_chars(const std::string& text, const std::string& chars) {
    std::size_t begin = 0;
    while (begin < text.size() && chars.find(text[begin]) != std::string::npos) ++begin;
    std::size_t end = text.size();
    while (end > begin && chars.find(text[end - 1]) != std::string::npos) --end;
    return text.substr(begin, end - begin);
}

inline bool word_char(unsigned char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')
        || (c >= '0' && c <= '9') || c == '_';
}

/// `re.sub(r"^[A-Z][\w '\-]{0,24}:\s+", "", text)` -- a leading speaker label.
///
/// The repeat count is a count of CHARACTERS in Python and of bytes here for
/// anything outside ASCII. The Latin-1 supplement is counted as one character
/// per two bytes so a label like "Müller: " behaves; beyond that range, a label
/// within four characters of the limit could be cut differently. Saying so is
/// better than implying a match nobody measured.
inline std::string strip_speaker_label(const std::string& text) {
    if (text.empty() || !(text[0] >= 'A' && text[0] <= 'Z')) return text;
    std::size_t index = 1;
    std::size_t counted = 0;
    while (index < text.size() && counted < 25) {
        unsigned char c = static_cast<unsigned char>(text[index]);
        if (c == 0xC3 && index + 1 < text.size()) { index += 2; ++counted; continue; }
        if (!(word_char(c) || c == ' ' || c == '\'' || c == '-')) break;
        ++index;
        ++counted;
    }
    // The colon has to be reachable within the repeat, and at least one space
    // must follow it.
    while (index >= 1) {
        if (index < text.size() && text[index] == ':' && index + 1 < text.size()
            && py_space(text[index + 1])) {
            std::size_t after = index + 1;
            while (after < text.size() && py_space(text[after])) ++after;
            return text.substr(after);
        }
        if (index == 1) break;
        --index;
    }
    return text;
}

/// `re.sub(r"^\s*(?:\d+[.)]|[-*•])\s*", "", text)` -- a leading list marker.
inline std::string strip_list_marker(const std::string& text) {
    std::size_t index = 0;
    while (index < text.size() && py_space(text[index])) ++index;
    std::size_t marker = index;
    if (index < text.size() && text[index] >= '0' && text[index] <= '9') {
        while (index < text.size() && text[index] >= '0' && text[index] <= '9') ++index;
        if (index < text.size() && (text[index] == '.' || text[index] == ')')) ++index;
        else return text;                             // digits with no terminator
    } else if (index < text.size() && (text[index] == '-' || text[index] == '*')) {
        ++index;
    } else if (text.compare(index, 3, "\xe2\x80\xa2") == 0) {   // U+2022 BULLET
        index += 3;
    } else {
        return text;
    }
    (void)marker;
    while (index < text.size() && py_space(text[index])) ++index;
    return text.substr(index);
}

}  // namespace detail_

/// Reduce a chatty small-model reply to one safe in-character line.
///
/// Returns "" when the reply is unusable -- empty, or an echo of the prompt
/// scaffolding. The caller turns that into a ProviderError, so the runtime falls
/// back to the validated deterministic template rather than leaking internal plan
/// data (allowed_facts, avoid_topics) to the player.
inline std::string clean_reply(const std::string& raw, long long max_length) {
    std::string text = detail_::drop_think_blocks(raw);
    text = detail_::drop_think_tags(text);
    // Cut at the first leaked chat-template special token (<|im_start|>, ...).
    std::size_t special = text.find("<|");
    if (special != std::string::npos) text = text.substr(0, special);
    // Strip markdown emphasis and heading characters, so "**Heading:**" becomes
    // "Heading:".
    std::string stripped;
    for (char c : text)
        if (c != '*' && c != '_' && c != '`' && c != '#') stripped += c;
    text = stripped;

    // If a labelled reasoning preamble exists, keep only what follows the LAST
    // answer label. `re.split` returns every part, and Python takes `parts[-1]`.
    std::size_t last_end = std::string::npos;
    for (std::size_t at = 0; at < text.size(); ++at) {
        std::size_t length = detail_::answer_label_at(text, at);
        if (length) { last_end = at + length; at += length - 1; }
    }
    if (last_end != std::string::npos && !py_strip(text.substr(last_end)).empty())
        text = text.substr(last_end);

    // Split into lines and drop pure reasoning-label lines.
    std::string flattened;
    for (char c : text) flattened += (c == '\r') ? '\n' : c;
    std::vector<std::string> lines;
    std::string current;
    for (char c : flattened) {
        if (c == '\n') { lines.push_back(current); current.clear(); }
        else current += c;
    }
    lines.push_back(current);
    std::vector<std::string> kept;
    for (const std::string& line : lines) {
        std::string trimmed = py_strip(line);
        if (trimmed.empty()) continue;                    // `if ln.strip()`
        if (detail_::is_label_line(trimmed)) continue;
        kept.push_back(trimmed);
    }
    text = kept.empty() ? std::string() : kept.front();

    // Strip surrounding quotes and markdown, then a leading speaker label.
    text = detail_::strip_chars(py_strip(text), "\"");
    text = detail_::strip_chars(text, "'");
    while (!text.empty() && text.front() == '*') text.erase(text.begin());
    text = py_strip(text);
    text = detail_::strip_speaker_label(text);
    text = py_strip(detail_::strip_list_marker(text));
    // Quotes or labels may have exposed an inner quote ('Vee: "Back off."').
    text = detail_::strip_chars(py_strip(text), "\"");
    text = py_strip(detail_::strip_chars(text, "'"));

    // Reject scaffolding echoes, leftover labels and non-utterances.
    std::string low = py_lower(text);
    bool has_letter = false;
    for (char c : text)
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z')) { has_letter = true; break; }
    if (text.empty() || text.back() == ':' || !has_letter) return "";
    for (const std::string& marker : scaffold_markers())
        if (low.find(marker) != std::string::npos) return "";

    // Keep the first sentence, so a rambling paragraph is never released.
    std::vector<std::string> parts = py_split_sentences(text);
    if (!parts.empty() && !parts[0].empty()) text = py_strip(parts[0]);

    // A hard character cap derived from the plan's length budget.
    std::size_t cap = static_cast<std::size_t>(std::max(40LL, max_length * 8));
    if (text.size() > cap) {
        std::string head = text.substr(0, cap);
        std::size_t space = head.rfind(' ');
        // `rsplit(" ", 1)[0]` -- with NO space, the whole string comes back.
        if (space != std::string::npos) head = head.substr(0, space);
        while (!head.empty() && (head.back() == ',' || head.back() == ';'
                                 || head.back() == ':'))
            head.pop_back();
        text = head + ".";
    }
    return py_strip(text);
}

/// Natural-language instructions, NOT raw JSON -- weak models echo JSON.
///
/// `allowed_facts` is exactly what the runtime decided this character says.
/// Selecting among options was the model's job until it turned out that choosing
/// which fact reaches a listener IS deciding what enters the society.
inline std::string build_user_prompt(const DialoguePlan& plan, const StyleVector& style) {
    std::string register_word = style.formality >= 0.6 ? "formal"
                              : style.formality <= 0.3 ? "rough/streetwise" : "plain";
    std::string slang = style.slang_level > 0.3 ? "use street slang" : "little slang";

    std::vector<std::string> lines;
    lines.push_back("Write the single line " + plan.speaker + " says to "
                    + plan.addressee + ".");
    lines.push_back("Intent: " + plan.dialogue_act + ". Goal: " + plan.goal + ".");

    if (!plan.moves.empty()) {
        for (const SemanticMove& move : plan.moves) {
            if (!move.is_factual()) continue;
            std::string hedge = "plainly";
            if (move.certainty == "certain") hedge = "as plain fact";
            else if (move.certainty == "probable")
                hedge = "as something you believe but were not there for";
            else if (move.certainty == "uncertain")
                hedge = "hesitantly, as something you are unsure of";
            lines.push_back("Say this, " + hedge + ": " + move.rendered());
        }
        lines.push_back("Say all of the above and nothing else of substance.");
    } else if (!plan.allowed_facts.empty()) {
        std::string joined;
        for (std::size_t i = 0; i < plan.allowed_facts.size(); ++i) {
            if (i) joined += "; ";
            joined += plan.allowed_facts[i];
        }
        lines.push_back("Say exactly this and nothing else of substance: " + joined);
    } else {
        lines.push_back("You have no concrete facts to share; stay vague.");
    }

    if (!plan.avoid_topics.empty()) {
        std::string joined;
        for (std::size_t i = 0; i < plan.avoid_topics.size(); ++i) {
            if (i) joined += "; ";
            joined += plan.avoid_topics[i];
        }
        lines.push_back("NEVER mention or hint at: " + joined + ".");
    }
    // Python's `//` FLOOR-divides, which for a negative budget rounds AWAY from
    // zero -- and the floor of 4 is what keeps that from reaching the prompt.
    long long words = plan.max_length / 4;
    if (plan.max_length % 4 != 0 && ((plan.max_length < 0) != (4 < 0))) --words;
    lines.push_back("Tone: " + register_word + ", " + slang + ", at most "
                    + std::to_string(std::max(4LL, words)) + " words.");
    lines.push_back("Reply with ONLY the spoken line, no quotes, no labels, no JSON.");

    std::string out;
    for (std::size_t i = 0; i < lines.size(); ++i) {
        if (i) out += '\n';
        out += lines[i];
    }
    return out;
}

}  // namespace chat_realizer

}  // namespace usc
