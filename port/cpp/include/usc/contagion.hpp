// `usc/contagion.py`. A mood is catching, and that is why one rude customer
// ruins an afternoon.
//
// The runtime has modelled affect per character since the beginning: a
// threatened trader's valence drops to -0.95 and she speaks faster to EVERYBODY
// afterwards, not only to the person who threatened her. What it never modelled
// is the next step, which is the one people actually notice: the person she
// serves next is worse off for it, and the one after that a little worse still.
//
// Hatfield, Cacioppo & Rapson (1994) call it primitive emotional contagion --
// automatic mimicry of expression and posture, then convergence of feeling,
// below the level of anybody deciding anything. Fast, small per exchange, and
// cumulative.
//
// Three properties keep it from becoming a mood engine that eats the world: it
// is damped by the listener's emotional stability, weighted by how much they
// care about the speaker, and capped per exchange. It moves MOOD, never
// personality -- this is weather, and who somebody is does not change.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/pyround.hpp"
#include "usc/knob.hpp"

namespace usc {

/// Most of a mood does not transfer. This is one exchange, not an hour together.
inline constexpr double CONTAGION_TRANSFER = 0.14;

/// Below this the two barely know each other, and a stranger's mood is not
/// catching.
inline constexpr double CONTAGION_MIN_TIE = 0.08;

/// Hard ceiling per exchange on each axis, so no single conversation moves
/// somebody more than this however extreme the speaker is.
inline constexpr double CONTAGION_MAX_STEP = 0.22;

using ContagionReason = Reason;

class ContagionEngine {
public:
    struct Params {
        double transfer = CONTAGION_TRANSFER;
        double min_tie = CONTAGION_MIN_TIE;
        double max_step = CONTAGION_MAX_STEP;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("transfer", &Params::transfer),
            knob("min_tie", &Params::min_tie),
            knob("max_step", &Params::max_step),
        };
        return table;
    }

    static constexpr const char* MODULE_ID = "contagion";

    ContagionEngine() = default;
    explicit ContagionEngine(bool enabled) : enabled_(enabled) {}
    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    /// Move a little of the speaker's mood onto the listener.
    ///
    /// Nothing at all when the layer is off, when the two are barely
    /// acquainted, or when there is no difference to transfer -- which is most
    /// exchanges, and should be.
    std::vector<ContagionReason> between(const Agent& speaker, Agent& listener) const {
        if (!enabled_) return {};
        // PROVABLY REDUNDANT and kept anyway: a character's mood differs from
        // their own by zero on every axis, so the transfer below would move
        // nothing regardless. No mutation can distinguish the two. It stays
        // because it says what the module means -- you do not catch a mood from
        // yourself -- and because the reason trace would otherwise be one line
        // longer for a self-exchange that did nothing.
        if (speaker.id == listener.id) return {};

        // How much this person's mood is worth to me: familiarity carries most
        // of it, and liking decides whether their bad afternoon lands as
        // sympathy or slides off. Trust is deliberately not in it -- you can
        // catch a mood from somebody you do not believe.
        const OrderedMap<double>* rel = listener.relationships.find(speaker.id);
        double familiarity = rel ? rel->get("familiarity", 0.0) : 0.0;
        double liking = rel ? rel->get("liking", 0.0) : 0.0;
        double tie = std::max(0.0, familiarity + 0.35 * std::max(0.0, liking));
        if (tie < params_.min_tie) return {};

        // A steady person catches less. This is what emotional stability is
        // for, and using it here means the trait does work rather than sitting
        // in a character sheet.
        double stability = listener.big_five.get("emotional_stability", 0.5);
        double weight = params_.transfer * std::min(1.0, tie) * (1.0 - 0.6 * stability);
        if (weight <= 0.0) return {};

        Json moved = Json::object();
        bool any = false;
        double* mine[3] = {&listener.affect.mood.p, &listener.affect.mood.a,
                           &listener.affect.mood.d};
        const double theirs[3] = {speaker.affect.mood.p, speaker.affect.mood.a,
                                  speaker.affect.mood.d};
        const char* axes[3] = {"p", "a", "d"};
        for (int i = 0; i < 3; ++i) {
            double step = clamp(( theirs[i] - *mine[i]) * weight,
                                -params_.max_step, params_.max_step);
            if (std::fabs(step) < 1e-4) continue;
            *mine[i] = clamp_signed(*mine[i] + step);
            moved.fields()[axes[i]] = Json(py_round(step, 4));
            any = true;
        }
        if (!any) return {};

        Json detail = Json::object();
        detail["from"] = speaker.id;
        detail["to"] = listener.id;
        detail["tie"] = py_round(tie, 3);
        detail["moved"] = moved;
        return {{"contagion.caught", py_round(weight, 4), detail}};
    }

private:
    bool enabled_ = false;
    Params params_;
};

}  // namespace usc
