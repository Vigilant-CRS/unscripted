"""Inspector views (Ontology v0.1 §19; spec v0.5 §9.6).

Human-readable dumps of the otherwise-opaque NPC internal state -- the
explainability USP. Used by the terminal demo's `inspect` commands.
"""
from __future__ import annotations


def fmt_beliefs(agent):
    lines = [f"  beliefs of {agent.id}:"]
    if not agent.beliefs:
        lines.append("    (none)")
    for b in agent.beliefs.values():
        lines.append(f"    {b.proposition}")
        lines.append(f"        p={b.expected_prob:.2f}  for={b.support_for:.2f} against={b.support_against:.2f}"
                     f"  ignorance={b.ignorance:.2f} conflict={b.conflict:.2f}")
        srcs = ", ".join(f"{p['claim_id']}(k={p['kappa']},eta={p['eta']})" for p in b.provenance)
        lines.append(f"        provenance: {srcs}")
    return "\n".join(lines)


def fmt_memory(agent, t):
    lines = [f"  memory of {agent.id} @ t={t}:"]
    if not agent.memory:
        lines.append("    (none)")
    rows = sorted(agent.memory, key=lambda m: m.base_activation(t), reverse=True)
    for m in rows:
        act = m.base_activation(t)
        status = "vivid" if act > 0 else ("faint" if act > -1.5 else "lost")
        lines.append(f"    [{m.type:10s}] {m.content}")
        lines.append(f"        activation={act:.2f} ({status})  importance={m.importance:.2f}"
                     f"  valence={m.emotional_valence:+.2f}  source_conf={m.source_conf:.2f}")
    return "\n".join(lines)


def fmt_affect(agent):
    a = agent.affect
    m = a.mood
    emos = ", ".join(f"{k}={v:.2f}" for k, v in a.active_emotions.items()) or "(calm)"
    lines = [f"  affect of {agent.id}:",
             f"    mood PAD: valence={m.p:+.2f} arousal={m.a:+.2f} dominance={m.d:+.2f}"
             f"   (baseline {a.baseline.p:+.2f}/{a.baseline.a:+.2f}/{a.baseline.d:+.2f})",
             f"    active emotions: {emos}"]
    from .affect import AffectEngine
    eng = AffectEngine()
    tend = eng.action_tendencies(a)
    if tend:
        top = sorted(tend.items(), key=lambda kv: -abs(kv[1]))[:5]
        lines.append("    action tendencies: " + ", ".join(f"{k}{v:+.2f}" for k, v in top))
    lines.append(f"    stress: {eng.stress(a):.2f}")
    return "\n".join(lines)


def fmt_last_trace(runtime, agent_id):
    rt = runtime.last_traces.get(agent_id, [])
    lines = [f"  last reason trace for {agent_id}:"]
    if not rt:
        lines.append("    (no trace this turn)")
    for code, mag, detail in rt:
        lines.append(f"    {code:28s} {mag:+.3f}  {detail}")
    return "\n".join(lines)
