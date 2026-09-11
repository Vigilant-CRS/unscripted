// `usc/appearance.py`. How somebody is read before they have said anything.
//
// Every character in every shipped pack authors an appearance -- a garment, and
// sometimes a symbol worn on it -- and until this existed exactly one thing read
// it: the character generator, to write a sentence of description.
// `social_status` even promised in its own docstring to be "reputation- and
// appearance-mediated" and consulted only reputation.
//
// Two effects, because a player notices two and they are not the same thing:
// STATUS is how seriously somebody is taken, which lands on perceived social
// status and therefore on the register -- it changes how they are spoken to
// before anybody knows anything about them. THREAT is how dangerous they seem;
// gang colours are not low-status, they are something else entirely, and that
// difference is the whole reason there are two numbers.
//
// INERT UNTIL A PACK SAYS OTHERWISE. With no `appearance_reactions` -- and no
// shipped pack has one -- every read is empty and a run reproduces
// byte-identically. That is why this is not an optional layer with a flag:
// authored data defaulting to nothing needs no switch, and a switch nobody has
// to set is a switch nobody has to read about.
//
// WHAT IT DELIBERATELY DOES NOT DO: change what anybody believes. Being read as
// dangerous makes a character wary of you; it does not make them think you did
// anything. Evidence comes from events, and a coat is not evidence.
#pragma once

#include <algorithm>
#include <cmath>
#include <set>
#include <string>
#include <vector>

#include "usc/actions.hpp"
#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/types.hpp"

namespace usc {

/// Effect of being read as dangerous on what a character would rather do. The
/// same order as the outcome values already in the catalogue -- evading is worth
/// +0.3 safety -- and not larger: how somebody is dressed should tip a close
/// call and lose to what they have actually done.
inline constexpr double THREAT_PULL = 0.35;

/// And of being read as somebody worth taking seriously. Lower, because status
/// works through the register rather than through the decision.
inline constexpr double STATUS_PULL = 0.15;

/// Which actions a reading pushes, and which way. PUSHES rather than value
/// terms: terms inside a group are averaged, so a modifier contributed as a term
/// can lower the thing it meant to raise -- which is exactly what happened, and
/// somebody dressed to look dangerous made a character LESS likely to back away.
inline const OrderedMap<double>& threat_actions() {
    static const OrderedMap<double>* table = [] {
        auto* fresh = new OrderedMap<double>();
        (*fresh)["evade"] = +1.0;
        (*fresh)["greet"] = -0.7;
        (*fresh)["answer_truthfully"] = -0.5;
        return fresh;
    }();
    return *table;
}

inline const OrderedMap<double>& status_actions() {
    static const OrderedMap<double>* table = [] {
        auto* fresh = new OrderedMap<double>();
        (*fresh)["answer_truthfully"] = +1.0;
        (*fresh)["greet"] = +0.6;
        return fresh;
    }();
    return *table;
}

struct AppearanceReading {
    double status = 0.0;
    double threat = 0.0;
    std::vector<std::string> signals;
    std::vector<std::string> tokens;
};

class AppearanceEngine {
public:
    static constexpr const char* MODULE_ID = "appearance";

    /// Every appearance token: garment first, then symbols.
    ///
    /// Authored as `{"garment": "item:apron", "symbols": ["sym:reds"]}`, and a
    /// pack may add any key it likes -- `mask`, `boots`, `scars` -- with the
    /// reactions table deciding which of them mean anything here. The keys are
    /// walked SORTED, not in authored order, so two packs listing the same
    /// wardrobe differently read the same.
    std::vector<std::string> tokens(const Agent& agent) const {
        std::vector<std::string> keys;
        for (const auto& entry : agent.appearance.fields()) keys.push_back(entry.first);
        std::sort(keys.begin(), keys.end());

        std::vector<std::string> found;
        for (const std::string& key : keys) {
            const Json& value = agent.appearance.at(key);
            if (value.kind() == Json::Kind::String) {
                found.push_back(value.as_string());
            } else if (value.kind() == Json::Kind::Array) {
                for (const Json& one : value.items()) found.push_back(one.py_str());
            }
        }
        return found;
    }

    /// How `observer` reads `agent`.
    AppearanceReading read(const Agent* observer, const Agent& agent,
                           const Json& appearance_reactions) const {
        AppearanceReading out;
        out.tokens = tokens(agent);
        bool no_reactions = appearance_reactions.kind() != Json::Kind::Object
                         || appearance_reactions.fields().empty();
        if (no_reactions || out.tokens.empty()) return out;

        // Not everybody judges a coat equally. 1.0 unless a pack says otherwise,
        // 0.0 for somebody who genuinely does not care what you are wearing.
        double sensitivity = 1.0;
        if (observer) {
            const Json* declared = observer->epistemic.find("appearance_sensitivity");
            if (declared && declared->is_number()) sensitivity = declared->as_double();
        }
        sensitivity = clamp01(sensitivity);

        double status = 0.0, threat = 0.0;
        for (const std::string& token : out.tokens) {
            const Json* spec = appearance_reactions.find(token);
            // `if not spec: continue` -- truthiness, so an empty reaction table
            // entry is not a reaction. UNOBSERVABLE for well-formed data and
            // kept anyway: reading `{}` yields zero status, zero threat and no
            // signal, which is what skipping it produces. It differs only on a
            // reaction authored as something that is not an object at all, where
            // Python raises and this skips -- and a case for that would be
            // testing the loader, not this.
            if (!spec || spec->kind() != Json::Kind::Object || spec->fields().empty())
                continue;
            const Json* status_value = spec->find("status");
            const Json* threat_value = spec->find("threat");
            if (status_value) status += status_value->as_double();
            if (threat_value) threat += threat_value->as_double();
            const Json* signal = spec->find("signals");
            if (signal && !signal->is_null() && !signal->py_str().empty()) {
                std::string named = signal->py_str();
                if (std::find(out.signals.begin(), out.signals.end(), named)
                    == out.signals.end()) out.signals.push_back(named);
            }
        }
        // Status is bipolar; threat is not. Being read as harmless is the
        // absence of threat, not its negative.
        out.status = clamp_signed(status) * sensitivity;
        out.threat = clamp01(threat) * sensitivity;
        return out;
    }

    /// How far this observer is drawn to how this person looks, in [0, 1].
    ///
    /// A SEPARATE AXIS, not a flavour of liking. You can be drawn to somebody
    /// you neither trust nor respect, and a runtime that folded this into liking
    /// could not tell an author which of the two it had modelled.
    ///
    /// Authored, and only authored: `epistemic.drawn_to` lists the tokens a
    /// character is taken with. There is no engine deciding what is attractive,
    /// because that is a fact about a person and a setting rather than about
    /// software, and inventing one would put a number where a characterisation
    /// belongs.
    ///
    /// Familiarity is deliberately absent. Being struck by a stranger across a
    /// room is the case worth modelling; growing fond of somebody over years is
    /// `liking`, which already exists and already moves.
    double drawn_to(const Agent* observer, const Agent& agent) const {
        if (!observer) return 0.0;
        const Json* declared = observer->epistemic.find("drawn_to");
        if (!declared) return 0.0;
        std::set<std::string> wanted;
        for (const Json& one : declared->items()) wanted.insert(one.py_str());
        if (wanted.empty()) return 0.0;

        std::vector<std::string> seen = tokens(agent);
        if (seen.empty()) return 0.0;
        std::set<std::string> hits;
        for (const std::string& token : seen)
            if (wanted.count(token)) hits.insert(token);
        if (hits.empty()) return 0.0;

        // Two things they are taken with is more than one, and four is not four
        // times one. Saturating, because being struck by somebody does not add up.
        return std::min(1.0, 0.55 * std::pow(static_cast<double>(hits.size()), 0.5));
    }

    /// How a reading pulls what this character would rather do.
    ///
    /// Kept separate from the standing layer on purpose: standing is what you
    /// have DONE and this is what you LOOK like, and a runtime that mixed them
    /// could not tell a studio which of the two it was reacting to.
    double bias_for(const Agent* observer, const ActionDefinition& action,
                    const Agent* other, const Json& appearance_reactions) const {
        if (!other) return 0.0;
        if (action.target.is_null() || action.target.py_str() != other->id) return 0.0;
        AppearanceReading reading = read(observer, *other, appearance_reactions);

        double pushed = 0.0;
        struct Channel { const OrderedMap<double>& table; double pull; double amount; };
        const Channel channels[] = {{threat_actions(), THREAT_PULL, reading.threat},
                                    {status_actions(), STATUS_PULL, reading.status}};
        for (const Channel& channel : channels) {
            if (std::fabs(channel.amount) < 1e-3) continue;
            const double* direction = channel.table.find(action.action_id);
            if (!direction) continue;
            pushed += channel.pull * (*direction) * channel.amount;
        }
        return pushed;
    }
};

}  // namespace usc
