// `usc/types.py`. Clamps, the sigmoid, the logit, and the PAD vector.
//
// Small enough to look like it needs no care, which is why the sigmoid is
// written the way it is below rather than as `1 / (1 + exp(-x))`.
#pragma once

#include <cmath>

#include "usc/json.hpp"

namespace usc {

inline double clamp(double x, double lo, double hi) {
    return x < lo ? lo : (x > hi ? hi : x);
}

inline double clamp01(double x) { return clamp(x, 0.0, 1.0); }

inline double clamp_signed(double x) { return clamp(x, -1.0, 1.0); }

/// The two-branch sigmoid, ported branch for branch.
///
/// Not a micro-optimisation and not optional. `1/(1+exp(-x))` overflows `exp`
/// for x around -710 and returns inf, and a belief with enough evidence against
/// it gets there. The branches keep the argument to `exp` negative on both
/// sides. Writing the shorter version here would be a port that agrees with
/// Python everywhere except at the extremes, which is the worst place to
/// disagree because it is where a character has finally made up their mind.
inline double sigmoid(double x) {
    if (x >= 0.0) {
        double z = std::exp(-x);
        return 1.0 / (1.0 + z);
    }
    double z = std::exp(x);
    return z / (1.0 + z);
}

inline double logit(double p, double eps = 1e-6) {
    p = clamp(p, eps, 1.0 - eps);
    return std::log(p / (1.0 - p));
}

/// Pleasure / Arousal / Dominance, each in [-1, 1].
struct Vec3 {
    double p = 0.0;
    double a = 0.0;
    double d = 0.0;

    Vec3 add(const Vec3& other) const { return {p + other.p, a + other.a, d + other.d}; }
    Vec3 scale(double k) const { return {p * k, a * k, d * k}; }
    Vec3 clamped() const {
        return {clamp_signed(p), clamp_signed(a), clamp_signed(d)};
    }

    /// Full precision. This is the persistence shape, and rounding it makes a
    /// save/load round-trip lossy; display code rounds separately.
    Json as_json() const {
        Json out = Json::object();
        out["valence"] = p;
        out["arousal"] = a;
        out["dominance"] = d;
        return out;
    }

    static Vec3 from_json(const Json& doc) {
        return {doc.get("valence").as_double(0.0),
                doc.get("arousal").as_double(0.0),
                doc.get("dominance").as_double(0.0)};
    }
};

}  // namespace usc
