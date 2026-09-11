"""Structured state & reason-trace API.

The inspector text dumps in :mod:`unscripted.inspect` are for terminals; this module
exposes the SAME internal state as JSON so an engine, a debug tool or the web
demo can render belief tables, provenance, memory decay, affect, relationships,
faction heat and per-turn reason traces. It is the machine-readable face of the
explainability USP -- real runtime objects, no summarisation, no mocks.
"""
from __future__ import annotations

from . import metahuman
from .affect import AffectEngine

_AFFECT = AffectEngine()


def _provenance(belief) -> list:
    out = []
    for p in belief.provenance:
        out.append({
            "claim_id": p.get("claim_id"),
            "origin_event": p.get("origin_event"),
            "kappa": p.get("kappa"),
            "eta": p.get("eta"),
        })
    return out


def agent_state(runtime, agent_id: str) -> dict:
    """Full structured snapshot of one agent's mind at the current world time."""
    agent = runtime.world.agents[agent_id]
    t = runtime.world.world_time
    affect = agent.affect
    tendencies = _AFFECT.action_tendencies(affect)

    beliefs = []
    for b in agent.beliefs.values():
        beliefs.append({
            "text": str(b.proposition),
            "proposition": b.proposition.as_dict(),
            "prob": round(b.expected_prob, 4),
            "support_for": round(b.support_for, 4),
            "support_against": round(b.support_against, 4),
            "ignorance": round(b.ignorance, 4),
            "conflict": round(b.conflict, 4),
            "provenance": _provenance(b),
        })
    beliefs.sort(key=lambda x: -max(x["prob"], 1.0 - x["prob"]))

    memory = []
    for m in sorted(agent.memory, key=lambda m: m.base_activation(t), reverse=True):
        act = m.base_activation(t)
        memory.append({
            "type": m.type,
            "content": m.content,
            "activation": round(act, 3),
            "status": "vivid" if act > 0 else ("faint" if act > -1.5 else "lost"),
            "importance": round(m.importance, 3),
            "valence": round(m.emotional_valence, 3),
            "source_conf": round(m.source_conf, 3),
        })

    # WHAT THEY THINK OF SOMEBODY, not only how they feel about them.
    #
    # `reputation` is what this character holds about another's conduct toward
    # OTHER people -- the thing the standing layer produces, and the thing a
    # game needs if it wants to draw a portrait that has cooled toward the
    # player. It was held in the world and reachable from nowhere: a studio
    # could not put it on screen, which is the same as it not existing.
    standing_engine = getattr(runtime.core, "standing", None)
    warm = getattr(standing_engine, "warmth", None) if (
        standing_engine is not None and standing_engine.enabled) else None

    relationships = {}
    for other in sorted(set(agent.relationships) | set(agent.reputation)):
        rel = agent.relationships.get(other) or {}
        entry = {
            "name": runtime.agent_name(other),
            "trust": round(rel.get("trust", 0.0), 3),
            "liking": round(rel.get("liking", 0.0), 3),
            "familiarity": round(rel.get("familiarity", 0.0), 3),
            "reputation": {dim: round(val, 3)
                           for dim, val in sorted((agent.reputation.get(other) or {}).items())},
        }
        # How much pull `other` has over the character being described.
        # Computed, never stored: a summary of respect, dependence, fear and how
        # many circles THEY stand in.
        #
        # `bridge_score(agent)` was the first version, and it measured the wrong
        # person: how many circles the observer stands in says nothing about how
        # much sway the other one has over them. Every number it produced was
        # about somebody who was not being asked about.
        if standing_engine is not None:
            network = getattr(runtime.core, "network", None)
            them = runtime.world.agents.get(other)
            reach = (network.bridge_score(them)
                     if (network is not None and them is not None) else 0.0)
            entry["influence"] = round(
                standing_engine.influence(agent, other, reach), 3)
        if warm is not None:
            # One number a UI can colour a character by: how warm they are
            # toward this person right now, in [-1, 1]. Absent when the layer is
            # off, rather than reported as zero, so nothing implies neutrality
            # where there is simply no opinion being modelled.
            entry["warmth"] = round(warm(agent, other), 3)
        relationships[other] = entry

    face = metahuman.affect_to_face(affect, action_tendencies=tendencies,
                                    gaze_target=runtime.config.player_id)

    trace = [{"code": code, "magnitude": round(mag, 4), "detail": detail}
             for code, mag, detail in runtime.core.last_traces.get(agent_id, [])]

    return {
        "id": agent_id,
        "name": runtime.agent_name(agent_id),
        "location": agent.location,
        "affect": {
            "valence": round(affect.mood.p, 4),
            "arousal": round(affect.mood.a, 4),
            "dominance": round(affect.mood.d, 4),
            "baseline": affect.baseline.as_dict(),
            "dominant_emotion": face["emotion"]["dominant"],
            "intensity": face["emotion"]["intensity"],
            "stress": round(_AFFECT.stress(affect), 3),
            "active_emotions": {k: round(v, 3) for k, v in affect.active_emotions.items()},
            "action_tendencies": tendencies,
        },
        "face": face,
        "beliefs": beliefs,
        "memory": memory,
        "relationships": relationships,
        "secrets": len(agent.secrets),
        "goals": [g.get("content") if isinstance(g, dict) else g for g in (agent.goals or [])],
        "reason_trace": trace,
    }


def knowledge_state(runtime, *, limit: int = 40) -> dict:
    """Who knows what, how far from the source, and how it got there.

    The machine-readable form of the thing the runtime is actually for. A UI can
    render it as a spread map; a QA tool can diff it between runs; a designer can
    answer "why does he know that" without reading a log.

    Deliberately built from live belief state plus the event ledger, not from a
    separate tracking structure: a second bookkeeping copy is a second thing that
    can be wrong.
    """
    facts = {}
    for agent in runtime.world.agents.values():
        for key, belief in agent.beliefs.items():
            entry = facts.setdefault(key, {
                "key": key,
                "text": str(belief.proposition),
                "predicate": belief.proposition.predicate,
                # How specific this version is: a headline names the place, a
                # witness account names the place AND the shift.
                "detail": sum(1 for v in (belief.proposition.slots or {}).values()
                              if v is not None),
                "holders": [],
                "origins": set(),
            })
            entry["holders"].append({
                "agent": agent.id,
                "name": runtime.agent_name(agent.id),
                "prob": round(belief.expected_prob, 4),
                "confidence": round(max(belief.expected_prob, 1.0 - belief.expected_prob), 4),
                "hops": belief.hops,
                "origin": belief.primary_origin,
                "times_heard": sum(belief.origin_counts.values()),
                "independent_origins": len(belief.origin_counts),
            })
            entry["origins"].update(belief.origin_counts)

    out = []
    for entry in facts.values():
        entry["holders"].sort(key=lambda h: (h["hops"], h["name"]))
        first_hand = [h for h in entry["holders"] if h["hops"] == 0]
        out.append({
            **entry,
            "origins": sorted(entry["origins"]),
            "reach": len(entry["holders"]),
            "first_hand": len(first_hand),
            "hearsay": len(entry["holders"]) - len(first_hand),
            "max_hops": max((h["hops"] for h in entry["holders"]), default=0),
        })
    # widest-spread first: that is what a designer wants to look at
    out.sort(key=lambda f: (-f["reach"], -f["hearsay"], f["text"]))

    transmissions = []
    if runtime.store is not None and hasattr(runtime.store, "diffusion_events"):
        for row in runtime.store.diffusion_events(limit=limit):
            described = ""
            if row.get("distortion_kind"):
                from .distortion import describe
                described = describe(row["distortion_kind"], row.get("distortion_detail") or {})
            transmissions.append({
                **row,
                "distortion_note": described,
                "from_name": runtime.agent_name(row["from"]) if row["from"] else None,
                "to_name": runtime.agent_name(row["to"]) if row["to"] else None,
                "place_label": runtime.world.place_label(row["place"]) if row["place"] else None,
            })

    occupancy = {}
    for agent in runtime.world.agents.values():
        if agent.location:
            occupancy.setdefault(agent.location, []).append(
                {"id": agent.id, "name": runtime.agent_name(agent.id)})

    # What a debug HUD needs in order to show the parts of the simulation that
    # were previously reachable only from Python. Without these, an engine
    # integration can render a talking face and nothing of what makes the
    # character worth talking to.
    from . import topology

    classes = []
    for predicate, spec in sorted((runtime.world.predicates or {}).items()):
        knowledge = topology.KnowledgeClass(predicate, spec)
        classes.append(knowledge.as_dict())

    circles = {}
    for agent in runtime.world.agents.values():
        for circle in topology.circles(agent):
            circles.setdefault(circle, []).append(agent.id)

    contested = []
    for fact in out:
        holders = fact["holders"]
        if len(holders) < 2:
            continue
        spread = max(h["prob"] for h in holders) - min(h["prob"] for h in holders)
        if spread >= 0.25:
            contested.append({"text": fact["text"], "disagreement": round(spread, 3),
                              "believers": [h["name"] for h in holders if h["prob"] >= 0.6],
                              "doubters": [h["name"] for h in holders if h["prob"] <= 0.4]})
    contested.sort(key=lambda c: -c["disagreement"])

    judgements = []
    for agent in runtime.world.agents.values():
        for memory in agent.memory:
            if memory.type != "judgement":
                continue
            judgements.append({
                "holder": agent.id, "holder_name": runtime.agent_name(agent.id),
                "about": memory.about[0] if memory.about else None,
                "about_name": (runtime.agent_name(memory.about[0])
                               if memory.about else None),
                "text": memory.content, "occasions": memory.episodes,
                "evidence": list(memory.evidence)})

    # One incident, several versions of it. A radio headline reaches everybody and
    # says little; a witness holds the detail and only they do; a witness who
    # could not read the scene holds something wrong. All three trace to the same
    # origin, and the runtime has always known that -- it simply never said so, so
    # a HUD saw three unrelated facts where there is one story.
    #
    # Reach and detail are separate properties, and this is where that becomes
    # visible: widely known and thin, narrowly known and precise, or widely known
    # and wrong.
    stories: dict = {}
    for fact in out:
        for origin in fact["origins"]:
            story = stories.setdefault(origin, {"origin": origin, "versions": []})
            story["versions"].append({
                "text": fact["text"],
                "predicate": fact["predicate"],
                "detail": fact.get("detail"),
                "reach": fact["reach"],
                "first_hand": fact["first_hand"],
                "held_by": [h["name"] for h in fact["holders"]],
            })
    story_list = []
    for story in stories.values():
        versions = sorted(story["versions"], key=lambda v: (-v["reach"], v["text"]))
        if len(versions) < 2:
            continue                      # one version is a fact, not a story
        widest = versions[0]
        richest = max(versions, key=lambda v: (v["detail"] or 0, v["first_hand"]))
        story_list.append({
            **story, "versions": versions,
            "widest_known": {"text": widest["text"], "reach": widest["reach"]},
            "most_detailed": {"text": richest["text"], "reach": richest["reach"],
                              "first_hand": richest["first_hand"]},
            "note": "versions of one incident: reach and detail are not the same thing",
        })
    story_list.sort(key=lambda s: -max(v["reach"] for v in s["versions"]))

    return {
        "world_time": runtime.world.world_time,
        "time_of_day": _clock(runtime.world.world_time),
        "facts": out,
        #: Incidents with more than one version in circulation.
        "stories": story_list,
        "transmissions": transmissions,
        #: What a world declares about each kind of claim: who circulates it,
        #: where, how readily. Lets a HUD explain why something has not spread.
        "knowledge_classes": classes,
        #: Groups, and who bridges between them -- the routes information can take.
        "circles": [{"circle": name, "members": sorted(ids)}
                    for name, ids in sorted(circles.items())],
        "bridges": [{"agent": agent_id, "name": runtime.agent_name(agent_id),
                     "circles": circle_list}
                    for agent_id, circle_list in sorted(topology.bridges(runtime.world).items())],
        #: Claims people actively disagree about. The interesting scenes.
        "contested": contested[:limit],
        #: Conclusions drawn from repeated experience, and what they rest on.
        "judgements": judgements,
        "occupancy": [{"place": place, "label": runtime.world.place_label(place),
                       "people": sorted(people, key=lambda p: p["name"])}
                      for place, people in sorted(occupancy.items())],
    }


def _clock(world_time: int) -> str:
    minute = world_time % 1440
    return f"{minute // 60:02d}:{minute % 60:02d}"


def world_state(runtime) -> dict:
    """Structured world snapshot: time, factions/heat/clocks, rumour exposure."""
    factions = {}
    for fid, f in runtime.core.director.factions.items():
        factions[fid] = {
            "influence": round(f.influence, 3),
            "heat": round(f.heat, 3),
            "resources": round(getattr(f, "resources", 0.0), 3),
            "clocks": [{"name": c.name, "filled": c.filled, "size": c.size}
                       for c in f.clocks.values()],
        }

    media = []
    for (agent, channel), value in runtime.world.media_exposure.items():
        entry = {"agent": agent, "channel": channel}
        entry.update(value if isinstance(value, dict) else {"value": value})
        media.append(entry)

    return {
        "world_time": runtime.world.world_time,
        "factions": factions,
        "media_exposure": media,
        "capabilities": runtime.capability_plan.resolved,
    }
