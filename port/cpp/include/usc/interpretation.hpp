// `usc/interpretation.py`. Seeing is not understanding.
//
// Perception decides who COULD observe an event. Everything after that used to
// be identical for everyone: a technician and a tourist in the same room
// acquired the same claim with the same slots, and competence only changed
// whether other people believed them afterwards. That is the wrong place for it.
//
// Three stages sit between an observation and a belief -- attention, recognition,
// interpretation -- and the third reuses the distortion processes rather than
// modelling the same phenomena twice: a layman losing the technical detail IS
// levelling, and reading an ambiguous scene as the thing you already fear IS
// assimilation.
#pragma once

#include <algorithm>
#include <cmath>
#include <optional>
#include <set>
#include <string>
#include <utility>
#include <vector>

#include "usc/agent.hpp"
#include "usc/belief.hpp"
#include "usc/determinism.hpp"
#include "usc/distortion.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/pyround.hpp"
#include "usc/world.hpp"

namespace usc {

namespace detail_ {

/// The domain a pack declared for this claim, or the street.
inline std::string domain_of(const Proposition& proposition, const World& world) {
    const Json* found = world.predicate_domains.find(proposition.predicate);
    return found ? found->py_str() : std::string("street");
}

/// `(domain, level)` a pack declared for IDENTIFYING this claim, or nothing.
inline std::optional<std::pair<std::string, double>> required_competence(
        const Proposition& proposition, const World& world) {
    const Json* need = world.predicate_competence.find(proposition.predicate);
    // Python's `if not need` -- an EMPTY declaration is no declaration, which is
    // not the same as a missing key and has to behave the same way.
    if (!need || !need->truthy()) return std::nullopt;
    const Json* domain = need->find("domain");
    const Json* level = need->find("level");
    return std::make_pair(domain ? domain->py_str() : std::string("street"),
                          level ? level->as_double() : 0.5);
}

}  // namespace detail_

/// Attention, recognition, interpretation.
class InterpretationEngine {
public:
    static constexpr const char* MODULE_ID = "interpretation";

    struct Params {
        /// Below this, an observer does not attend to the event at all.
        double attention_floor = 0.18;
        /// How much an event about a familiar person or place raises attention.
        double familiarity_weight = 0.35;
        /// How much the observer's role domain raises attention.
        double role_weight = 0.40;
        /// How far below the required competence an observer may be and still
        /// identify what they saw.
        double recognition_slack = 0.15;
    };

    Params params;

    InterpretationEngine() = default;
    explicit InterpretationEngine(Params settings) : params(settings) {}

    struct Attention {
        double score = 0.0;
        std::vector<Reason> reasons;
    };

    /// How much of this observer's attention this event gets, and why.
    ///
    /// Deliberately additive and small: this decides whether something is
    /// noticed, not what it means, and a model with many multiplied terms would
    /// make "noticed nothing" the common case.
    Attention attention(const Agent& agent, const Event& event,
                        const Proposition* proposition, const World& world,
                        double quality) const {
        // Python writes `(event.payload or {}).get(...)`. The `or {}` cannot
        // change the answer -- an empty payload has no key either way -- so it
        // is not reproduced, and a mutation of it is not catchable.
        const Json* declared = event.payload.find("importance");
        double importance = declared ? declared->as_double() : 0.5;
        Attention out;
        out.score = 0.35 + 0.5 * importance;

        if (proposition) {
            // A SET of the slot values as strings -- Python's `str(v)`, so a
            // missing value reads as "None" and an integer loses its type.
            std::set<std::string> about;
            for (const auto& slot : proposition->slots) about.insert(slot.second.py_str());

            if (about.count(agent.id)) {
                out.score += 0.5;
                out.reasons.push_back({"attention.about_me", 1.0, Json::object()});
            } else {
                bool familiar = false;
                for (const auto& known : agent.relationships)
                    if (about.count(known.first)) { familiar = true; break; }
                if (familiar) {
                    out.score += params.familiarity_weight;
                    out.reasons.push_back({"attention.familiar_subject",
                                           params.familiarity_weight, Json::object()});
                }
            }

            std::string domain = detail_::domain_of(*proposition, world);
            double competence = agent.competence_in(domain);
            if (competence >= 0.5) {
                out.score += params.role_weight * competence;
                Json why = Json::object();
                why["domain"] = domain;
                out.reasons.push_back({"attention.professional_interest",
                                       py_round(competence, 3), why});
            }
        }

        double curiosity = agent.trait("curiosity");
        if (std::fabs(curiosity - 0.5) > 1e-9) {
            double bonus = 0.4 * (curiosity - 0.5);
            out.score += bonus;
            out.reasons.push_back({"attention.curiosity", py_round(bonus, 3),
                                   Json::object()});
        }

        out.score *= std::max(0.1, quality);
        out.score = std::max(0.0, std::min(1.5, out.score));
        return out;
    }

    struct Recognition {
        bool known = true;
        double have = 1.0;
        std::string detail;
    };

    /// Can this observer identify what they are looking at?
    ///
    /// The requirement is world content: a pack declares what a claim takes to
    /// recognise, because "you need to be an engineer to see that this was
    /// deliberate" is a fact about a setting, not about an engine.
    Recognition recognises(const Agent& agent, const Proposition& proposition,
                           const World& world) const {
        auto need = detail_::required_competence(proposition, world);
        if (!need) return {true, 1.0, "no expertise required"};
        double have = agent.competence_in(need->first);
        bool ok = have >= need->second - params.recognition_slack;
        return {ok, have,
                need->first + " " + format_fixed(have, 2) + " vs "
                    + format_fixed(need->second, 2) + " required"};
    }

    struct Interpreted {
        /// Absent means the observer did not take it in at all -- a different
        /// state from disbelieving.
        std::optional<Proposition> proposition;
        std::vector<Reason> reasons;
    };

    /// Attend, recognise, interpret.
    ///
    /// A DIFFERENT proposition coming back means they took in something less
    /// specific, or something coloured by what they already expect -- which is
    /// the interesting case, and the one that makes four witnesses genuinely
    /// disagree while every account still traces to the same origin.
    Interpreted interpret(const Agent& agent, const Event& event,
                          const Proposition* proposition, const World& world,
                          double quality,
                          const std::string& modality = "sight") const {
        Interpreted out;
        Attention attended = attention(agent, event, proposition, world, quality);
        out.reasons = attended.reasons;

        if (attended.score < params.attention_floor) {
            Json why = Json::object();
            why["note"] = std::string("below attention floor; formed no belief");
            out.reasons.push_back({"interpretation.unnoticed",
                                   py_round(attended.score, 3), why});
            return out;
        }
        out.reasons.push_back({"interpretation.attended",
                               py_round(attended.score, 3), Json::object()});

        if (!proposition) return out;

        // Recognition is about IDENTIFYING something you perceived, not about
        // understanding a sentence. You can disbelieve a radio report that a seal
        // failed in Stores; you do not mishear "Stores" as "the med bay". When a
        // claim arrives in words the speaker has already done the identifying, so
        // competence decides whether you BELIEVE them -- which the belief engine
        // handles -- and not what you took in.
        if (modality == "hearing" || modality == "media") {
            Json why = Json::object();
            why["note"] = std::string("a stated claim needs no identifying; "
                                      "competence bears on credence instead");
            out.reasons.push_back({"interpretation.told_in_words", 1.0, why});
            out.proposition = *proposition;
            return out;
        }

        Recognition seen = recognises(agent, *proposition, world);
        if (seen.known) {
            Json why = Json::object();
            why["detail"] = seen.detail;
            out.reasons.push_back({"interpretation.recognised",
                                   py_round(seen.have, 3), why});
            out.proposition = *proposition;
            return out;
        }

        // Out of their depth. They saw something; they could not say what. The
        // claim they end up holding is a coarser one -- and it is still theirs,
        // first-hand, with the same origin, which is what keeps it accountable.
        std::vector<std::uint8_t> seed = derive_seed(
            world.global_seed, agent.id, event.event_id, world.world_time,
            MODULE_ID, "recognise");
        // How a scene you cannot read gets bent is a property of the reader. A
        // character who confirms what they already expect assimilates it towards
        // the familiar; one who does not simply loses the detail.
        double bias = agent.trait("confirmation_bias");
        OrderedMap<double> weights;
        weights[LEVELLING] = 1.0 - bias;
        weights[ASSIMILATION] = bias;
        weights[SHARPENING] = 0.0;
        weights[INVERSION] = 0.0;
        std::optional<Distortion> outcome =
            distort(*proposition, agent, world, seed, &weights);

        // UNREACHABLE, and worth saying so rather than leaving it as a silent
        // gap in the mutation count. `distort` tries all four processes in
        // turn, inversion last, and inversion cannot fail: negating a claim
        // always changes its polarity, so the "nothing changed" test never
        // rejects it. The only thing that could is a protected key, and
        // interpretation passes none -- what an observer secretly holds has no
        // bearing on what they managed to make out. The branch stays because
        // `distort` is free to grow a way to fail and this is the honest
        // answer if it does.
        if (!outcome) {
            Json why = Json::object();
            why["detail"] = seen.detail;
            why["note"] = std::string("could not identify it and could not simplify it; "
                                      "took it at face value");
            out.reasons.push_back({"interpretation.not_recognised",
                                   py_round(seen.have, 3), why});
            out.proposition = *proposition;
            return out;
        }

        Json why = Json::object();
        why["detail"] = seen.detail;
        why["process"] = outcome->kind;
        why["saw"] = proposition->str();
        why["understood"] = outcome->proposition.str();
        why["note"] = outcome->detail;
        out.reasons.push_back({"interpretation.misread", py_round(seen.have, 3), why});
        out.proposition = outcome->proposition;
        return out;
    }
};

/// Shared helper so any future stage draws from the same stream.
inline double interpretation_noise(const World& world, const std::string& agent_id,
                                   long long event_id, const std::string& salt) {
    return seeded_uniform(derive_seed(world.global_seed, agent_id, event_id,
                                      world.world_time, "interpretation", salt));
}

}  // namespace usc
