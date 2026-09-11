// `usc/validator.py`. The last thing that runs before a line reaches a player.
//
// BUFFERED generation: the utterance is produced in full, validated, and only
// then released. Nothing unvalidated is ever streamed, because streaming leaks.
//
//   0  context minimisation -- forbidden content never enters the prompt at all
//   3a secret-token / alias scan over released text
//   3b canon -- the speaker may not assert specifics it was not licensed to
//   3c repetition guard
//   4  fallback to a deterministic, validated line
//
// Layer 3b matters only when an external model writes the line, which is
// precisely the case this runtime is sold for. The deterministic realizer emits
// authored text and is correct by construction; a language model is not. Before
// this layer existed the check was a comment, and a model could invent any name,
// place, quantity or event and the runtime would hand it to the player:
//
//     check("The mayor was murdered by Kane in the harbour last Tuesday.") -> ACCEPT
//
// The rule is narrow and deterministic, which is what makes it trustworthy:
// PROPER NOUNS AND NUMBERS CARRY FACTUAL SPECIFICITY, and every one of them in
// provider output must be licensed by the plan. Ordinary words carry stance and
// are left alone -- the model is free to phrase, not to invent.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/content.hpp"
#include "usc/dialogue.hpp"
#include "usc/grounding.hpp"
#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pystr.hpp"
#include "usc/world.hpp"

namespace usc {

inline constexpr const char* ACCEPT = "ACCEPT";

inline constexpr const char* REJECT_HARD = "REJECT_HARD";
inline constexpr const char* REJECT_SOFT = "REJECT_SOFT";

/// Canon enforcement levels.
inline constexpr const char* CANON_OFF = "off";       // no parse-back
inline constexpr const char* CANON_WARN = "warn";     // report but release
inline constexpr const char* CANON_STRICT = "strict"; // reject (default externally)

/// Capitalised words that carry no factual reference and must not be mistaken
/// for an invented proper noun. Deliberately small: anything world-specific
/// belongs to a pack, and anything longer would start hiding real hallucinations.
inline const std::set<std::string>& neutral_capitals() {
    static const std::set<std::string>* words = new std::set<std::string>{
        "i", "i'm", "i've", "i'll", "i'd", "ok", "okay", "yes", "no", "sir",
        "ma'am", "mr", "mrs", "ms", "miss", "god", "hey", "well", "look",
        "listen", "sorry", "please", "thanks", "thank", "good", "morning",
        "afternoon", "evening", "night"};
    return *words;
}

struct ValidationResult {
    std::string verdict;
    std::vector<Json> reasons;
    std::vector<Json> unlicensed;
};

/// Reason codes that mean the LINE WAS UNSAFE, so the commitment behind it must
/// not reach the world. Repetition is deliberately not one: saying the same
/// thing twice is a quality problem, and treating it as safety let an earlier
/// sentence decide whether a later fact entered the society.
inline bool is_unsafe(const ValidationResult& result) {
    for (const Json& row : result.reasons) {
        std::string code = row.items().empty() ? std::string() : row.items()[0].py_str();
        if (code == "validator.secret_leak" || code == "validator.secret_referent"
            || code == "validator.canon_violation")
            return true;
    }
    return false;
}

namespace detail_ {

inline bool ascii_letter(char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
}
inline bool ascii_digit(char c) { return c >= '0' && c <= '9'; }
inline bool ascii_upper(char c) { return c >= 'A' && c <= 'Z'; }

/// `re.finditer(r"[A-Za-z][A-Za-z'\-]*", text)`.
inline std::vector<std::string> words_in(const std::string& text) {
    std::vector<std::string> out;
    std::size_t index = 0;
    while (index < text.size()) {
        if (!ascii_letter(text[index])) { ++index; continue; }
        std::size_t start = index++;
        while (index < text.size()
               && (ascii_letter(text[index]) || text[index] == '\'' || text[index] == '-'))
            ++index;
        out.push_back(text.substr(start, index - start));
    }
    return out;
}

/// `re.finditer(r"\d+(?:[.,]\d+)?", text)`. The fractional part is optional and
/// only taken when a digit follows the separator, so "300." yields "300".
inline std::vector<std::string> numbers_in(const std::string& text) {
    std::vector<std::string> out;
    std::size_t index = 0;
    while (index < text.size()) {
        if (!ascii_digit(text[index])) { ++index; continue; }
        std::size_t start = index;
        while (index < text.size() && ascii_digit(text[index])) ++index;
        if (index + 1 < text.size() && (text[index] == '.' || text[index] == ',')
            && ascii_digit(text[index + 1])) {
            ++index;
            while (index < text.size() && ascii_digit(text[index])) ++index;
        }
        out.push_back(text.substr(start, index - start));
    }
    return out;
}

/// `re.sub(r"[:_\-()=,.]+", " ", text)` -- a RUN of separators becomes ONE space.
inline std::string separators_to_space(const std::string& text) {
    auto separator = [](char c) {
        return c == ':' || c == '_' || c == '-' || c == '(' || c == ')'
            || c == '=' || c == ',' || c == '.';
    };
    std::string out;
    bool in_run = false;
    for (char c : text) {
        if (separator(c)) {
            if (!in_run) out += ' ';
            in_run = true;
        } else {
            out += c;
            in_run = false;
        }
    }
    return out;
}

}  // namespace detail_

class Validator {
public:
    static constexpr const char* MODULE_ID = "validator";
    static constexpr const char* VERSION = "0.7.0";

    /// avoid-label -> surface tokens that must never appear. These are WORLD
    /// VOCABULARY and come from the loaded pack's secrets: "back room" gives away
    /// a secret in one world and means nothing in another. This table used to be
    /// hardcoded here for a single character in a single pack, which meant every
    /// other secret in every other pack was unprotected.
    OrderedMap<std::vector<std::string>> secret_surface_forms;
    long long repetition_window = 3;
    /// term -> world id, for reporting WHICH referent was used without licence.
    OrderedMap<std::string> world_terms;
    std::string canon_mode = CANON_STRICT;
    /// The world itself, for grounding checks that need its vocabulary rather
    /// than a flattened term table. Optional: a validator built without one still
    /// does everything else.
    ///
    /// The grounding LEXICON is built once and kept beside it. Python caches the
    /// same thing on the world object and rebuilds it when the place, agent or
    /// entity counts change; here the validator owns it, because the validator is
    /// rebuilt per world by `for_world` and there is nowhere else it could go
    /// without giving `World` a dependency on `grounding`.
    const World* world = nullptr;
    WorldLexicon lexicon;
    /// avoid-label -> the world ids its secrets are about. Surface forms catch
    /// the phrasings a pack thought of; this catches the THING, in whatever
    /// words the world itself uses for it.
    OrderedMap<std::set<std::string>> protected_ids;

    /// A validator that knows this world's protected and canonical vocabulary.
    static Validator for_world(const World& setting,
                              const std::string& mode = CANON_STRICT,
                              long long window = 3) {
        Validator out;
        std::vector<Secret> secrets;
        for (const auto& entry : setting.agents)
            for (const Json& row : entry.second.secrets)
                secrets.push_back(Secret::from_json(row));
        out.secret_surface_forms = surface_forms_by_label(secrets);
        // What a secret is ABOUT, from both directions a pack can state it:
        // structurally when `protects` is a proposition, and from the give-away
        // phrases resolved through the world's own lexicon -- which is the half
        // that matters, because every shipped pack declares `protects` as an
        // opaque key and without it the layer would be inert in all of them.
        out.protected_ids = protected_ids_by_label(secrets);
        {
            WorldLexicon reading = WorldLexicon::build(setting);
            for (const Secret& secret : secrets) {
                std::set<std::string> named;
                for (const std::string& form : secret.surface_forms) {
                    std::set<std::string> hits = referenced_ids(form, reading);
                    named.insert(hits.begin(), hits.end());
                }
                if (!named.empty())
                    out.protected_ids[secret.avoid_label].insert(named.begin(), named.end());
            }
        }
        out.world_terms = terms_of(setting);
        out.world = &setting;
        out.lexicon = WorldLexicon::build(setting);
        out.canon_mode = mode;
        out.repetition_window = window;
        return out;
    }

    /// Avoid-labels with no surface forms -- the scan cannot see them.
    std::vector<std::string> unprotected_labels(
            const std::vector<std::string>& avoid_topics) const {
        std::vector<std::string> out;
        for (const std::string& topic : avoid_topics) {
            const std::vector<std::string>* forms = secret_surface_forms.find(topic);
            // `if not ...get(topic)` -- a label present with an EMPTY list is
            // just as unprotected as a label that is missing entirely.
            if (!forms || forms->empty()) out.push_back(topic);
        }
        return out;
    }

    /// Validate a fully generated utterance before release.
    ///
    /// `canon_mode` overrides the instance default for this call: the runtime
    /// passes CANON_OFF for its own deterministic output and the configured mode
    /// for text that came back from a provider.
    ValidationResult check(const std::string& utterance, const DialoguePlan& plan,
                           const Agent& agent,
                           const std::vector<std::string>& recent_utterances,
                           const std::string* mode_override = nullptr) const {
        (void)agent;   // Python takes it and does not read it; kept in the signature
        std::vector<Json> reasons;
        std::string low = py_lower(utterance);

        // Layer 3a: secret-token / alias scan for avoided topics.
        for (const std::string& topic : plan.avoid_topics) {
            const std::vector<std::string>* forms = secret_surface_forms.find(topic);
            if (!forms) continue;
            for (const std::string& form : *forms) {
                if (low.find(form) == std::string::npos) continue;
                Json why = Json::object();
                why["topic"] = topic;
                why["form"] = form;
                reasons.push_back(reason("validator.secret_leak", 1.0, why));
                return {REJECT_HARD, reasons, {}};
            }
        }

        // Layer 3a': the THING a secret is about, named in the world's own
        // words. Surface forms are a list of phrasings somebody thought of, and
        // a paraphrase is by definition a phrasing nobody thought of.
        if (world != nullptr && !protected_ids.empty()) {
            std::set<std::string> guarded;
            for (const std::string& topic : plan.avoid_topics) {
                const std::set<std::string>* ids = protected_ids.find(topic);
                if (ids) guarded.insert(ids->begin(), ids->end());
            }
            if (!guarded.empty()) {
                std::string licence = licence_text(plan);
                std::set<std::string> named = referenced_ids(utterance, lexicon);
                // What the pack's own phrasing for this answer names is licensed,
                // read with the same lexicon as the utterance. The licence text
                // compares ids, and a phrasing names things in the world's words,
                // so an authored cover story used to refuse itself.
                std::string phrased;
                for (const auto& entry : plan.phrasing.fields()) {
                    phrased += entry.second.py_str();
                    phrased += ' ';
                }
                std::set<std::string> authored = referenced_ids(phrased, lexicon);
                std::vector<std::string> leaked;
                for (const std::string& entity : guarded) {
                    if (!named.count(entity)) continue;
                    if (authored.count(entity)) continue;
                    std::string plain = WorldLexicon::lower(entity);
                    for (char& c : plain)
                        if (c == ':' || c == '_' || c == '-') c = ' ';
                    if (licence.find(plain) != std::string::npos) continue;
                    leaked.push_back(entity);
                }
                if (!leaked.empty()) {
                    Json why = Json::object();
                    Json rows = Json::array();
                    for (const std::string& one : leaked) rows.push(Json(one));
                    why["named"] = rows;
                    why["note"] = std::string("named something a protected claim "
                                              "is about, without licence to");
                    reasons.push_back(reason("validator.secret_referent",
                                             static_cast<double>(leaked.size()), why));
                    return {REJECT_HARD, reasons, {}};
                }
            }
        }

        // Layer 3b: canon parse-back.
        std::string mode = mode_override ? *mode_override : canon_mode;
        std::vector<Json> unlicensed;
        if (mode != CANON_OFF) {
            unlicensed = unlicensed_specifics(utterance, plan);
            // Nouns that assert something exists. A proper-noun rule cannot see
            // "the old mill by the river": no capital, no number, and a world
            // with no mill just had one placed in it by a sentence.
            if (world) {
                // One token, one finding. A word can trip both rules -- a
                // capitalised invented noun is a proper noun AND an invented
                // referent -- and reporting it twice makes the record read as two
                // problems where there is one.
                std::set<std::string> already;
                for (const Json& entry : unlicensed)
                    already.insert(py_lower(entry.at("token").py_str()));
                for (const Json& entry : unknown_referents(utterance, lexicon,
                                                           licence_text(plan)))
                    if (!already.count(py_lower(entry.at("token").py_str())))
                        unlicensed.push_back(entry);
            }
            if (!unlicensed.empty()) {
                Json detail = Json::object();
                Json listed = Json::array();
                for (const Json& entry : unlicensed) listed.push(entry);
                detail["unlicensed"] = listed;
                Json facts = Json::array();
                for (const std::string& fact : plan.allowed_facts) facts.push(fact);
                detail["licensed_facts"] = facts;
                if (mode == CANON_STRICT) {
                    reasons.push_back(reason("validator.canon_violation",
                                             static_cast<double>(unlicensed.size()),
                                             detail));
                    return {REJECT_SOFT, reasons, unlicensed};
                }
                reasons.push_back(reason("validator.canon_warning",
                                         static_cast<double>(unlicensed.size()),
                                         detail));
            }
        }

        // Layer 3c: repetition guard. `recent[-window:]` with a window of zero is
        // the WHOLE list in Python, not an empty one -- `x[-0:]` is `x[0:]`.
        std::size_t from = 0;
        if (repetition_window > 0
            && static_cast<std::size_t>(repetition_window) < recent_utterances.size())
            from = recent_utterances.size() - static_cast<std::size_t>(repetition_window);
        else if (repetition_window < 0)
            from = recent_utterances.size();   // `x[1:]` of a negative slice start
        bool repeated = false;
        for (std::size_t i = from; i < recent_utterances.size(); ++i)
            if (recent_utterances[i] == utterance) { repeated = true; break; }
        if (repeated) {
            reasons.push_back(reason("validator.repetition", 1.0, Json::object()));
            return {REJECT_SOFT, reasons, unlicensed};
        }

        reasons.push_back(reason("validator.accept", 0.0, Json::object()));
        return {ACCEPT, reasons, unlicensed};
    }

    /// Proper nouns and numbers the plan does not license.
    ///
    /// Licensed by: an allowed fact, the authored phrasing for this answer, the
    /// speaker or addressee, or being a neutral capitalised word. Everything else
    /// is a specific claim the speaker had no grounds to make.
    std::vector<Json> unlicensed_specifics(const std::string& utterance,
                                           const DialoguePlan& plan) const {
        std::string licence = licence_text(plan);
        std::vector<Json> found;

        for (const std::string& token : detail_::numbers_in(utterance)) {
            if (licence.find(token) != std::string::npos) continue;
            Json entry = Json::object();
            entry["kind"] = std::string("number");
            entry["token"] = token;
            found.push_back(entry);
        }

        for (const std::string& sentence : py_split_sentences(utterance)) {
            std::vector<std::string> words = detail_::words_in(sentence);
            for (std::size_t position = 0; position < words.size(); ++position) {
                const std::string& token = words[position];
                if (!detail_::ascii_upper(token[0])) continue;
                std::string lowered = py_lower(token);
                if (neutral_capitals().count(lowered) || lowered.size() < 2) continue;
                if (licence.find(lowered) != std::string::npos) continue;
                const std::string* known = world_terms.find(lowered);
                if (position == 0 && !known) {
                    // A sentence-initial capital is usually grammar, and an
                    // unknown word there cannot be told apart from an ordinary
                    // one. A NAMED world referent is different: "Kane told me."
                    // is never grammar, and skipping position 0 wholesale let
                    // exactly that through.
                    continue;
                }
                Json entry = Json::object();
                entry["kind"] = std::string("proper_noun");
                entry["token"] = token;
                if (known) {
                    // A real thing in this world that this speaker was not
                    // licensed to bring up -- more serious than an invented word.
                    entry["kind"] = std::string("unlicensed_referent");
                    entry["refers_to"] = *known;
                }
                found.push_back(entry);
            }
        }

        // De-duplicate while preserving order, so a repeated word is reported once.
        //
        // The KIND in the key cannot change the answer and a mutation of it is
        // not catchable: a number token is all digits and a word token is not, so
        // the two can never collide, and among words the kind is decided purely
        // by whether `world_terms` knows the lowered token. Kept because Python
        // keys on the pair, and because the day a fourth kind arrives the key is
        // already right.
        std::set<std::pair<std::string, std::string>> seen;
        std::vector<Json> unique;
        for (const Json& entry : found) {
            auto key = std::make_pair(entry.at("kind").py_str(),
                                      py_lower(entry.at("token").py_str()));
            if (seen.insert(key).second) unique.push_back(entry);
        }
        return unique;
    }

    /// Everything this plan authorises the speaker to be specific about.
    static std::string licence_text(const DialoguePlan& plan) {
        std::vector<std::string> parts = plan.allowed_facts;
        parts.push_back(plan.speaker);
        parts.push_back(plan.addressee);
        parts.push_back(plan.goal);
        for (const auto& entry : plan.phrasing.fields()) parts.push_back(entry.second.py_str());
        std::string joined;
        for (std::size_t i = 0; i < parts.size(); ++i) {
            if (i) joined += ' ';
            joined += parts[i];
        }
        // Ids read like "place:back_room"; separators become spaces so that the
        // word "room" in an utterance matches the id it came from.
        return py_lower(detail_::separators_to_space(joined));
    }

    /// Every name this world answers to -> the id it refers to.
    ///
    /// Used to tell "the model invented a word" from "the model named a real
    /// thing this character had no licence to mention", which is the more serious
    /// of the two.
    static OrderedMap<std::string> terms_of(const World& setting) {
        OrderedMap<std::string> terms;
        auto add = [&terms](const std::string& name, const std::string& target) {
            // `if name:` and then `setdefault` -- the FIRST claim on a name wins.
            if (name.empty()) return;
            std::string key = py_lower(name);
            if (!terms.contains(key)) terms[key] = target;
        };
        for (const auto& place : setting.places.fields()) {
            const Json* label = place.second.find("label");
            if (label) add(label->py_str(), place.first);
            const Json* aliases = place.second.find("aliases");
            if (aliases) for (const Json& alias : aliases->items())
                add(alias.py_str(), place.first);
        }
        for (const auto& entry : setting.agents) {
            const Agent& agent = entry.second;
            if (agent.public_name.truthy()) add(agent.public_name.py_str(), agent.id);
            if (agent.objective_name.truthy()) add(agent.objective_name.py_str(), agent.id);
            for (const std::string& alias : agent.aliases) add(alias, agent.id);
        }
        for (const auto& entity : setting.entities.fields()) {
            const Json* name = entity.second.find("name");
            if (name) add(name->py_str(), entity.first);
        }
        for (const auto& entry : setting.topics)
            for (const std::string& alias : entry.second.aliases)
                add(alias, entry.second.topic_id);
        return terms;
    }

private:
    static Json reason(const char* code, double amount, const Json& detail) {
        Json row = Json::array();
        row.push(std::string(code));
        row.push(amount);
        row.push(detail);
        return row;
    }
};

}  // namespace usc
