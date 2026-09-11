// `usc/medium.py`. How something was said, and what that costs it.
//
// A person-to-person claim used to be one undifferentiated act: A told B. But
// the same two people telling each other the same thing face to face, over a
// phone and in a note are three different events.
//
//   face to face   everything survives, and the room hears it
//   a phone call   detail goes, nobody overhears, and it is harder to weigh
//   a note         the words survive, the tone does not, and it can be shown to
//                  somebody else later
//
// Daft & Lengel (1986) is the usual framing: media differ in how much they carry
// per exchange, and leaner media lose more of what was meant. This is that idea
// reduced to three numbers, landed on machinery that already exists rather than
// a parallel one -- fidelity scales the LEVELLING probability the distortion
// layer already implements, audience decides whether there are bystanders at
// all, and trust_factor scales the assertion strength the listener weighs.
#pragma once

#include <algorithm>
#include <cstdio>
#include <set>
#include <string>

#include "usc/agent.hpp"
#include "usc/pyround.hpp"

namespace usc {

/// How well two people must know each other before a pack that has not said
/// otherwise assumes they can call one another.
inline constexpr double CONTACT_FAMILIARITY = 0.45;

/// One way of saying something, and what it costs.
struct Medium {
    std::string name;
    /// 1.0 loses nothing beyond what any retelling loses; lower levels more.
    double fidelity = 1.0;
    /// Whether anybody else in the room takes it in.
    bool audience = true;
    /// Whether the two have to be in the same place.
    bool needs_colocation = true;
    /// What the listener's weighing of the claim is multiplied by.
    double trust_factor = 1.0;

    /// How much likelier a retelling is to lose a detail on this medium.
    double distortion_scale() const {
        return 2.0 - std::max(0.0, std::min(1.0, fidelity));
    }
};

inline const Medium& in_person() {
    static const Medium one{"in_person", 1.0, true, true, 1.0};
    return one;
}
inline const Medium& phone() {
    static const Medium one{"phone", 0.72, false, false, 0.88};
    return one;
}
inline const Medium& note() {
    static const Medium one{"note", 0.88, false, false, 0.78};
    return one;
}

inline const Medium* medium_by_name(const std::string& name) {
    if (name == "in_person") return &in_person();
    if (name == "phone") return &phone();
    if (name == "note") return &note();
    return nullptr;
}

/// Whose number this character has.
///
/// Authored with `"contacts": [...]`, or inferred from how well they know
/// somebody. The inference is A DEFAULT, NOT A CLAIM: a pack that cares about
/// who can reach whom should say so, and a pack that does not still gets a
/// plausible small-world graph rather than a fully connected one.
inline std::set<std::string> contacts_of(const Agent& agent) {
    // `if authored:` -- an empty list falls through to the inference, which is
    // what lets a pack declare the field without committing to it.
    if (!agent.contacts.empty())
        return std::set<std::string>(agent.contacts.begin(), agent.contacts.end());
    std::set<std::string> known;
    for (const auto& entry : agent.relationships)
        if (entry.second.get("familiarity", 0.0) >= CONTACT_FAMILIARITY)
            known.insert(entry.first);
    return known;
}

/// The medium these two would use, or nothing if they cannot reach each other.
///
/// Same room: they speak. Different rooms and each other's number: they call.
/// Otherwise the exchange does not happen, which is the point -- a world where
/// everybody can always reach everybody has no geography left.
inline const Medium* for_exchange(const Agent& speaker, const Agent& listener,
                                  bool enabled = true) {
    bool together = speaker.location().py_str() == listener.location().py_str();
    if (!enabled) return together ? &in_person() : nullptr;
    if (together) return &in_person();
    if (contacts_of(speaker).count(listener.id)) return &phone();
    return nullptr;
}

/// Python's `f"{x:.0%}"`: multiply by 100, round HALF TO EVEN, append `%`.
///
/// `printf("%.0f")` rounds half away from zero, so 0.725 would print 73 where
/// Python prints 72. Going through the same fixed-point conversion the rounding
/// helper uses keeps the two in step.
inline std::string percent(double value) {
    return std::to_string(static_cast<long long>(py_round(value * 100.0, 0))) + "%";
}

/// One line for a trace or a debug HUD.
inline std::string describe(const Medium& medium) {
    std::string label = medium.name;
    std::replace(label.begin(), label.end(), '_', ' ');
    char buffer[256];
    // `:.0%` -- a percentage with no decimals, which rounds half to EVEN in
    // Python's format spec and half away from zero in printf. `%.0f` on the
    // scaled value would disagree at exactly .5; this rounds the same way
    // Python does by going through the same decimal path.
    std::snprintf(buffer, sizeof buffer,
                  "%s: %s, detail survives %s as well, weighed at %s",
                  label.c_str(),
                  medium.audience ? "the room hears it" : "nobody else hears it",
                  percent(medium.fidelity).c_str(),
                  percent(medium.trust_factor).c_str());
    return buffer;
}

}  // namespace usc
