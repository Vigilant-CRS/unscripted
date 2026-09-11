// `usc/agent.py`. One character: what a pack authored about them, and what play
// has done to them since.
//
// This replaces the `AgentState` subset the relationship engines were written
// against. Keeping a subset was right while four modules existed and wrong the
// moment topology needed `networks`, `roles` and `identities` from the same
// object -- two structs describing the same character is how they come to
// disagree about one.
//
// `identities` and `roles` stay as raw JSON rather than becoming structs,
// because they are authored content with open shapes: `topology.circles()`
// reads `role["role"]`, `role["context"]` and `identity["group"]`, while
// `IdentityEngine` reads `id` and `accessibility`, and a pack may carry keys
// neither of them knows about. A struct here would quietly drop them.
#pragma once

#include <optional>
#include <string>
#include <vector>

#include "usc/affect.hpp"
#include "usc/belief.hpp"
#include "usc/json.hpp"
#include "usc/memory.hpp"
#include "usc/ordered_map.hpp"
#include "usc/types.hpp"

namespace usc {

/// Bumped by every write to any agent's `location`. A world's occupancy index
/// is cached against this, so it cannot go stale no matter who moves somebody
/// -- routines, the player, a snapshot restore, or a test.
///
/// A counter rather than invalidation at each of the half-dozen places that
/// move somebody, because that bookkeeping works until the seventh one is added.
inline long long& location_epoch() {
    static long long epoch = 0;
    return epoch;
}

struct Agent {
    std::string id;
    OrderedMap<double> big_five;
    OrderedMap<double> schwartz;
    OrderedMap<double> needs;
    std::vector<Json> identities;
    std::vector<Json> roles;
    Json appearance;
    OrderedMap<double> education;                     // domain -> competence
    OrderedMap<OrderedMap<double>> relationships;     // other -> field -> value
    std::vector<Json> secrets;
    std::vector<Json> goals;
    Json public_name;
    Json objective_name;
    std::vector<std::string> aliases;
    Json routine;
    double social_status = 0.4;                       // prestige baseline [0,1]
    double resources = 0.4;                           // liquid wealth [0,1]
    Json dialect;
    OrderedMap<OrderedMap<double>> reputation;        // subject -> dimension -> degree
    OrderedMap<double> identity_salience;
    /// How threatened each belonging currently feels, [0,1]. Alarm, not a fact
    /// about the world: raised when somebody who shares it is attacked, decayed
    /// with mood. It feeds `IdentityEngine`'s `w_threat`, which was multiplied
    /// by zero for a long time because nothing ever produced one.
    OrderedMap<double> identity_threat;
    /// What this character will not trade away. `truthfulness` decides whether
    /// a cornered character lies or refuses. Authored, because "would this
    /// person lie to you" is a characterisation and not an engine's guess.
    OrderedMap<double> values;
    /// How they handle evidence, as opposed to what they value.
    Json epistemic;
    /// Groups beyond their role: family, shift, union, congregation.
    std::vector<std::string> networks;
    Json voice;
    std::vector<std::string> contacts;
    /// Bounded intake, reset each world day. Nobody takes in everything.
    long long attention_day = -1;
    long long attention_spent = 0;
    /// incident (proposition core key) -> how far this character's standing
    /// towards whoever did it has already been moved by it. A believed act is a
    /// position, not a running total, so hearing about it again applies only the
    /// difference.
    OrderedMap<double> standing_applied;
    /// Depth-1 models of what somebody else believes about one claim.
    ///
    /// Python keys this with a `(other, proposition_key)` TUPLE, which JSON
    /// cannot express as an object key -- so it is carried as an explicit list
    /// of triples, which is also exactly how the snapshot stores it. Nothing in
    /// the runtime reads it yet; it is here so a save round-trips whole rather
    /// than losing a field nobody happened to be using.
    struct TheoryOfMind {
        std::string other;
        std::string proposition;
        OrderedMap<double> model;
    };
    std::vector<TheoryOfMind> tom_models;

    // Owned runtime state.
    OrderedMap<Belief> beliefs;                       // core_key -> Belief
    MemoryList memory;
    AffectState affect;

    /// Every write to `location` goes through here, so the epoch cannot be
    /// missed. Python does it in `__setattr__`; C++ has no such hook, so the
    /// field is private and this is the only door.
    const Json& location() const { return location_; }
    void set_location(const Json& where) {
        ++location_epoch();
        location_ = where;
    }

    /// Mirrors `__post_init__`: an affect state derived from personality unless
    /// one was restored. Called after the authored fields are filled in.
    void initialise_affect() {
        Vec3 base = big_five.empty() ? Vec3{} : pad_baseline_from_big_five(big_five);
        affect.mood = base;
        affect.baseline = base;
    }

    double trust_in(const std::string& other) const {
        const OrderedMap<double>* row = relationships.find(other);
        return row ? row->get("trust", 0.3) : 0.3;
    }

    double competence_in(const std::string& domain) const {
        return education.get(domain, 0.3);
    }

    /// An authored epistemic trait, or a neutral default. Python swallows
    /// KeyError, TypeError and ValueError alike, so a trait authored as a
    /// string that is not a number falls back rather than raising.
    double trait(const std::string& name, double fallback = 0.5) const {
        const Json* found = epistemic.find(name);
        if (!found) return fallback;
        if (found->is_number()) return found->as_double();
        if (found->kind() == Json::Kind::String) {
            try {
                return std::stod(found->as_string());
            } catch (const std::exception&) {
                return fallback;
            }
        }
        return fallback;
    }

    /// An authored value, falling back to a Schwartz proxy and then a default.
    double value(const std::string& name, double fallback = 0.5) const {
        const double* authored = values.find(name);
        if (authored) return *authored;
        std::string proxy;
        if (name == "truthfulness")           proxy = "benevolence";
        else if (name == "loyalty")           proxy = "tradition";
        else if (name == "self_preservation") proxy = "security";
        if (!proxy.empty()) {
            const double* found = schwartz.find(proxy);
            if (found) return *found;
        }
        return fallback;
    }

    /// Lie, or refuse? A character lies when the stake outweighs their honesty.
    ///
    /// No cover story means no lie. Deliberate: the engine will not invent what
    /// somebody claims instead, any more than it invents a fact -- so a world
    /// that has not authored the lie gets a refusal, which is honest in its own
    /// way, because silence is itself information.
    /// Would this character say something else rather than fall silent?
    ///
    /// Takes the two things it needs rather than a secret, because `Secret`
    /// lives a layer above this one and the alternative was two copies of the
    /// rule -- one for a parsed secret and one for the raw JSON, drifting apart
    /// the first time the stake changed. `content.hpp` has the wrapper that
    /// reads them off a `Secret`.
    bool will_lie_about(bool has_cover_story, double stake) const {
        if (!has_cover_story) return false;
        return value("truthfulness") < stake;
    }

    bool will_lie_about(const Json& secret) const {
        const Json* cover = secret.find("cover_story");
        bool has_cover = cover && !cover->is_null()
                      && !(cover->kind() == Json::Kind::String && cover->as_string().empty());
        const Json* stake = secret.find("min_trust");
        return will_lie_about(has_cover,
                              (stake && stake->is_number()) ? stake->as_double() : 0.45);
    }

    /// Low agreeableness and low stability read as more skeptical. A derived
    /// proxy, not an authored trait.
    double skepticism() const {
        double agreeable = big_five.get("agreeableness", 0.5);
        double stable = big_five.get("emotional_stability", 0.5);
        return clamp01(0.6 - 0.3 * agreeable - 0.2 * (stable - 0.5));
    }

private:
    Json location_;
};

}  // namespace usc
