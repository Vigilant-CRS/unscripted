"""PerceptionEngine (Technical Core v0.2 §6; Ontology v0.4 §3.10; spec v0.5 §6.1).

Determines who could perceive an event and how well. Reference model: co-location +
environmental noise + (for broadcasts) media exposure. Produces quality-weighted
observations, so a noisy bar yields partial hearing.
"""
from __future__ import annotations
from .events import Event, Observation
from .determinism import derive_seed, seeded_uniform


class PerceptionEngine:
    module_id = "perception"
    version = "0.5.0"

    def __init__(self, params=None):
        self.params = {"base_quality": 0.95}
        if params:
            self.params.update(params)

    def filter(self, event: Event, world):
        """Return list[Observation] for agents who can perceive the event."""
        obs = []
        place = world.places.get(event.location, {})
        noise = place.get("noise_level", 0.0)            # [0,1]

        if event.type == "broadcast":
            channel = event.payload.get("channel")
            for agent in world.agents.values():
                exposure = world.media_exposure.get((agent.id, channel))
                if exposure:
                    attention = exposure.get("attention", 0.5)
                    quality = max(0.0, attention)
                    obs.append(Observation(agent.id, event.event_id, "media", quality, event))
            return obs

        # An event may name its audience: a word between two people in a crowded
        # square is heard by those nearby, not by everyone in the square. Without
        # this, every retelling was perceived by the entire population of a place,
        # which is both wrong and quadratic in crowd size.
        audience = event.payload.get("audience")
        if audience is not None:
            audience = set(audience)

        # Direct events: whoever is co-located. Asking the world for occupants
        # rather than scanning the whole cast is what keeps a crowded scene linear
        # -- more people produce more events AND made each event more expensive to
        # route, which was the dominant cost in a large world.
        for agent in world.occupants(event.location):
            if agent.id == event.actor:
                continue
            if audience is not None and agent.id not in audience:
                continue
            seed = derive_seed(world.global_seed, agent.id, event.event_id,
                               world.world_time, self.module_id)
            jitter = (seeded_uniform(seed) - 0.5) * 0.1
            quality = max(0.0, self.params["base_quality"] * (1.0 - noise) + jitter)
            modality = ("hearing" if event.type in ("claim", "promise", "threat",
                                                    "question") else "sight")
            obs.append(Observation(agent.id, event.event_id, modality, quality, event))
        return obs
