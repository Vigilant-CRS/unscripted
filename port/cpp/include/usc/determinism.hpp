// The seeding primitives, ported. Thirty-two lines of Python, and the first
// thing worth porting because everything stochastic in the runtime derives from
// them: get one bit wrong and the two implementations agree until the first coin
// flip, then diverge in a way that looks like a modelling difference.
#pragma once

#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

#include "usc/blake2b.hpp"
#include "usc/pysum.hpp"

namespace usc {

/// blake2b(global_seed|agent|event|world_time|module|salt), 16 bytes.
///
/// The joined string has to match Python's f-string byte for byte, which means
/// the integers are formatted the way Python formats them. That is why the
/// signature takes them as integers and does the formatting here, rather than
/// letting each caller build a string its own way.
/// The general form: every part as the string Python's f-string would produce.
///
/// NOT a convenience. Callers pass whatever they have -- `diffusion` puts an
/// agent id where the signature says `event_id`, and `distortion` puts a hex
/// digest where it says `global_seed` -- because in Python an f-string does not
/// care. A port with a narrow signature does not merely fail to compile those
/// call sites; it invites somebody to convert the value, and a converted value
/// hashes differently.
inline std::vector<std::uint8_t> derive_seed_parts(const std::string& global_seed,
                                                   const std::string& agent_id,
                                                   const std::string& event_id,
                                                   const std::string& world_time,
                                                   const std::string& module_id,
                                                   const std::string& salt = "") {
    std::string key = global_seed + "|" + agent_id + "|" + event_id
                    + "|" + world_time + "|" + module_id + "|" + salt;
    Blake2b hash(16);
    hash.update(key);
    return hash.digest();
}

inline std::vector<std::uint8_t> derive_seed(const std::string& global_seed,
                                             const std::string& agent_id,
                                             long long event_id,
                                             long long world_time,
                                             const std::string& module_id,
                                             const std::string& salt = "") {
    return derive_seed_parts(global_seed, agent_id, std::to_string(event_id),
                             std::to_string(world_time), module_id, salt);
}

/// The overload `pursuit` needs: an id where the WORLD TIME would go.
///
/// Python interpolates whatever it is handed, and `pursuit` passes the place id
/// there. Adding an overload rather than converting at the call site, for the
/// reason above: a converted value hashes differently.
inline std::vector<std::uint8_t> derive_seed(const std::string& global_seed,
                                             const std::string& agent_id,
                                             long long event_id,
                                             const std::string& world_time,
                                             const std::string& module_id,
                                             const std::string& salt = "") {
    return derive_seed_parts(global_seed, agent_id, std::to_string(event_id),
                             world_time, module_id, salt);
}

/// The overload `diffusion` needs: an id where an event number would go.
inline std::vector<std::uint8_t> derive_seed(const std::string& global_seed,
                                             const std::string& agent_id,
                                             const std::string& event_id,
                                             long long world_time,
                                             const std::string& module_id,
                                             const std::string& salt = "") {
    return derive_seed_parts(global_seed, agent_id, event_id,
                             std::to_string(world_time), module_id, salt);
}

/// A uniform double in [0, 1).
///
/// `int.from_bytes(seed[:8], "big") / 2**64` in Python. The division is by an
/// exact power of two, so it is one rounding of an integer that fits in 64
/// bits -- the same on any IEEE-754 machine, with no libm involved. That is
/// deliberate and worth keeping: the moment this needs `pow` it stops being
/// portable for free.
inline double seeded_uniform(const std::vector<std::uint8_t>& seed) {
    std::uint64_t value = 0;
    for (int i = 0; i < 8; ++i)
        value = (value << 8) | static_cast<std::uint64_t>(seed[i]);
    return static_cast<double>(value) / 18446744073709551616.0;   // 2^64
}

/// Weighted choice over indices. Ported exactly, including `r <= acc`: the
/// boundary condition decides which index a seed lands on, and swapping it for
/// `<` moves outcomes in a way no test would obviously attribute to this line.
inline std::size_t seeded_choice(const std::vector<std::uint8_t>& seed,
                                 const std::vector<double>& weights) {
    // `float(sum(weights))`, and `sum` compensates -- see `pysum.hpp`. A naive
    // loop here shifts the threshold a seeded draw is compared against, which
    // is not a rounding difference but a different choice.
    double total = py_sum(weights);
    if (total <= 0.0) return 0;
    double r = seeded_uniform(seed) * total;
    double acc = 0.0;
    for (std::size_t i = 0; i < weights.size(); ++i) {
        acc += weights[i];
        if (r <= acc) return i;
    }
    return weights.empty() ? 0 : weights.size() - 1;
}

/// The belief engine's evidence term: `eta * log(kappa / (1 - kappa))`.
///
/// THE ONE THAT USES libm, and therefore the one that decides whether a port
/// can be bit-identical at all. `std::log` and Python's `math.log` are the same
/// call on the same machine; across platforms they need not be. The probe
/// measures it rather than assuming either way.
inline double evidence(double kappa, double eta) {
    return eta * std::log(kappa / (1.0 - kappa));
}

}  // namespace usc
