// `usc/content.py`. Authored world content: topics, secrets, the alias index.
//
// Everything here is CONTENT, not engine. It exists because the reference
// scene's vocabulary -- which places connect to which, what "the medic" refers
// to, which words would give a secret away -- used to live in Python constants
// inside the SDK. That made the runtime look engine-independent while in
// practice only one pack was playable: a second one loaded, validated, and then
// could not be navigated or talked to.
//
// The rule this enforces: the engine knows the SHAPE of content, never a
// particular world's content. Adding a world means writing JSON, and a pack can
// be authored in any language because its aliases travel with it.
#pragma once

#include <algorithm>
#include <cctype>
#include <tuple>
#include <set>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/pystr.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"

namespace usc {

inline constexpr const char* PLAYER_TOKEN = "$player";
inline constexpr const char* ADDRESSEE_TOKEN = "$addressee";

/// Recursively replace `$token` strings anywhere in authored JSON.
///
/// A whole-string match, not a substring one: `"$player"` becomes the id and
/// `"ask $player about it"` does not. That is what the Python does, and widening
/// it would let a pack's prose be rewritten by accident.
inline Json substitute(const Json& value, const OrderedMap<std::string>& bindings) {
    if (value.kind() == Json::Kind::String) {
        const std::string* bound = bindings.find(value.as_string());
        return bound ? Json(*bound) : value;
    }
    if (value.kind() == Json::Kind::Object) {
        Json out = Json::object();
        for (const auto& entry : value.fields())
            out.fields()[entry.first] = substitute(entry.second, bindings);
        return out;
    }
    if (value.kind() == Json::Kind::Array) {
        Json out = Json::array();
        for (const Json& item : value.items()) out.push(substitute(item, bindings));
        return out;
    }
    return value;
}

/// Substitute `$player` / `$addressee` in an authored template. A falsy
/// template -- absent, null, or an empty object -- resolves to nothing.
inline Json resolve_template(const Json& tmpl, const std::string& player_id,
                             const std::string& addressee_id = "") {
    bool empty = tmpl.is_null()
              || (tmpl.kind() == Json::Kind::Object && tmpl.fields().empty())
              || (tmpl.kind() == Json::Kind::Array && tmpl.items().empty())
              || (tmpl.kind() == Json::Kind::String && tmpl.as_string().empty());
    if (empty) return Json();
    OrderedMap<std::string> bindings;
    bindings[PLAYER_TOKEN] = player_id;
    if (!addressee_id.empty()) bindings[ADDRESSEE_TOKEN] = addressee_id;
    return substitute(tmpl, bindings);
}

/// A subject the player can raise, and what the world does about it.
struct Topic {
    std::string topic_id;
    std::string label;
    std::vector<std::string> aliases;
    /// The proposition a belief must be relevant to for an answer to count.
    Json query;
    /// What ASKING asserts. Raising a subject is itself information the NPC now
    /// holds about the player.
    Json player_claim;
    /// What TELLING asserts.
    Json player_assertion;
    /// Events the world fires when this comes up. Asking a fixer about her
    /// hidden brother is a threat to her, and that is a fact about this world,
    /// not about dialogue systems in general.
    std::vector<Json> reactions;
    /// How a character phrases an answer, per stance and register. Without these
    /// the engine will not assert anything about this world.
    Json phrasings = Json::object();

    static Topic from_json(const Json& data) {
        Topic out;
        out.topic_id = data.at("id").as_string();
        const Json* label = data.find("label");
        // `data.get("label") or topic_id` -- truthiness, so an empty label falls
        // back to the id rather than rendering as nothing.
        out.label = (label && !label->is_null() && !label->py_str().empty())
                  ? label->py_str() : out.topic_id;
        for (const Json& alias : data.at("aliases").items())
            out.aliases.push_back(alias.py_str());
        out.query = data.get("query");
        out.player_claim = data.get("player_claim");
        out.player_assertion = data.get("player_assertion");
        for (const Json& reaction : data.at("reactions").items())
            out.reactions.push_back(reaction);
        const Json* phrasings = data.find("phrasings");
        if (phrasings && phrasings->kind() == Json::Kind::Object) out.phrasings = *phrasings;
        return out;
    }

    Json resolved_query(const std::string& player_id) const {
        return resolve_template(query, player_id);
    }
    Json resolved_player_claim(const std::string& player_id) const {
        return resolve_template(player_claim, player_id);
    }
    Json resolved_player_assertion(const std::string& player_id) const {
        return resolve_template(player_assertion, player_id);
    }

    /// Register variants for affirming or denying this topic's query.
    Json phrasing_for(bool affirmed) const {
        const Json* found = phrasings.find(affirmed ? "affirm" : "deny");
        if (!found || found->kind() != Json::Kind::Object) return Json::object();
        return *found;
    }

    std::vector<Json> resolved_reactions(const std::string& player_id,
                                         const std::string& addressee_id = "") const {
        std::vector<Json> out;
        for (const Json& reaction : reactions)
            out.push_back(resolve_template(reaction, player_id, addressee_id));
        return out;
    }
};

/// A `protects` entry may be a proposition template or an already-canonical key.
///
/// Authors write `{"predicate": ..., "slots": {...}}` and this canonicalises it.
/// Making a human type `pred(a=1,b=2)[None,None,None]` by hand would be an
/// invitation to typo a security control into silence.
inline std::string protected_key(const Json& entry) {
    if (entry.kind() == Json::Kind::Object)
        return Proposition::from_json(entry).core_key();
    return entry.py_str();
}

/// Something a character will not say, and the words that would give it away.
struct Secret {
    std::string secret_id;
    /// The coarse tag handed to the dialogue planner and the validator. It names
    /// the SHAPE of the forbidden area, never its content, so the secret cannot
    /// leak by sitting in a prompt.
    std::string avoid_label = "protected_topic";
    /// Topics the holder refuses while trust is below `min_trust`. This is what
    /// turns a secret into behaviour rather than a filter.
    std::vector<std::string> guards_topics;
    /// For authors and the inspector. Never placed in a prompt, never sent to a
    /// text provider.
    std::string summary;
    /// What the validator scans released text for -- the last line of defence
    /// when an external model writes the line. Pack-owned, because it is this
    /// world's vocabulary: "back room" is a leak in Block 17 and meaningless
    /// anywhere else.
    std::vector<std::string> surface_forms;
    std::vector<std::string> protects;
    /// Every world id named in a slot of a protected proposition. `protects`
    /// keeps canonical KEYS, which is the right identity for filtering beliefs
    /// and the wrong one for reading a sentence back: a released line that names
    /// the place a secret is about has given it away whatever wording it used.
    std::vector<std::string> protected_ids;
    /// Agent ids this secret concerns. Drives leverage.
    std::vector<std::string> about;
    double min_trust = 0.45;
    /// What the holder says INSTEAD, when they would rather lie than deflect.
    /// A proposition template, so the lie is authored world content like
    /// everything else -- the engine will not invent a cover story any more than
    /// it invents a fact. Without one a cornered character deflects, which is
    /// the honest default: silence is refusal, and refusal is information.
    Json cover_story;
    Json cover_phrasings = Json::object();

    static Secret from_json(const Json& data) {
        Secret out;
        if (data.kind() == Json::Kind::String) {
            // A bare string names a protected proposition and nothing else.
            // Accepted so a pack can start small; pack validation warns, because
            // without surface forms there is no protection against an external
            // model phrasing the secret in its own words.
            out.secret_id = data.as_string();
            out.protects = {data.as_string()};
            return out;
        }
        out.secret_id = data.at("id").as_string();
        const Json* label = data.find("avoid_label");
        if (label && !label->is_null() && !label->py_str().empty())
            out.avoid_label = label->py_str();
        for (const Json& one : data.at("guards_topics").items())
            out.guards_topics.push_back(one.py_str());
        const Json* summary = data.find("summary");
        if (summary && !summary->is_null()) out.summary = summary->py_str();
        for (const Json& one : data.at("surface_forms").items())
            out.surface_forms.push_back(one.py_str());
        for (const Json& one : data.at("protects").items()) {
            out.protects.push_back(protected_key(one));
            if (one.kind() != Json::Kind::Object) continue;
            const Json* slots = one.find("slots");
            if (slots == nullptr || slots->kind() != Json::Kind::Object) continue;
            for (const auto& slot : slots->fields()) {
                std::string token = slot.second.py_str();
                if (token.find(':') == std::string::npos) continue;
                if (std::find(out.protected_ids.begin(), out.protected_ids.end(), token)
                    == out.protected_ids.end())
                    out.protected_ids.push_back(token);
            }
        }
        for (const Json& one : data.at("about").items())
            out.about.push_back(one.py_str());
        const Json* trust = data.find("min_trust");
        if (trust && !trust->is_null()) out.min_trust = trust->as_double();
        out.cover_story = data.get("cover_story");
        const Json* phrasings = data.find("cover_phrasings");
        if (phrasings && phrasings->kind() == Json::Kind::Object) out.cover_phrasings = *phrasings;
        return out;
    }

    bool covers(const std::string& proposition_key, const std::string& rendered = "") const {
        auto has = [&](const std::string& what) {
            return std::find(protects.begin(), protects.end(), what) != protects.end();
        };
        return has(proposition_key) || (!rendered.empty() && has(rendered));
    }
};

/// Longest-match lookup from free text to a world id.
///
/// Longest-first matters: "police post" must beat "police", or `go police post`
/// resolves to an officer instead of a place.
struct AliasIndex {
    std::vector<std::pair<std::string, std::string>> entries;

    static AliasIndex build(const Json& alias_map) {
        AliasIndex out;
        for (const auto& target : alias_map.fields())
            for (const Json& alias : target.second.items()) {
                std::string text = alias.py_str();
                if (text.empty()) continue;            // `if alias` -- truthiness
                text = py_lower(text);
                out.entries.emplace_back(text, target.first);
            }
        // `key=lambda pair: (-len(pair[0]), pair[0])` -- longest first, then
        // alphabetically, so the order does not depend on the map's iteration.
        std::sort(out.entries.begin(), out.entries.end(),
                  [](const auto& a, const auto& b) {
                      if (a.first.size() != b.first.size())
                          return a.first.size() > b.first.size();
                      return a.first < b.first;
                  });
        return out;
    }

    std::string match(const std::string& text,
                      const std::vector<std::string>& exclude = {}) const {
        for (const auto& entry : entries) {
            if (std::find(exclude.begin(), exclude.end(), entry.second) != exclude.end())
                continue;
            if (text.find(entry.first) != std::string::npos) return entry.second;
        }
        return "";
    }

    /// Aliases claimed by more than one target -- an authoring error.
    std::vector<std::tuple<std::string, std::string, std::string>> conflicts() const {
        OrderedMap<std::string> seen;
        std::vector<std::tuple<std::string, std::string, std::string>> clashes;
        for (const auto& entry : entries) {
            const std::string* first = seen.find(entry.first);
            if (first && *first != entry.second)
                clashes.emplace_back(entry.first, *first, entry.second);
            if (!first) seen[entry.first] = entry.second;
        }
        return clashes;
    }
};

inline std::vector<Secret> secrets_from(const Json& data) {
    std::vector<Secret> out;
    for (const Json& entry : data.items()) out.push_back(Secret::from_json(entry));
    return out;
}

/// Every proposition key any of these secrets covers. A `set` in Python and a
/// `std::set` here, because it is only ever asked "is this in it".
inline std::set<std::string> protected_keys(const std::vector<Secret>& secrets) {
    std::set<std::string> keys;
    for (const Secret& secret : secrets)
        keys.insert(secret.protects.begin(), secret.protects.end());
    return keys;
}

/// Secrets whose holder refuses to discuss this conversation topic.
inline std::vector<Secret> secrets_guarding(const std::vector<Secret>& secrets,
                                            const std::string& topic_id) {
    std::vector<Secret> out;
    for (const Secret& secret : secrets)
        if (std::find(secret.guards_topics.begin(), secret.guards_topics.end(), topic_id)
            != secret.guards_topics.end()) out.push_back(secret);
    return out;
}

/// Coarse labels the dialogue planner may expose. Never contains secret content,
/// and de-duplicated in FIRST-APPEARANCE order rather than sorted.
inline std::vector<std::string> avoid_labels(const std::vector<Secret>& secrets) {
    std::vector<std::string> out;
    for (const Secret& secret : secrets)
        if (std::find(out.begin(), out.end(), secret.avoid_label) == out.end())
            out.push_back(secret.avoid_label);
    return out;
}

/// Whether a secret is worth lying about, given how truthful its holder is.
///
/// `Agent` cannot see `Secret` -- it is a layer below -- so the rule lives on the
/// agent and this reads the two fields off the secret for it.
inline bool has_cover_story(const Secret& secret) {
    // Python's `if not template: return None` in the caller, and truthiness
    // here: a cover story authored as an empty object is no cover story.
    return secret.cover_story.truthy();
}

/// Validator input: avoid-label -> the strings that would give the secret away.
/// avoid-label -> the world ids its secrets are about.
inline OrderedMap<std::set<std::string>> protected_ids_by_label(
        const std::vector<Secret>& secrets) {
    OrderedMap<std::set<std::string>> table;
    for (const Secret& secret : secrets) {
        if (secret.protected_ids.empty()) continue;
        std::set<std::string>& bucket = table[secret.avoid_label];
        bucket.insert(secret.protected_ids.begin(), secret.protected_ids.end());
    }
    return table;
}

inline OrderedMap<std::vector<std::string>> surface_forms_by_label(
        const std::vector<Secret>& secrets) {
    OrderedMap<std::vector<std::string>> forms;
    for (const Secret& secret : secrets) {
        std::vector<std::string>& bucket = forms[secret.avoid_label];
        bucket.insert(bucket.end(), secret.surface_forms.begin(), secret.surface_forms.end());
    }
    return forms;
}

}  // namespace usc
