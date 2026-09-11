// Prints, as exact bit patterns, everything the Python side must agree with.
//
// Not a test: a measurement. `port_probe.py` runs this, computes the same
// values in Python and compares. Doubles are printed as their raw 64 bits
// because "0.35" printed to fifteen places can hide a difference in the last
// one, and the last one is what diverges a simulation after a thousand ticks.
#include <cstdio>
#include <cstring>
#include <string>

#include "usc/determinism.hpp"
#include "usc/pyround.hpp"

static void print_bits(const char* label, double value) {
    std::uint64_t bits;
    std::memcpy(&bits, &value, sizeof bits);
    std::printf("%s\t%016llx\t%.17g\n", label,
                static_cast<unsigned long long>(bits), value);
}

int main() {
    // 1. The seed itself.
    struct Case { const char* seed; const char* agent; long long event;
                  long long time; const char* module_; const char* salt; };
    const Case cases[] = {
        {"lamb-street-2107", "agent:halloran", 17, 1267, "diffusion", ""},
        {"seedA", "npc", 0, 0, "belief", "topic"},
        {"", "", 0, 0, "", ""},
        {"unicode-\xc3\xa4\xc3\xb6", "agent:\xc3\xbc", 9, 4242, "climate", "x|y"},
    };
    for (const Case& c : cases) {
        auto seed = usc::derive_seed(c.seed, c.agent, c.event, c.time,
                                     c.module_, c.salt);
        std::printf("seed\t");
        for (unsigned char byte : seed) std::printf("%02x", byte);
        std::printf("\n");
        print_bits("uniform", usc::seeded_uniform(seed));
    }

    // 2. The arithmetic that decides a belief.
    const double kappas[] = {0.2, 0.35, 0.5, 0.571, 0.698, 0.803, 0.95};
    const double etas[] = {1.0, 0.85, 0.4225};
    for (double kappa : kappas)
        for (double eta : etas)
            print_bits("evidence", usc::evidence(kappa, eta));

    // 3. Python's round(), on the values where the obvious implementation is
    //    wrong. Every one of these is a tie: the double sits a hair above or
    //    below the halfway point, and `nearbyint(x * 1000) / 1000` throws away
    //    the information that decides it. The runtime rounds kappa, eta and
    //    delta before storing them, so these land in the exported state.
    const double ties[] = {0.0005, 0.0015, 0.1235, 0.1245, 0.5555, 0.8885,
                           -0.1235, -0.5555, 0.9995, 0.0000005, 2.675, 1.005};
    for (double value : ties) print_bits("round3", usc::py_round(value, 3));
    for (double value : ties) print_bits("round6", usc::py_round(value, 6));

    // 4. And an accumulation, because rounding compounds.
    double logit = 0.0;
    for (int i = 0; i < 200; ++i)
        logit += usc::evidence(0.698, std::pow(0.85, i % 12));
    print_bits("accumulated", logit);
    print_bits("sigmoid", 1.0 / (1.0 + std::exp(-logit)));
    return 0;
}
