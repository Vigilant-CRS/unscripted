// `usc/sociolinguistics.py`. Register and style as a function of social
// position, education, group identity, audience, setting and affect.
//
// NOT A "GOOD VS BAD SPEECH" LADDER, and the framing matters. This models
// register and PRESTIGE variation -- formality, sentence length, lexical
// breadth, slang, politeness -- plus accommodation toward the interlocutor
// (Giles) and audience design (Bell). A low-status speaker is not "worse"; they
// use a different, fully competent variety. Education must not be equated with
// intelligence.
#pragma once

#include <algorithm>
#include <cmath>
#include <optional>
#include <string>

#include "usc/affect.hpp"
#include "usc/agent.hpp"
#include "usc/appearance.hpp"
#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/types.hpp"
#include "usc/world.hpp"
#include "usc/knob.hpp"

namespace usc {

struct StyleVector {
    double formality = 0.5;                  // [0,1]
    double lexical_sophistication = 0.5;
    double mean_sentence_length = 12.0;      // target tokens
    double slang_level = 0.0;                // [0,1]
    double directness = 0.5;
    double hedging = 0.3;
    Json dialect;
    Json jargon_domain;
    Json slang_lexicon;                      // vocab scheme id for in-group slang
    std::string politeness_strategy = "neutral";   // bald / positive / negative / off-record

    /// Rebuild from what `as_json` produced.
    ///
    /// Needed because the dialogue planner stores the ROUNDED dictionary on the
    /// plan, and the realizer then reads its register out of that -- so the
    /// numbers the text is chosen from are three decimal places, not the full
    /// ones this struct was computed with. A port that passed the unrounded
    /// vector straight through would pick a different register exactly on a
    /// threshold.
    static StyleVector from_json(const Json& doc) {
        StyleVector out;
        auto number = [&doc](const char* key, double fallback) {
            const Json* found = doc.find(key);
            return found && found->is_number() ? found->as_double() : fallback;
        };
        out.formality = number("formality", 0.5);
        out.lexical_sophistication = number("lexical_sophistication", 0.5);
        out.mean_sentence_length = number("mean_sentence_length", 12.0);
        out.slang_level = number("slang_level", 0.0);
        out.directness = number("directness", 0.5);
        out.hedging = number("hedging", 0.3);
        out.dialect = doc.get("dialect");
        out.jargon_domain = doc.get("jargon_domain");
        out.slang_lexicon = doc.get("slang_lexicon");
        const Json* politeness = doc.find("politeness_strategy");
        if (politeness && politeness->truthy()) out.politeness_strategy = politeness->py_str();
        return out;
    }

    /// Floats rounded for display, everything else as it is -- which is what
    /// `as_dict` does, and what the engine bridges send over the wire.
    Json as_json() const {
        Json out = Json::object();
        out["formality"] = py_round(formality, 3);
        out["lexical_sophistication"] = py_round(lexical_sophistication, 3);
        out["mean_sentence_length"] = py_round(mean_sentence_length, 3);
        out["slang_level"] = py_round(slang_level, 3);
        out["directness"] = py_round(directness, 3);
        out["hedging"] = py_round(hedging, 3);
        out["dialect"] = dialect;
        out["jargon_domain"] = jargon_domain;
        out["slang_lexicon"] = slang_lexicon;
        out["politeness_strategy"] = politeness_strategy;
        return out;
    }
};

/// Fallback when a pack authors no `formality` on a place.
inline constexpr double DEFAULT_SETTING_FORMALITY = 0.4;

class SociolinguisticEngine {
public:
    struct Params {
        double w_edu = 0.4;
        double w_setting = 0.3;
        double w_status = 0.2;
        double w_role = 0.2;
        double w_arousal = 0.4;
        double w_ingroup = 0.5;
        double lambda_accommodation = 0.4;
        double base_sentence_len = 8.0;
        double k_len = 12.0;
        double k_stress = 6.0;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("w_edu", &Params::w_edu),
            knob("w_setting", &Params::w_setting),
            knob("w_status", &Params::w_status),
            knob("w_role", &Params::w_role),
            knob("w_arousal", &Params::w_arousal),
            knob("w_ingroup", &Params::w_ingroup),
            knob("lambda_accommodation", &Params::lambda_accommodation),
            knob("base_sentence_len", &Params::base_sentence_len),
            knob("k_len", &Params::k_len),
            knob("k_stress", &Params::k_stress),
        };
        return table;
    }

    static constexpr const char* MODULE_ID = "sociolinguistics";

    SociolinguisticEngine() = default;
    explicit SociolinguisticEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    /// Continuous prestige in [0,1]. With an observer, the PERCEIVED status.
    ///
    /// This said "reputation- and appearance-mediated" from the day it was
    /// written and consulted reputation only, while every character in every
    /// shipped pack authored a garment that nothing read. It reads it now, when
    /// the pack says what a garment means; with no `appearance_reactions` the
    /// term is exactly zero and this returns what it always did.
    double social_status(const Agent& agent, const Agent* observer = nullptr,
                         const Json* appearance_reactions = nullptr,
                         const AppearanceEngine* appearance = nullptr) const {
        double base = agent.social_status;
        if (!observer) return clamp01(base);
        const OrderedMap<double>* view = observer->reputation.find(agent.id);
        double status = view ? view->get("status", 0.0) : 0.0;
        double perceived = 0.6 * base + 0.4 * clamp01(0.5 + 0.5 * status);
        if (appearance && appearance_reactions)
            perceived += 0.25 * appearance->read(observer, agent, *appearance_reactions).status;
        return clamp01(perceived);
    }

    /// `regard` carries the two feelings the register never had: fear, respect.
    ///
    /// Optional, and absent unless the standing layer is on, so a world that
    /// declines that mechanic produces byte-identical style.
    ///
    /// NOT the (agency, communion) pair from `InterpersonalEngine`, and the
    /// first attempt was. Communion is mostly liking again, and the
    /// accommodation step below has consulted liking since it was written -- so
    /// that version added a second copy of something already modelled and its
    /// effect vanished under the existing one, measured at 0.007 on directness,
    /// which is decoration. What fear and respect add is the part liking cannot
    /// express: you can be wary of somebody you like, and defer to somebody you
    /// do not.
    StyleVector compute_style(const Agent& agent,
                              const std::string& interlocutor = "",
                              const Json& place = Json(),
                              const World* world = nullptr,
                              const OrderedMap<double>* regard = nullptr,
                              const Json* appearance_reactions = nullptr,
                              const AppearanceEngine* appearance = nullptr,
                              bool use_affect_engine = false) const {
        // General education and vocabulary breadth -- NOT street competence. A
        // street-smart person may have low GENERAL register education, and
        // conflating the two is exactly the ladder this module refuses to be.
        double edu = agent.education.get("general", 0.35);
        double status = social_status(agent);
        double setting = world ? world->place_formality(place, DEFAULT_SETTING_FORMALITY)
                               : DEFAULT_SETTING_FORMALITY;

        double role_formal = 0.4;
        for (const Json& role : agent.roles) {
            const Json* name = role.find("role");
            if (!name) continue;
            std::string which = name->py_str();
            if (which == "role:bartender" || which == "role:officer" || which == "role:doctor") {
                role_formal = 0.7;
                break;
            }
        }

        double arousal = agent.affect.mood.a;
        double negative = std::max(0.0, -agent.affect.mood.p);
        double stress = clamp01(arousal * negative);
        double membership = has_argot(agent);
        // Vernacular pull from in-group membership, suppressed in a formal
        // setting -- which is code-switching, not inconsistency.
        double ingroup_pull = membership * (1.0 - setting);

        StyleVector style;
        style.formality = clamp01(params_.w_edu * edu + params_.w_setting * setting
                                  + params_.w_status * status + params_.w_role * role_formal
                                  - params_.w_arousal * stress
                                  - params_.w_ingroup * ingroup_pull);
        style.lexical_sophistication = clamp01(0.4 * edu + 0.6 * (edu * style.formality));
        double sentence = params_.base_sentence_len
                        + params_.k_len * style.lexical_sophistication * style.formality
                        - params_.k_stress * stress;
        style.mean_sentence_length = std::max(4.0, sentence);
        style.slang_level = clamp01(membership * (1.0 - style.formality));

        double anger = 0.0;
        if (use_affect_engine && !interlocutor.empty())
            anger = AffectEngine::emotions_toward(agent.affect, interlocutor).get("anger", 0.0);
        style.directness = clamp01(0.5 + 0.3 * (1 - agent.big_five.get("agreeableness", 0.5))
                                   - 0.3 * style.formality + 0.4 * anger);
        style.hedging = clamp01((1 - style.directness) * (0.4 + 0.4 * style.formality));
        style.dialect = agent.dialect;
        style.jargon_domain = best_domain(agent);
        style.slang_lexicon = style.slang_level > 0.2
            ? Json(std::string("vocab:reds_slang")) : Json();
        style.politeness_strategy = politeness(style.formality, style.directness);

        // Communication Accommodation Theory: converge toward a liked
        // interlocutor's register, diverge from a disliked one.
        if (!interlocutor.empty()) {
            const OrderedMap<double>* rel = agent.relationships.find(interlocutor);
            double liking = rel ? rel->get("liking", 0.0) : 0.0;
            double other_status = 0.5;
            if (world) {
                const Agent* other = world->agents.find(interlocutor);
                if (other) other_status = social_status(*other, &agent,
                                                        appearance_reactions, appearance);
            }
            double target = 0.5 + 0.5 * other_status;   // a high-status listener pulls up

            // CONVERGENCE AND DIVERGENCE ARE A DIAL, NOT A SWITCH.
            //
            // This used to be `1 if liking >= 0 else -1`, and that sign flip was
            // a cliff at exactly zero: a stranger, whose liking is 0.000, got
            // the FULL pull toward the other's register, and one small unkindness
            // later -- liking -0.15 -- got the full push away from it, taking
            // formality from 0.568 to 0.097. A whole register collapsing on a
            // fifteen-hundredth of a unit is not accommodation, and it saturated
            // the vector so completely that nothing else added to it could be
            // seen. Giles' theory is about degree: no feeling, no accommodation;
            // a little liking, a little convergence. Full strength at 0.5, which
            // is where a relationship here is unmistakable.
            double direction = (liking >= 0 ? 1.0 : -1.0)
                             * std::min(1.0, std::fabs(liking) * 2.0);
            style.formality = clamp01(style.formality + params_.lambda_accommodation
                                      * (target - style.formality) * direction);
        }

        // HOW SOMEBODY SPEAKS TO A PERSON THEY ARE WARY OF.
        //
        // Wariness makes people careful: they hedge, they stop being blunt, and
        // they reach for a more formal register than they otherwise would.
        // Respect makes them deferential without making them warm. Neither is
        // expressible through liking, which is why this exists -- and neither
        // had ever moved before conduct started producing them.
        // `if regard:` -- an empty mapping is FALSY in Python, and skipping it
        // is not cosmetic even though every term below would be zero.
        // `politeness_strategy` was set above from the formality BEFORE
        // accommodation, and the last line of this block recomputes it from the
        // formality after. So an empty regard that ran the block anyway would
        // change the strategy without changing a single number it is derived
        // from -- which is exactly the kind of difference nobody would look for.
        if (regard && !regard->empty()) {
            double fear = clamp01(regard->get("fear", 0.0));
            double respect = clamp01(regard->get("respect", 0.0));
            style.formality = clamp01(style.formality + 0.25 * fear + 0.15 * respect);
            style.directness = clamp01(style.directness - 0.30 * fear);
            style.hedging = clamp01(style.hedging + 0.30 * fear + 0.10 * respect);
            style.politeness_strategy = politeness(style.formality, style.directness);
        }
        return style;
    }

    static std::string politeness(double formality, double directness) {
        if (formality > 0.7 && directness < 0.5) return "negative";    // deferential
        if (formality < 0.3 && directness > 0.6) return "bald";        // no redress
        if (directness < 0.4) return "off_record";
        return "positive";
    }

private:
    /// Member of a group with an in-group vernacular.
    static double has_argot(const Agent& agent) {
        for (const Json& identity : agent.identities) {
            const Json* id = identity.find("id");
            if (id && id->py_str() == "gang_member") return 1.0;
        }
        return 0.0;
    }

    /// `max(agent.education, key=agent.education.get)` -- the domain they are
    /// best at, and on a TIE the one declared FIRST, because Python's `max`
    /// keeps the first maximum. A sorted container here would pick a different
    /// jargon for a character equally competent at two things.
    static Json best_domain(const Agent& agent) {
        if (agent.education.empty()) return Json();
        const std::string* best = nullptr;
        double highest = 0.0;
        for (const auto& entry : agent.education) {
            if (!best || entry.second > highest) { best = &entry.first; highest = entry.second; }
        }
        return Json(*best);
    }

    Params params_;
};

}  // namespace usc
