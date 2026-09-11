// `usc/parser.py`. The deterministic semantic parser for the reference client.
//
// Not a chatbot. It maps free player text onto a CLOSED command catalogue that
// the SDK can validate, execute and replay -- which is what makes a studio able
// to swap in its own parser provider without the rest of the runtime noticing.
//
// Two vocabularies meet here and keeping them apart is the point. The COMMAND
// lexicon (go / ask / threaten / wait) belongs to the engine, and a pack may
// extend or replace the words but not invent an intent. The WORLD vocabulary
// (place names, character names, what "the medic" means) belongs to the pack,
// and is read from the loaded world rather than from tables in this file --
// which is what a second pack needs in order to be navigable at all.
//
// The regular expressions are hand-written rather than delegated to <regex>.
// Not for speed: `std::regex` is a portability question on the platforms this
// port exists for, and both patterns here are small enough that reproducing
// Python's exact semantics -- ORDERED alternation included -- is the shorter
// road than arguing with a library about them.
#pragma once

#include <algorithm>
#include <cctype>
#include <cstring>
#include <optional>
#include <string>
#include <vector>

#include "usc/content.hpp"
#include "usc/contracts.hpp"
#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/pystr.hpp"
#include "usc/ordered_map.hpp"
#include "usc/world.hpp"

namespace usc {

/// Engine-level command words. A pack extends or replaces these per intent
/// through `world.json: {"command_aliases": {"move": [...], ...}}`.
inline const OrderedMap<std::vector<std::string>>& default_command_lexicon() {
    static const OrderedMap<std::vector<std::string>>* words = [] {
        auto* fresh = new OrderedMap<std::vector<std::string>>();
        (*fresh)["quit"] = {"quit", "exit", "q", "ende", "stop"};
        (*fresh)["help"] = {"help", "hilfe", "?", "commands"};
        (*fresh)["observe"] = {"look", "observe", "l", "schau", "umsehen",
                               "umschauen", "sieh dich um"};
        (*fresh)["move"] = {"go ", "move ", "walk ", "enter ", "gehe ", "geh ",
                            "zu ", "nach "};
        (*fresh)["wait"] = {"wait", "sleep", "warte", "schlaf"};
        (*fresh)["inspect"] = {"inspect", "debug", "trace", "untersuche", "zeige"};
        (*fresh)["listen_radio"] = {"radio", "news", "nachrichten"};
        (*fresh)["attack"] = {"attack", "hit", "punch", "angreif", "schlag"};
        (*fresh)["threaten"] = {"threaten", "droh", "intimidat", "warn"};
        (*fresh)["promise"] = {"promise", "versprech", "pay", "zahl",
                               "give you", "gebe dir"};
        (*fresh)["claim"] = {"lie", "lueg", "l\xc3\xbcg", "claim", "behaupt", "tell"};
        (*fresh)["ask"] = {"ask", "frage", "frag", "rede", "talk", "speak", "sprich"};
        (*fresh)["accuse"] = {"accuse", "beschuldig", "confront", "konfront"};
        // The only thing a player could do TO somebody was hostile or
        // transactional. A runtime about what a town comes to think of you needs
        // a way to be decent in front of it.
        //
        // Called `assist` and not `help`: `help` is already the intent for the
        // system command, and in Python a second key of the same name in the
        // same literal simply REPLACED it -- so "help byrne" printed the command
        // list and nobody could be kind to anybody. Every entry keeps its
        // trailing space so a bare "help" is still the command list.
        (*fresh)["assist"] = {"help ", "assist ", "hilf ", "defend ",
                              "stand up for ", "steh "};
        // What you turn up wearing. Needed to play the thing at all: appearance
        // was authored on every character and fixed for the player, so the one
        // person whose clothes a player could reasonably choose was the one who
        // could not.
        (*fresh)["wear"] = {"wear ", "put on ", "change into ", "zieh ", "trage "};
        return fresh;
    }();
    return *words;
}

inline constexpr const char* HELP_TEXT =
    "Commands: look, go <place>, ask <npc> about <topic>, tell <npc> <claim>, "
    "promise <npc> 300, threaten <npc>, attack <npc>, wait 30, inspect <npc>, quit.";

namespace detail_ {

inline bool is_digit(char c) { return c >= '0' && c <= '9'; }

}  // namespace detail_

/// Strip, lower-case, fold the umlauts, collapse the whitespace.
inline std::string normalize(const std::string& text) {
    std::string low = py_lower(py_strip(text));
    py_replace_all(low, "\xc3\xa4", "ae");
    py_replace_all(low, "\xc3\xb6", "oe");
    py_replace_all(low, "\xc3\xbc", "ue");
    py_replace_all(low, "\xc3\x9f", "ss");
    // `re.sub(r"\s+", " ", low)`. The string is already stripped, so there is no
    // run at either end to worry about.
    std::string out;
    bool in_space = false;
    for (char c : low) {
        bool space = (c == ' ' || c == '\t' || c == '\n' || c == '\r'
                      || c == '\v' || c == '\f');
        if (space) {
            if (!in_space) out += ' ';
            in_space = true;
        } else {
            out += c;
            in_space = false;
        }
    }
    return out;
}

inline bool contains_any(const std::string& text,
                         const std::vector<std::string>& words) {
    for (const std::string& word : words)
        if (text.find(word) != std::string::npos) return true;
    return false;
}

inline bool starts_with_any(const std::string& text,
                            const std::vector<std::string>& words) {
    for (const std::string& word : words)
        if (text.rfind(word, 0) == 0) return true;
    return false;
}

class RuleBasedParserProvider {
public:
    static constexpr const char* MODULE_ID = "rule_based_parser";
    static constexpr const char* VERSION = "2.0.0";

    RuleBasedParserProvider() = default;
    explicit RuleBasedParserProvider(OrderedMap<std::vector<std::string>> override_words)
        : override_(std::move(override_words)), has_override_(true) {}

    /// The engine's lexicon, then any constructor override, then the pack's --
    /// each REPLACING an intent's whole word list rather than adding to it.
    OrderedMap<std::vector<std::string>> lexicon(const World& world) const {
        OrderedMap<std::vector<std::string>> merged = default_command_lexicon();
        if (has_override_)
            for (const auto& entry : override_) merged[entry.first] = entry.second;
        for (const auto& entry : world.command_aliases.fields()) {
            std::vector<std::string> words;
            for (const Json& word : entry.second.items()) words.push_back(word.py_str());
            merged[entry.first] = words;
        }
        // A word with no surrounding whitespace is NORMALISED -- so a pack can
        // author "lüg" and have it fold. A word that carries a trailing space is
        // only lower-cased, because that space is load-bearing: it is what keeps
        // a bare "help" a system command.
        OrderedMap<std::vector<std::string>> out;
        for (const auto& entry : merged) {
            std::vector<std::string> words;
            for (const std::string& word : entry.second)
                words.push_back(py_strip(word) == word
                                    ? normalize(word) : py_lower(word));
            out[entry.first] = words;
        }
        return out;
    }

    ParsedCommand parse(const std::string& text, const std::string& player_id,
                        const std::string& player_location, const World& world) const {
        std::string raw = py_strip(text);
        std::string low = normalize(raw);
        OrderedMap<std::vector<std::string>> lex = lexicon(world);

        auto words_of = [&](const char* intent) -> const std::vector<std::string>& {
            static const std::vector<std::string> none;
            const std::vector<std::string>* found = lex.find(intent);
            return found ? *found : none;
        };
        auto is_exactly = [&](const char* intent) {
            const std::vector<std::string>& words = words_of(intent);
            return std::find(words.begin(), words.end(), low) != words.end();
        };

        if (low.empty()) return command(raw, "noop", 1.0, player_id, "parser.empty", 1.0);
        if (is_exactly("quit")) return command(raw, "quit", 1.0, player_id, "parser.system", 1.0);
        if (is_exactly("help")) {
            ParsedCommand out = command(raw, "help", 1.0, player_id, "parser.system", 1.0);
            Json metadata = Json::object();
            metadata["help"] = std::string(HELP_TEXT);
            out.metadata = metadata;
            return out;
        }
        if (is_exactly("observe"))
            return command(raw, "observe", 1.0, player_id, "parser.observe", 1.0);

        if (starts_with_any(low, words_of("move"))) {
            std::string place = world.place_alias_index().match(low);
            if (!place.empty()) {
                Json why = Json::object();
                why["place"] = place;
                ParsedCommand out = command(raw, "move", 0.95, player_id,
                                            "parser.move.place_alias", 0.95, why);
                out.location_id = place;
                return out;
            }
            return command(raw, "unknown", 0.2, player_id, "parser.move.no_place", 0.2);
        }

        if (starts_with_any(low, words_of("wait"))
            || low.find("minute") != std::string::npos) {
            // `_extract_minutes(low) or ...` -- TRUTHINESS. "wait 0" extracts a
            // zero, which is falsy, so it falls through to the default half hour
            // rather than waiting for no time at all.
            std::optional<long long> found = extract_minutes(low);
            long long minutes = (found && *found != 0)
                ? *found
                : (contains_any(low, {"sleep", "schlaf"}) ? 8 * 60 : 30);
            Json why = Json::object();
            why["minutes"] = minutes;
            ParsedCommand out = command(raw, "wait", 0.9, player_id,
                                        "parser.time", 0.9, why);
            out.minutes = minutes;
            return out;
        }

        if (starts_with_any(low, words_of("inspect"))) {
            Json target = resolve_agent(low, world, player_location, player_id);
            Json why = Json::object();
            why["target"] = target;
            ParsedCommand out = command(raw, "inspect", 0.9, player_id,
                                        "parser.inspect", 0.9, why);
            out.target_id = target;
            return out;
        }

        // A LEADING VERB WINS -- see the long note below -- and this check has to
        // come BEFORE the radio. It did not, and `listen_radio` matched "radio"
        // or "news" anywhere in the line, so "ask Byrne about the news" switched
        // the radio on instead of asking the newsagent, and "ask him about the
        // radio version" could not be said at all. The same bug as the one below,
        // one line earlier, found by asking a newsstand about the news.
        std::string leading;
        for (const char* intent : {"attack", "threaten", "promise", "claim",
                                   "accuse", "assist", "wear", "ask"}) {
            std::vector<std::string> imperative;
            // `w for w in lex.get(intent, ()) if w.strip()` -- a word that is
            // nothing but whitespace cannot start a sentence.
            for (const std::string& word : words_of(intent))
                if (!py_strip(word).empty()) imperative.push_back(word);
            if (starts_with_any(low, imperative)) { leading = intent; break; }
        }

        if (leading.empty() && contains_any(low, words_of("listen_radio")))
            return command(raw, "listen_radio", 0.85, player_id, "parser.media", 0.85);

        Json target = resolve_agent(low, world, player_location, player_id);
        std::string matched_topic = world.topic_alias_index().match(low);
        Json topic = matched_topic.empty() ? Json() : Json(matched_topic);

        // `move`, `wait` and `inspect` above have always matched on the START of
        // the line; the intents below matched anywhere in it, and the
        // inconsistency was a bug with teeth: in a world whose topic is called
        // `market_attack`, "ask Honce about the market attack" contains the word
        // "attack" and was parsed as an assault. Every character in the room
        // mobilised their allies, and the topic could not be asked about at all
        // -- by anyone, ever, in that world.
        //
        // An imperative puts its verb first, so when the line starts with one it
        // decides. The contains-anywhere pass stays as the fallback, because that
        // is what catches "I want to threaten him".
        auto means = [&](const char* intent) {
            if (!leading.empty()) return leading == intent;
            return contains_any(low, words_of(intent));
        };

        if (means("attack")) {
            Json why = Json::object();
            why["target"] = target;
            ParsedCommand out = command(raw, "attack", 0.85, player_id,
                                        "parser.attack", 0.85, why);
            out.target_id = target;
            return out;
        }

        if (means("wear")) {
            Json garment = match_appearance(low, world);
            double confidence = garment.truthy() ? 0.9 : 0.3;
            Json why = Json::object();
            why["garment"] = garment;
            ParsedCommand out = command(raw, "wear", confidence, player_id,
                                        "parser.wear", confidence, why);
            Json metadata = Json::object();
            metadata["garment"] = garment;
            out.metadata = metadata;
            return out;
        }

        if (means("assist")) {
            Json why = Json::object();
            why["target"] = target;
            ParsedCommand out = command(raw, "assist", 0.85, player_id,
                                        "parser.assist", 0.85, why);
            out.target_id = target;
            return out;
        }

        if (means("threaten")) {
            Json why = Json::object();
            why["target"] = target;
            ParsedCommand out = command(raw, "threaten", 0.85, player_id,
                                        "parser.threat", 0.85, why);
            out.target_id = target;
            out.topic = topic;
            return out;
        }

        if (means("promise")) {
            // `_extract_amount(low) or "300"` -- truthiness again, but here it
            // cannot bite: the pattern needs at least one digit, so what comes
            // back is never the empty string. An amount of "0" survives, unlike
            // a wait of zero minutes, and a mutation of the difference is not
            // catchable because there is no difference to catch.
            std::optional<std::string> found = extract_amount(low);
            std::string amount = found ? *found : "300";
            Proposition promised;
            promised.predicate = "economy:owes_amount";
            promised.slots["debtor"] = player_id;
            promised.slots["creditor"] = target.truthy() ? target.py_str() : std::string();
            promised.slots["amount"] = amount;
            Json why = Json::object();
            why["target"] = target;
            why["amount"] = amount;
            ParsedCommand out = command(raw, "promise", 0.9, player_id,
                                        "parser.promise", 0.9, why);
            out.target_id = target;
            out.proposition = promised;
            out.amount = amount;
            return out;
        }

        if (means("claim")) {
            Json why = Json::object();
            why["target"] = target;
            why["topic"] = topic;
            ParsedCommand out = command(raw, "claim", 0.78, player_id,
                                        "parser.claim", 0.78, why);
            out.target_id = target;
            out.proposition = topic_proposition(world, matched_topic, player_id, true);
            out.topic = topic;
            return out;
        }

        if (means("ask")) {
            Json why = Json::object();
            why["target"] = target;
            why["topic"] = topic;
            ParsedCommand out = command(raw, "ask", 0.86, player_id,
                                        "parser.ask", 0.86, why);
            out.target_id = target;
            out.proposition = topic_proposition(world, matched_topic, player_id, false);
            out.topic = topic;
            return out;
        }

        if (means("accuse")) {
            Json why = Json::object();
            why["target"] = target;
            ParsedCommand out = command(raw, "accuse", 0.78, player_id,
                                        "parser.accuse", 0.78, why);
            out.target_id = target;
            out.topic = topic;
            return out;
        }

        // Fallback: route as ordinary speech to a nearby target if one was named.
        if (target.truthy()) {
            Json why = Json::object();
            why["target"] = target;
            ParsedCommand out = command(raw, "say", 0.55, player_id,
                                        "parser.fallback_say", 0.55, why);
            out.target_id = target;
            out.topic = topic;
            return out;
        }
        return command(raw, "unknown", 0.2, player_id, "parser.unknown", 0.2);
    }

    /// A named agent first, else the only NPC present.
    ///
    /// The player is excluded by their CONFIGURED id. This used to compare
    /// against the literal string "agent:player_1", so any game that named its
    /// player differently could address the player as if they were an NPC.
    Json resolve_agent(const std::string& text, const World& world,
                       const std::string& player_location,
                       const std::string& player_id) const {
        std::string named = world.agent_alias_index().match(text, {player_id});
        if (!named.empty()) return Json(named);
        std::vector<std::string> nearby;
        for (const auto& entry : world.agents)
            if (entry.first != player_id
                && entry.second.location().py_str() == player_location)
                nearby.push_back(entry.first);
        return nearby.size() == 1 ? Json(nearby[0]) : Json();
    }

    /// Which authored garment the player meant, by its last word.
    ///
    /// Deliberately dumb: `item:red_cyberjacket` answers to "cyberjacket" and to
    /// its full id, and nothing else. A pack that wants "the red one" adds the
    /// alias to its reactions table rather than teaching this parser about
    /// adjectives.
    Json match_appearance(const std::string& low, const World& world) const {
        std::vector<std::string> tokens;
        for (const auto& entry : world.appearance_reactions.fields())
            tokens.push_back(entry.first);
        std::sort(tokens.begin(), tokens.end());          // Python's `sorted(...)`
        for (const std::string& token : tokens) {
            if (!token.empty() && token[0] == '_') continue;
            std::size_t colon = token.rfind(':');
            std::string tail = colon == std::string::npos ? token
                                                          : token.substr(colon + 1);
            std::replace(tail.begin(), tail.end(), '_', ' ');
            if (low.find(token) != std::string::npos) return Json(token);
            // An EMPTY tail matches everything, because "" is a substring of any
            // string. Faithful rather than guarded: a token authored as "item:"
            // does answer to every line in Python, and a port that quietly fixed
            // that would disagree with a fixture that happens to contain one.
            if (low.find(tail) != std::string::npos) return Json(token);
            std::vector<std::string> tail_words = py_split(tail);
            if (!tail_words.empty()) {
                const std::string& last = tail_words.back();
                for (const std::string& word : py_split(low))
                    if (word == last) return Json(token);
            }
        }
        return Json();
    }

private:
    static ParsedCommand command(const std::string& raw, const char* intent,
                                 double confidence, const std::string& player_id,
                                 const char* code, double amount,
                                 Json detail = Json::object()) {
        ParsedCommand out;
        out.raw_text = raw;
        out.intent = intent;
        out.confidence = confidence;
        out.actor_id = player_id;
        out.metadata = Json::object();
        // A reason is a TUPLE in Python. Reproduced as a three-element array so
        // it exports the same way rather than as an object with invented keys.
        Json reason = Json::array();
        reason.push(std::string(code));
        reason.push(amount);
        reason.push(detail);
        out.reasons.push_back(reason);
        return out;
    }

    static std::optional<Proposition> topic_proposition(const World& world,
                                                        const std::string& topic_id,
                                                        const std::string& player_id,
                                                        bool assertion) {
        if (topic_id.empty()) return std::nullopt;
        const Topic* topic = world.topics.find(topic_id);
        if (!topic) return std::nullopt;
        Json data = assertion ? topic->resolved_player_assertion(player_id)
                              : topic->resolved_player_claim(player_id);
        if (!data.truthy()) return std::nullopt;
        return Proposition::from_json(data);
    }

    /// `re.search(r"(\d+)\s*(m|min|minute|minutes|minuten|h|hour|hours|stunden)?")`.
    ///
    /// The alternation is ORDERED, which matters more than it looks: against
    /// "30min" the group tries "m" first and takes it, so the unit is "m" and
    /// not "min". The answer is the same either way here, and would not be if
    /// somebody reordered the pattern.
    static std::optional<long long> extract_minutes(const std::string& text) {
        std::size_t at = 0;
        while (at < text.size() && !detail_::is_digit(text[at])) ++at;
        if (at >= text.size()) return std::nullopt;
        std::size_t end = at;
        while (end < text.size() && detail_::is_digit(text[end])) ++end;
        long long value = std::stoll(text.substr(at, end - at));

        std::size_t after = end;
        while (after < text.size() && (text[after] == ' ' || text[after] == '\t'
                                       || text[after] == '\n' || text[after] == '\r'
                                       || text[after] == '\v' || text[after] == '\f'))
            ++after;
        std::string unit = "m";
        for (const char* candidate : {"m", "min", "minute", "minutes", "minuten",
                                      "h", "hour", "hours", "stunden"}) {
            if (text.compare(after, std::strlen(candidate), candidate) == 0) {
                unit = candidate;
                break;
            }
        }
        bool hours = unit.rfind("h", 0) == 0 || unit.rfind("hour", 0) == 0
                  || unit.rfind("stund", 0) == 0;
        return hours ? value * 60 : value;
    }

    /// `re.search(r"(\d+)")` -- the first run of digits anywhere in the line.
    ///
    /// `\d` in a Python `str` pattern matches any Unicode decimal digit, not
    /// only ASCII. A line typed in Arabic-Indic numerals would part here and
    /// agree nowhere else; ASCII is what the packs and the fixtures contain, and
    /// saying so is better than implying a match that was never checked.
    static std::optional<std::string> extract_amount(const std::string& text) {
        std::size_t at = 0;
        while (at < text.size() && !detail_::is_digit(text[at])) ++at;
        if (at >= text.size()) return std::nullopt;
        std::size_t end = at;
        while (end < text.size() && detail_::is_digit(text[end])) ++end;
        return text.substr(at, end - at);
    }

    OrderedMap<std::vector<std::string>> override_;
    bool has_override_ = false;
};

}  // namespace usc
