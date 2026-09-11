// `usc/standing.py`. What the town thinks of you, because of what it saw you do.
//
// The runtime already had two thirds of this and nobody had joined them up.
// Attack somebody in the open and the place closes up, the victim mobilises,
// and bystanders who share a belonging feel it threatened. What did NOT happen
// -- measured, not assumed -- was that anybody thought worse of YOU. Only a
// broken promise moved a player's standing, because `promises` was the one
// producer `ReputationEngine` ever had.
//
// WHY IT IS DRIVEN BY BELIEF AND NOT BY WITNESSING. The obvious implementation
// is a loop over everyone in the room, which gives you a reputation counter --
// every game has had one since 1997. This attaches a proposition to the act
// instead, `mistreated(who=victim, by=actor)`, and lets the existing machinery
// carry it: perceived, believed with provenance, passed on, decayed, doubted.
// Standing then moves in proportion to HOW MUCH THE HEARER BELIEVES IT.
//
// Three things fall out for free. Somebody who was not there can still come to
// think badly of you, because they were told. What you saw yourself weighs more
// than what you heard, because certainty scales the delta rather than a hop
// count somebody tuned. And a character can lie about what you did, and the lie
// moves standing exactly as far as it is believed -- no extra code, because it
// is a claim like any other.
//
// WHAT IT DOES NOT DO: touch personality, or decay on its own. A standing that
// quietly healed would let a player wait out a reputation, which is a design
// decision and not one this layer should make behind an author's back.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "usc/actions.hpp"
#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/statekey.hpp"
#include "usc/types.hpp"

namespace usc {

struct ConductSpec {
    std::string dimension = "decent";
    double sign = -1.0;
    double weight = 1.0;
};

/// Predicates this layer understands. Deliberately small: two covering cruelty
/// and kindness are enough to show the mechanic, and a pack that wants
/// "cheated", "stole from" or "stood up for" adds them in
/// `world.json: standing_conduct` -- what counts as decency is a fact about a
/// setting, not about an engine.
inline const OrderedMap<ConductSpec>& default_conduct() {
    static const OrderedMap<ConductSpec>* table = [] {
        auto* fresh = new OrderedMap<ConductSpec>();
        (*fresh)["mistreated"] = {"decent", -1.0, 1.0};
        (*fresh)["helped"] = {"decent", +1.0, 0.7};
        return fresh;
    }();
    return *table;
}

/// How far a single believed act moves the actor's standing, before certainty
/// and before how much the hearer cared about the victim.
///
/// Being kind is quieter than being cruel -- not a moral claim: an unkindness in
/// the street is remarked on and a kindness is mostly not, which is why the
/// positive weight above is lower and why nothing here is symmetric.
inline constexpr double BASE_STEP = 0.5;

/// How much survives when the hearer has no feeling about the victim at all.
/// Cruelty to a stranger still counts -- most of it does -- but cruelty to
/// someone you like counts for more.
inline constexpr double STRANGER_FLOOR = 0.6;

/// Standing never moves further than this from one act, however certain and
/// however beloved the victim. A single event should not make somebody's mind up
/// on its own; that is what repetition is for.
inline constexpr double MAX_STEP = 0.35;

/// Of a believed cruelty, how much becomes WARINESS OF YOU rather than dislike.
///
/// `fear` was read in three places and written in none: it decides whether a
/// threat is expected to work or to backfire, and it pulls a character's stance
/// away from warmth. This is wariness, not fright -- acute fear is an emotion
/// and lives in `affect`, where it decays over an afternoon; this is the part
/// that does not.
inline constexpr double FEAR_SHARE = 0.8;

/// And of a believed kindness, how much becomes STANDING rather than affection.
/// Lower than fear on purpose: one good turn is noted, one bad one is remembered.
inline constexpr double RESPECT_SHARE = 0.5;

/// How far what they think of you may move what they decide to do.
///
/// The same order as the outcome values already in the catalogue -- evading is
/// worth +0.3 safety -- and not larger. Standing should tip a close call and
/// lose to a character's own judgement about their safety. A number that
/// overrode that would produce an NPC who tells a stranger a secret because they
/// were nice once, which is worse than not modelling this at all.
inline constexpr double DECISION_PULL = 0.4;

/// Which way each action is pushed by warmth toward the person in front of you.
/// A PUSH and not a value term: terms within a group are averaged, so a modifier
/// contributed as a term can lower the very thing it meant to raise.
inline const OrderedMap<double>& warmth_pull() {
    static const OrderedMap<double>* table = [] {
        auto* fresh = new OrderedMap<double>();
        (*fresh)["answer_truthfully"] = +1.0;
        (*fresh)["greet"] = +0.6;
        (*fresh)["evade"] = -1.0;
        (*fresh)["threaten"] = -0.8;
        return fresh;
    }();
    return *table;
}

using StandingReason = Reason;

class StandingEngine {
public:
    static constexpr const char* MODULE_ID = "standing";

    StandingEngine() = default;

    /// A pack may add predicates or retune the shipped ones. MERGED rather than
    /// replaced, so adding "stole_from" does not silently delete the two the
    /// demo and the tests rely on.
    StandingEngine(const Json& conduct, bool enabled) : enabled_(enabled) {
        conduct_ = default_conduct();
        if (conduct.kind() != Json::Kind::Object) return;
        for (const auto& entry : conduct.fields()) {
            const ConductSpec* existing = conduct_.find(entry.first);
            ConductSpec merged = existing ? *existing : ConductSpec{};
            if (entry.second.kind() == Json::Kind::Object) {
                const Json* dimension = entry.second.find("dimension");
                const Json* sign = entry.second.find("sign");
                const Json* weight = entry.second.find("weight");
                if (dimension) merged.dimension = dimension->py_str();
                if (sign) merged.sign = sign->as_double();
                if (weight) merged.weight = weight->as_double();
            }
            conduct_[entry.first] = merged;
        }
    }

    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }

    bool describes_conduct(const Proposition& proposition) const {
        return conduct_.contains(proposition.predicate);
    }

    /// Who is said to have done it. `by` is the slot; no `by`, no judgement.
    std::string actor_of(const Proposition& proposition) const {
        const Json* found = proposition.slots.find("by");
        return found && !found->is_null() ? found->py_str() : "";
    }

    std::string victim_of(const Proposition& proposition) const {
        const Json* found = proposition.slots.find("who");
        return found && !found->is_null() ? found->py_str() : "";
    }

    /// Move `observer`'s view of whoever is named in `by`.
    ///
    /// `confidence` is how far the observer actually believes it -- the belief
    /// engine's number, not a fresh one invented here. Takes NO WORLD: everything
    /// it decides is in the observer and the proposition, which is what keeps it
    /// an engine in the sense the architecture map means.
    /// `observer` is mutable because a judgement is a POSITION and has to be
    /// remembered as one -- see the ledger below.
    std::pair<std::vector<ProposedDelta>, std::vector<StandingReason>> judge(
            Agent& observer, const Proposition& proposition,
            double confidence) const {
        if (!enabled_) return {};
        std::string actor_id = actor_of(proposition);
        std::string victim_id = victim_of(proposition);
        // You do not revise your opinion of yourself by hearing about yourself.
        // Every other layer leaves the actor alone too.
        if (actor_id.empty() || actor_id == observer.id) return {};
        const ConductSpec* spec = conduct_.find(proposition.predicate);
        if (!spec) return {};

        // A claim asserted negatively -- "he did NOT hit her" -- is evidence
        // AGAINST the conduct, so it must not read as evidence for it.
        double polarity = proposition.polarity == "+" ? 1.0 : -1.0;
        double care = care_about(observer, victim_id);
        double amount = BASE_STEP * spec->weight * spec->sign * polarity
                      * clamp01(confidence) * care;
        amount = std::max(-MAX_STEP, std::min(MAX_STEP, amount));

        // ONLY THE CHANGE IS APPLIED. A believed act is a STANDING position --
        // "this is what I now think of you" -- so hearing about it again is not
        // a second act, it is the same one restated. Paying out the full amount
        // on every report made repetition into a punishment the belief engine
        // had already, correctly, refused to be persuaded by: twenty reports of
        // one incident moved the belief from 0.54960677 to 0.54960683 and liking
        // from -0.198 to -0.659.
        const std::string incident = proposition.core_key();
        double already = observer.standing_applied.get(incident, 0.0);
        double step = amount - already;
        if (std::fabs(step) < 1e-4) return {};
        observer.standing_applied[incident] = amount;

        // Argument order matters and is easy to get backwards: reputation_delta
        // takes (subject, audience) -- who it is ABOUT first, whose view second
        // -- while trust_delta and liking_delta take (owner, subject).
        std::vector<ProposedDelta> deltas = {
            reputation_delta(actor_id, observer.id, spec->dimension, step,
                             "conduct_believed", MODULE_ID),
            liking_delta(observer.id, actor_id, step, "conduct_believed", MODULE_ID)};

        if (amount < 0) {
            // Cruelty costs trust as well as liking, and the two are not the
            // same: you can dislike somebody you would still believe.
            deltas.push_back(trust_delta(observer.id, actor_id, step * 0.6,
                                         "conduct_believed", MODULE_ID));
            // And it makes them wary of you, which is a third thing again. Fear
            // is not dislike, and a character can be afraid of somebody they
            // like. It decides whether your next threat lands or gets you
            // laughed at, and how carefully they speak to you.
            deltas.push_back(relationship_delta(observer.id, actor_id, "fear",
                                                -step * FEAR_SHARE,
                                                "conduct_believed", MODULE_ID));
        } else {
            // Decency earns standing, which is not being liked -- it is what
            // lets somebody be deferred to by a person who is not their friend.
            deltas.push_back(relationship_delta(observer.id, actor_id, "respect",
                                                step * RESPECT_SHARE,
                                                "conduct_believed", MODULE_ID));
        }

        Json detail = Json::object();
        detail["observer"] = observer.id;
        detail["about"] = actor_id;
        detail["victim"] = victim_id.empty() ? Json() : Json(victim_id);
        detail["predicate"] = proposition.predicate;
        detail["dimension"] = spec->dimension;
        detail["confidence"] = py_round(confidence, 3);
        detail["cared_about_victim"] = py_round(care, 3);
        detail["position"] = py_round(amount, 4);
        detail["note"] = std::string(
            "how far this moved is how far they believe it, which is why "
            "hearsay counts for less than what you watched; and only the CHANGE "
            "is applied, so being told again is not being wronged again");
        return {deltas, {{"standing.judged", py_round(step, 4), detail}}};
    }

    /// What they think of you, as a reason to answer you or turn you away.
    ///
    /// THIS IS THE HALF THAT MAKES THE OTHER HALF WORTH HAVING. Before it,
    /// relationships and reputation moved and nothing read them when deciding
    /// what to say: whether a character answered you depended on their
    /// agreeableness, their secrets and their safety, and not at all on what
    /// they thought of you. Standing nobody acts on is a number in a save file.
    double bias_for(const Agent& agent, const ActionDefinition& action,
                    const std::string& other_id) const {
        if (!enabled_ || other_id.empty()) return 0.0;
        if (action.target.is_null() || action.target.py_str() != other_id) return 0.0;
        const double* direction = warmth_pull().find(action.action_id);
        if (!direction) return 0.0;
        double warm = warmth(agent, other_id);
        if (std::fabs(warm) < 1e-3) return 0.0;
        return DECISION_PULL * (*direction) * warm;
    }

    /// How this character feels about `other_id` right now, in [-1, 1].
    ///
    /// Three sources, because they are three different things: liking is
    /// affection, trust is whether your word is worth anything, and `decent` is
    /// what they think of your conduct toward OTHER PEOPLE. The third is what
    /// this layer adds, and the one that lets somebody who has never met you
    /// dislike you on sight.
    double warmth(const Agent& agent, const std::string& other_id) const {
        const OrderedMap<double>* rel = agent.relationships.find(other_id);
        double liking = clamp_signed(rel ? rel->get("liking", 0.0) : 0.0);
        double trust = clamp01(rel ? rel->get("trust", 0.3) : 0.3);
        const OrderedMap<double>* view = agent.reputation.find(other_id);
        double decent = clamp_signed(view ? view->get("decent", 0.0) : 0.0);
        // Trust is centred on the 0.3 a stranger starts with, so a stranger is
        // neither warm nor cold and only what you do moves them.
        double centred_trust = (trust - 0.3) / 0.7;
        double attraction = clamp01(rel ? rel->get("attraction", 0.0) : 0.0);
        // `decent` carries half. It is the only one of the three about your
        // CONDUCT rather than your dealings with this particular person -- it is
        // what a bystander has, and what somebody who was told about you has,
        // and weighting it below liking made the layer quietest in exactly the
        // case it exists for. Attraction is ADDED rather than blended in: it
        // warms you toward somebody without pretending to be liking, trust or
        // approval, and it is zero in every pack that does not author it.
        return clamp_signed(0.30 * liking + 0.20 * centred_trust + 0.50 * decent
                            + 0.25 * attraction);
    }

    /// How much sway `other_id` has over `agent`, in [0, 1]. READ ONLY.
    ///
    /// Not a new number in the save file: a summary of four already there,
    /// because "how much pull does this person have over me" is a question a
    /// game asks constantly and had to assemble by hand every time.
    ///
    /// Deliberately NOT liking. Somebody you are fond of and neither respect nor
    /// need has no particular sway over you, and a summary that said otherwise
    /// would flatter every friendship in the world.
    double influence(const Agent& agent, const std::string& other_id,
                     double bridge_score = 0.0) const {
        const OrderedMap<double>* rel = agent.relationships.find(other_id);
        double respect = clamp01(rel ? rel->get("respect", 0.0) : 0.0);
        double dependence = clamp01(rel ? rel->get("dependence", 0.0) : 0.0);
        double fear = clamp01(rel ? rel->get("fear", 0.0) : 0.0);
        double reach = clamp01(bridge_score);
        return clamp01(0.35 * respect + 0.30 * dependence + 0.25 * fear + 0.10 * reach);
    }

private:
    /// Between STRANGER_FLOOR and 1: whose treatment you take personally.
    double care_about(const Agent& observer, const std::string& victim_id) const {
        if (victim_id.empty()) return STRANGER_FLOOR;
        const OrderedMap<double>* rel = observer.relationships.find(victim_id);
        double warm = std::max(0.0, rel ? rel->get("liking", 0.0) : 0.0);
        double known = std::max(0.0, rel ? rel->get("familiarity", 0.0) : 0.0);
        double closeness = std::min(1.0, 0.5 * warm + 0.5 * known);
        return STRANGER_FLOOR + (1.0 - STRANGER_FLOOR) * closeness;
    }

    bool enabled_ = false;
    OrderedMap<ConductSpec> conduct_ = default_conduct();
};

}  // namespace usc
