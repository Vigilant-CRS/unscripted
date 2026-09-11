// `usc/inspect.py`. Human-readable dumps of otherwise-opaque internal state.
//
// This is the explainability the runtime is sold on, in the form a person reads:
// what a character believes and on whose word, what they remember and how faded
// it is, what they feel, and why the last turn went the way it did. The terminal
// client's `inspect` commands are these five functions and nothing else.
//
// Every line is compared character for character against the Python, which is
// stricter than it sounds: a reason detail is printed as a Python DICT, so the
// two implementations have to agree on how a float, a string and None look
// inside one. That is what `pyrepr.hpp` is for.
#pragma once

#include <algorithm>
#include <string>
#include <vector>

#include "usc/affect.hpp"
#include "usc/agent.hpp"
#include "usc/memory.hpp"
#include "usc/pyrepr.hpp"
#include "usc/pyround.hpp"
#include "usc/reason.hpp"
#include "usc/runtime.hpp"

namespace usc {

namespace detail_ {

/// `f"{value:+.Nf}"` -- fixed notation with the sign always written.
inline std::string format_signed(double value, int digits) {
    std::string out = format_fixed(value, digits);
    // `-0.00` keeps its minus in Python too: the sign comes from the VALUE, not
    // from whether the rounded digits are zero.
    if (!out.empty() && out[0] != '-') out = "+" + out;
    return out;
}

/// `f"{text:Ns}"` -- left-aligned, padded to at least N, never truncated.
inline std::string ljust(const std::string& text, std::size_t width) {
    if (text.size() >= width) return text;
    return text + std::string(width - text.size(), ' ');
}

inline std::string joined(const std::vector<std::string>& parts,
                          const std::string& separator) {
    std::string out;
    for (std::size_t i = 0; i < parts.size(); ++i) {
        if (i) out += separator;
        out += parts[i];
    }
    return out;
}

}  // namespace detail_

inline std::string format_beliefs(const Agent& agent) {
    std::vector<std::string> lines = {"  beliefs of " + agent.id + ":"};
    if (agent.beliefs.empty()) lines.push_back("    (none)");
    for (const auto& entry : agent.beliefs) {
        const Belief& b = entry.second;
        lines.push_back("    " + b.proposition.str());
        lines.push_back("        p=" + format_fixed(b.expected_prob(), 2)
                        + "  for=" + format_fixed(b.support_for, 2)
                        + " against=" + format_fixed(b.support_against, 2)
                        + "  ignorance=" + format_fixed(b.ignorance(), 2)
                        + " conflict=" + format_fixed(b.conflict(), 2));
        std::vector<std::string> sources;
        // `f"{p['kappa']}"` is `str(float)`, which in Python 3 is `repr(float)`
        // -- the shortest round-tripping decimal, not a rounded display value.
        for (const ProvenanceEntry& p : b.provenance)
            sources.push_back(p.claim_id.py_str() + "(k=" + py_repr(p.kappa)
                              + ",eta=" + py_repr(p.eta) + ")");
        lines.push_back("        provenance: " + detail_::joined(sources, ", "));
    }
    return detail_::joined(lines, "\n");
}

inline std::string format_memory(const Agent& agent, long long now) {
    std::vector<std::string> lines =
        {"  memory of " + agent.id + " @ t=" + std::to_string(now) + ":"};
    if (agent.memory.empty()) lines.push_back("    (none)");

    // `sorted(..., reverse=True)` -- STABLE, so two memories of equal activation
    // stay in the order they were laid down. `std::sort` is not, and the order of
    // a character's memories is what an inspector is being read for.
    std::vector<const MemoryItem*> rows;
    for (const auto& item : agent.memory) rows.push_back(item.get());
    std::stable_sort(rows.begin(), rows.end(),
                     [now](const MemoryItem* a, const MemoryItem* b) {
                         return a->base_activation(now) > b->base_activation(now);
                     });

    for (const MemoryItem* m : rows) {
        double activation = m->base_activation(now);
        std::string status = activation > 0 ? "vivid"
                           : (activation > -1.5 ? "faint" : "lost");
        lines.push_back("    [" + detail_::ljust(m->type, 10) + "] " + m->content);
        lines.push_back("        activation=" + format_fixed(activation, 2)
                        + " (" + status + ")  importance="
                        + format_fixed(m->importance, 2)
                        + "  valence=" + detail_::format_signed(m->emotional_valence, 2)
                        + "  source_conf=" + format_fixed(m->source_conf, 2));
    }
    return detail_::joined(lines, "\n");
}

inline std::string format_affect(const Agent& agent) {
    const AffectState& a = agent.affect;
    std::vector<std::string> emotions;
    for (const auto& entry : a.active_emotions)
        emotions.push_back(entry.first + "=" + format_fixed(entry.second, 2));
    std::string active = emotions.empty() ? "(calm)" : detail_::joined(emotions, ", ");

    std::vector<std::string> lines = {
        "  affect of " + agent.id + ":",
        "    mood PAD: valence=" + detail_::format_signed(a.mood.p, 2)
            + " arousal=" + detail_::format_signed(a.mood.a, 2)
            + " dominance=" + detail_::format_signed(a.mood.d, 2)
            + "   (baseline " + detail_::format_signed(a.baseline.p, 2) + "/"
            + detail_::format_signed(a.baseline.a, 2) + "/"
            + detail_::format_signed(a.baseline.d, 2) + ")",
        "    active emotions: " + active};

    AffectEngine engine;
    OrderedMap<double> tendencies = engine.action_tendencies(a);
    if (!tendencies.empty()) {
        // `sorted(key=lambda kv: -abs(kv[1]))[:5]` -- strongest pull first,
        // whichever way it pulls, and STABLE so ties keep their order.
        std::vector<std::pair<std::string, double>> ranked(tendencies.begin(),
                                                           tendencies.end());
        std::stable_sort(ranked.begin(), ranked.end(),
                         [](const auto& a, const auto& b) {
                             return std::fabs(a.second) > std::fabs(b.second);
                         });
        if (ranked.size() > 5) ranked.resize(5);
        std::vector<std::string> top;
        for (const auto& entry : ranked)
            top.push_back(entry.first + detail_::format_signed(entry.second, 2));
        lines.push_back("    action tendencies: " + detail_::joined(top, ", "));
    }
    lines.push_back("    stress: " + format_fixed(engine.stress(a), 2));
    return detail_::joined(lines, "\n");
}

inline std::string format_last_trace(const Runtime& runtime,
                                     const std::string& agent_id) {
    const std::vector<Reason>* rows = runtime.last_traces.find(agent_id);
    std::vector<std::string> lines =
        {"  last reason trace for " + agent_id + ":"};
    if (!rows || rows->empty()) lines.push_back("    (no trace this turn)");
    if (rows) for (const Reason& reason : *rows)
        lines.push_back("    " + detail_::ljust(reason.code, 28) + " "
                        + detail_::format_signed(reason.amount, 3) + "  "
                        + py_repr(reason.detail));
    return detail_::joined(lines, "\n");
}

}  // namespace usc
