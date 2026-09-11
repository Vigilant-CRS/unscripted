// `usc/grounding.py`. Reading a released sentence back, and checking it against
// what was committed.
//
// The validator catches proper nouns and numbers a speaker was not licensed to
// use. That leaves a documented hole: "the old mill by the river" in a world
// with no mill contains no proper noun and no number, so it passed. A character
// asserting the existence of a thing that does not exist is exactly the failure
// that makes a language model untrustworthy in an NPC's mouth, and it is
// invisible to a capitalisation rule.
//
// Two checks, and they are different questions. DID THE SENTENCE SAY WHAT IT WAS
// SUPPOSED TO -- a commitment the words did not carry must not propagate, or the
// room hears an assertion the player never read. And DID IT SAY ANYTHING ELSE --
// every referential noun phrase against the world's own vocabulary, classified
// rather than uniformly rejected, because "the door" is furniture and "the old
// mill" is a claim about what exists.
//
// NO LANGUAGE MODEL IS INVOLVED, deliberately: a grounding check that needs a
// model to work cannot be the thing that makes the model safe.
#pragma once

#include <algorithm>
#include <cctype>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/content.hpp"
#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pystr.hpp"
#include "usc/world.hpp"

namespace usc {

/// Words that introduce a referring noun phrase. An unknown noun after one of
/// these asserts that the thing exists; the same noun elsewhere usually does not.
inline const std::set<std::string>& determiners() {
    static const std::set<std::string> words = {
        "the", "a", "an", "that", "this", "those", "these", "his", "her",
        "their", "my", "your", "our", "its"};
    return words;
}

/// Ordinary furniture of a sentence: nouns that describe rather than assert. A
/// world extends this through `decorative_vocabulary` -- what counts as scenery
/// is a property of the setting, not of the engine.
inline const std::set<std::string>& generic_nouns() {
    static const std::set<std::string>* words = [] {
        auto* fresh = new std::set<std::string>();
        const char* text =
            "door doors wall walls floor ceiling roof window windows street streets "
            "road roads corner corners room rooms place places thing things man woman "
            "men women people person guy guys kid kids friend friends family night day "
            "morning evening afternoon week weeks month months year years hour hours "
            "minute minutes time times money cash price cost work job business trouble "
            "problem problems question questions answer answers word words name names "
            "story stories news rumour rumor truth lie lies matter matters point points "
            "reason reasons way ways side sides hand hands eye eyes face head foot feet "
            "body voice light dark air water food drink smoke rain cold heat noise "
            "sound silence";
        std::string current;
        for (const char* p = text; ; ++p) {
            if (*p == ' ' || *p == '\0') {
                if (!current.empty()) fresh->insert(current);
                current.clear();
                if (*p == '\0') break;
            } else current += *p;
        }
        return fresh;
    }();
    return *words;
}

/// Words that end a noun phrase. The head noun is the last word before one of
/// these, which is why "the old mill" is a claim about a mill and not about "old".
inline const std::set<std::string>& phrase_end() {
    static const std::set<std::string>* words = [] {
        auto* fresh = new std::set<std::string>();
        const char* text =
            "by in on at to of for with from into onto over under near behind beside "
            "about was were is are be been being had has have did does do will would "
            "can could should might must went came saw said told burned closed opened "
            "stood sat ran and or but so then than that which who whom whose when "
            "where while because if";
        std::string current;
        for (const char* p = text; ; ++p) {
            if (*p == ' ' || *p == '\0') {
                if (!current.empty()) fresh->insert(current);
                current.clear();
                if (*p == '\0') break;
            } else current += *p;
        }
        return fresh;
    }();
    return *words;
}

/// Rough end-of-phrase test for a past participle or gerund.
///
/// English morphology, not a parser. It exists so "a courier dropped" reads as a
/// courier and a verb rather than as a thing called a "dropped". Getting this
/// slightly wrong costs a deflection, never a leak, because the check only ever
/// adds candidates to an already-conservative list.
inline bool looks_verbal(const std::string& token) {
    if (token.size() <= 4) return false;
    auto ends_with = [&](const std::string& suffix) {
        return token.size() >= suffix.size()
            && token.compare(token.size() - suffix.size(), suffix.size(), suffix) == 0;
    };
    return ends_with("ed") || ends_with("ing");
}

/// `re.findall(r"[a-z][a-z'\-]*", text.lower())` -- a token starts with a
/// letter and may carry apostrophes and hyphens, so "don't" and "half-hour" are
/// one token each.
inline std::vector<std::string> tokenise(const std::string& text) {
    std::vector<std::string> tokens;
    std::string current;
    for (char raw : text) {
        char c = static_cast<char>(std::tolower(static_cast<unsigned char>(raw)));
        bool letter = c >= 'a' && c <= 'z';
        if (current.empty()) {
            if (letter) current += c;
        } else if (letter || c == '\'' || c == '-') {
            current += c;
        } else {
            tokens.push_back(current);
            current.clear();
        }
    }
    if (!current.empty()) tokens.push_back(current);
    return tokens;
}

/// Every phrase this world answers to, and what it refers to.
class WorldLexicon {
public:
    struct Entry {
        std::string kind;
        std::string target;
    };

    WorldLexicon() = default;
    WorldLexicon(OrderedMap<Entry> terms, std::set<std::string> decorative)
        : terms_(std::move(terms)), decorative_(std::move(decorative)) {}

    const OrderedMap<Entry>& terms() const { return terms_; }
    const std::set<std::string>& decorative() const { return decorative_; }

    /// `WorldLexicon.build(world)`. The topics and the pack's extra decorative
    /// vocabulary are separate parameters only because this module was ported
    /// before `World` carried either; the one-argument form below is what Python
    /// actually has, and is what every caller should use.
    static WorldLexicon build(const World& world) {
        return build(world, world.topics, world.decorative_vocabulary);
    }

    static WorldLexicon build(const World& world, const OrderedMap<Topic>& topics,
                              const Json& decorative_vocabulary = Json()) {
        OrderedMap<Entry> terms;
        auto add = [&](const std::string& name, const std::string& target,
                       const std::string& kind) {
            if (name.empty()) return;
            std::string key = trim_lower(name);
            if (key.empty()) return;
            // `setdefault` -- the FIRST claim on a phrase wins, so a later place
            // does not steal a name an earlier one already answers to.
            if (!terms.contains(key)) terms[key] = Entry{kind, target};

            // Index the words of a multi-word name too. "The Harbour Front" is a
            // place, so "harbour" is this world's vocabulary and a character
            // saying it has invented nothing. Without this, every world's own
            // nouns read as inventions the moment they appear on their own.
            std::vector<std::string> parts;
            for (const std::string& part : split_on_separators(key))
                if (part.size() > 3) parts.push_back(part);
            bool single = parts.size() == 1 && key == parts[0];
            if (parts.size() > 1 || !single)
                for (const std::string& part : parts)
                    if (!determiners().count(part) && !terms.contains(part))
                        terms[part] = Entry{kind, target};
        };

        for (const auto& place : world.places.fields()) {
            const Json& attrs = place.second;
            const Json* label = attrs.find("label");
            if (label && !label->is_null()) add(label->py_str(), place.first, "place");
            for (const Json& alias : attrs.at("aliases").items())
                add(alias.py_str(), place.first, "place");
        }
        for (const auto& entry : world.agents) {
            const Agent& agent = entry.second;
            if (!agent.public_name.is_null()) add(agent.public_name.py_str(), agent.id, "agent");
            if (!agent.objective_name.is_null())
                add(agent.objective_name.py_str(), agent.id, "agent");
            for (const std::string& alias : agent.aliases) add(alias, agent.id, "agent");
        }
        for (const auto& thing : world.entities.fields()) {
            const Json& entity = thing.second;
            const Json* name = entity.find("name");
            if (name && !name->is_null()) add(name->py_str(), thing.first, "entity");
            for (const Json& alias : entity.at("aliases").items())
                add(alias.py_str(), thing.first, "entity");
            // Bare ids read like "item:sealant"; the tail is what people say.
            std::size_t colon = thing.first.find(':');
            if (colon != std::string::npos) {
                std::string tail = thing.first.substr(colon + 1);
                std::replace(tail.begin(), tail.end(), '_', ' ');
                add(tail, thing.first, "entity");
            }
        }
        for (const auto& topic : topics)
            for (const std::string& alias : topic.second.aliases)
                add(alias, topic.second.topic_id, "topic");

        // The predicate catalogue is this world's declared subject matter: if a
        // pack declares `seal_breached`, then "seal" is a thing in that world.
        for (const auto& predicate : world.predicates.fields())
            for (const std::string& part : split_on_separators(lower(predicate.first)))
                if (part.size() > 3 && !terms.contains(part))
                    terms[part] = Entry{"predicate", predicate.first};

        std::set<std::string> decorative = generic_nouns();
        for (const Json& word : decorative_vocabulary.items())
            decorative.insert(lower(word.py_str()));
        return WorldLexicon(std::move(terms), std::move(decorative));
    }

    const Entry* lookup(const std::string& phrase) const {
        return terms_.find(trim_lower(phrase));
    }

    /// The longest known phrase starting at `index`, or nothing.
    struct Match {
        std::string phrase;
        Entry entry;
        std::size_t length = 0;
    };

    /// LONGEST first, and no case here can tell that from shortest first.
    ///
    /// Worth saying rather than leaving as a silent gap: every constituent word
    /// longer than three characters is indexed on its own, so a shorter match
    /// inside a longer one is itself a known term and the walk ends up skipping
    /// the same tokens either way. The two orders can only diverge on a
    /// multi-word name whose second word is three characters or fewer -- and
    /// that word can never begin a flagged phrase, because a flagged phrase must
    /// follow a determiner. The order is right on its own terms and a mutation
    /// of it is not caught, which is a fact about the design rather than a hole
    /// in the cases.
    std::optional<Match> longest_match_at(const std::vector<std::string>& tokens,
                                          std::size_t index,
                                          std::size_t span = 4) const {
        std::size_t most = std::min(span, tokens.size() - index);
        for (std::size_t length = most; length >= 1; --length) {
            std::string phrase;
            for (std::size_t i = 0; i < length; ++i) {
                if (i) phrase += " ";
                phrase += tokens[index + i];
            }
            const Entry* hit = terms_.find(phrase);
            if (hit) return Match{phrase, *hit, length};
        }
        return std::nullopt;
    }

    /// `str.lower()`, and NOT `std::tolower` in a loop -- a place labelled
    /// "Tür" would otherwise be filed under "tÜr" and be unreachable. The
    /// tokeniser above is a different matter: it keeps only `[a-z]`, so an
    /// umlaut is dropped either way and the two agree there by accident.
    static std::string lower(const std::string& text) { return py_lower(text); }

private:
    static std::string trim_lower(const std::string& text) {
        std::size_t start = text.find_first_not_of(" \t\n\r");
        if (start == std::string::npos) return "";
        std::size_t stop = text.find_last_not_of(" \t\n\r");
        return lower(text.substr(start, stop - start + 1));
    }

    /// `re.split(r"[\s:_\-]+", key)`.
    ///
    /// Splits on RUNS of separators, so `a::b` yields two parts and not three --
    /// but a LEADING or TRAILING run still yields an empty part, which is what
    /// makes `":vee"` split into `""` and `"vee"`. The length test downstream
    /// drops those, and reproducing the empty part anyway keeps the `key ==
    /// parts[:1]` comparison honest.
    static std::vector<std::string> split_on_separators(const std::string& text) {
        auto is_separator = [](char c) {
            return c == ' ' || c == '\t' || c == '\n' || c == '\r'
                || c == ':' || c == '_' || c == '-';
        };
        std::vector<std::string> parts;
        std::string current;
        std::size_t at = 0;
        while (at < text.size()) {
            if (!is_separator(text[at])) { current += text[at++]; continue; }
            parts.push_back(current);
            current.clear();
            while (at < text.size() && is_separator(text[at])) ++at;
        }
        parts.push_back(current);
        return parts;
    }

    OrderedMap<Entry> terms_;
    std::set<std::string> decorative_;
};

/// The words a listener would have to hear for this claim to have been made.
///
/// Slot values give the concrete ones -- a place, a person, an item -- resolved
/// through the world's own aliases. That is the honest floor: without naming any
/// of the things a proposition is about, a sentence has not asserted it.
inline std::vector<std::string> anchors_for(const Proposition* proposition,
                                            const WorldLexicon& lexicon) {
    if (!proposition) return {};
    OrderedMap<std::vector<std::string>> reverse;
    for (const auto& entry : lexicon.terms())
        reverse[entry.second.target].push_back(entry.first);

    std::set<std::string> anchors;
    for (const auto& slot : proposition->slots) {
        std::string value = slot.second.py_str();
        if (const std::vector<std::string>* known = reverse.find(value))
            for (const std::string& phrase : *known)
                if (!phrase.empty()) anchors.insert(WorldLexicon::lower(phrase));
        std::size_t colon = value.find(':');
        std::string tail = colon == std::string::npos ? value : value.substr(colon + 1);
        std::replace(tail.begin(), tail.end(), '_', ' ');
        if (!tail.empty()) anchors.insert(WorldLexicon::lower(tail));
    }
    return std::vector<std::string>(anchors.begin(), anchors.end());
}

/// Would a listener take this sentence to have made that claim?
///
/// Deliberately generous: ONE anchor is enough. The purpose is to catch a
/// sentence that says nothing about the subject at all -- a deflection released
/// while the room heard an assertion -- not to grade paraphrase quality. Being
/// strict would reject good writing; being absent lets the simulation and the
/// script describe different conversations.
/// Words that make a sentence a denial. Crude on purpose, and it can only ever
/// cost a deflection: this decides whether a released line AGREES with the
/// polarity of what was committed.
inline const std::vector<std::string>& negations() {
    static const std::vector<std::string> table = {
        "not", "no", "never", "none", "nothing", "nobody", "nowhere", "neither",
        "nor", "without", "isn't", "wasn't", "aren't", "weren't", "don't",
        "doesn't", "didn't", "won't", "wouldn't", "shouldn't", "can't", "cannot",
        "couldn't", "hasn't", "haven't", "hadn't", "ain't", "denied", "denies",
        "deny", "refused", "refuses"};
    return table;
}

inline bool denies(const std::string& text) {
    for (const std::string& token : tokenise(text))
        for (const std::string& word : negations())
            if (token == word) return true;
    return false;
}

/// Every world id this sentence names, by any word the world answers to.
/// Longest-match, so "the back room" resolves once to the place.
inline std::set<std::string> referenced_ids(const std::string& text,
                                            const WorldLexicon& lexicon) {
    std::set<std::string> found;
    std::vector<std::string> words = tokenise(text);
    std::size_t index = 0;
    while (index < words.size()) {
        if (auto match = lexicon.longest_match_at(words, index)) {
            found.insert(match->entry.target);
            index += match->length;
            continue;
        }
        ++index;
    }
    return found;
}

inline bool expresses(const std::string& text, const Proposition* proposition,
                      const WorldLexicon& lexicon) {
    std::vector<std::string> anchors = anchors_for(proposition, lexicon);
    if (anchors.empty()) return true;     // nothing to look for; do not block
    std::string lowered = " " + WorldLexicon::lower(text) + " ";
    bool anchored = false;
    for (const std::string& anchor : anchors)
        if (lowered.find(" " + anchor + " ") != std::string::npos
            || lowered.find(anchor) != std::string::npos) { anchored = true; break; }
    if (!anchored) return false;
    // AND IT HAS TO SAY IT THE RIGHT WAY ROUND. Naming the subject is not making
    // the claim: "The clinic was open all night" names the clinic, and the
    // commitment behind it was that the clinic was NOT open. Generosity is right
    // about paraphrase and wrong about negation.
    bool negative = proposition != nullptr && proposition->polarity == "-";
    return negative == denies(text);
}

/// Noun phrases that assert the existence of something the world lacks.
///
/// Classified rather than uniformly rejected: decorative furniture passes,
/// anything named in the commitment passes, and an unknown noun in referring
/// position is the "old mill by the river" case -- it does not exist, and the
/// character just implied it does.
inline std::vector<Json> unknown_referents(const std::string& text,
                                           const WorldLexicon& lexicon,
                                           const std::string& licensed = "") {
    std::vector<std::string> tokens = tokenise(text);
    std::string licence = WorldLexicon::lower(licensed);
    for (char& c : licence)
        if (c == ':' || c == '_' || c == '-' || c == '(' || c == ')'
            || c == '=' || c == ',' || c == '.') c = ' ';

    std::vector<Json> found;
    std::set<std::string> seen;
    std::size_t index = 0;
    while (index < tokens.size()) {
        if (auto match = lexicon.longest_match_at(tokens, index)) {
            index += match->length;       // a known thing, however many words long
            continue;
        }
        if (index > 0 && determiners().count(tokens[index - 1])) {
            // Walk to the head of the noun phrase. "the old mill" asserts a
            // mill, not an "old"; flagging the adjective would be wrong and noisy.
            std::size_t end = index;
            while (end + 1 < tokens.size()
                   // Stop AT the head: an ordinary or known noun ends the
                   // phrase, so "the city months ago" is about a city and not
                   // about "ago".
                   && !lexicon.decorative().count(tokens[end])
                   && !lexicon.lookup(tokens[end])
                   && !phrase_end().count(tokens[end + 1])
                   && !determiners().count(tokens[end + 1])
                   && !looks_verbal(tokens[end + 1])
                   && !lexicon.longest_match_at(tokens, end + 1))
                ++end;
            const std::string& head = tokens[end];
            std::string phrase;
            for (std::size_t i = index - 1; i <= end; ++i) {
                if (i > index - 1) phrase += " ";
                phrase += tokens[i];
            }
            if (!lexicon.decorative().count(head)
                && licence.find(head) == std::string::npos
                && !lexicon.lookup(head)
                && head.size() > 2
                && !seen.count(head)) {
                seen.insert(head);
                Json entry = Json::object();
                entry["kind"] = std::string("invented_referent");
                entry["token"] = head;
                entry["phrase"] = phrase;
                found.push_back(entry);
            }
            index = end + 1;
            continue;
        }
        ++index;
    }
    return found;
}

}  // namespace usc
