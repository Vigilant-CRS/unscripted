"""Engine and third-party bridge contracts.

The SDK exposes a neutral JSON ABI. Native plugins for Unreal, Unity, Godot or
third-party NPC frontends should map their local events into this contract and
map Unscripted responses back to their own systems.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

from .events import Event


@dataclass(frozen=True)
class BridgeProfile:
    bridge_id: str
    category: str
    inbound_events: tuple[str, ...]
    outbound_results: tuple[str, ...]
    notes: str

    def as_dict(self):
        return asdict(self)


BRIDGE_PROFILES = {
    "unreal": BridgeProfile(
        "unreal", "engine",
        ("gameplay_event", "dialogue_input", "time_advance", "savegame_hook"),
        ("dialogue_response", "action_proposal", "inspector_trace", "snapshot_id"),
        "Map Gameplay Tags / State Tree events to WorldEvent JSON.",
    ),
    "unity": BridgeProfile(
        "unity", "engine",
        ("gameobject_event", "dialogue_input", "time_advance", "savegame_hook"),
        ("dialogue_response", "action_proposal", "inspector_trace", "snapshot_id"),
        "Map GameObject ids or ECS entity ids to agent ids.",
    ),
    "godot": BridgeProfile(
        "godot", "engine",
        ("node_signal", "dialogue_input", "time_advance", "savegame_hook"),
        ("dialogue_response", "action_proposal", "inspector_trace", "snapshot_id"),
        "Map node paths or stable resource ids to agent ids.",
    ),
    "custom": BridgeProfile(
        "custom", "engine",
        ("world_event", "dialogue_input", "time_advance"),
        ("dialogue_response", "event_receipt", "inspector_trace"),
        "Use the neutral HTTP/JSON ABI directly.",
    ),
    "inworld": BridgeProfile(
        "inworld", "npc_frontend",
        ("dialogue_input", "character_state", "world_event"),
        ("allowed_facts", "avoid_topics", "memory_trace", "validated_response"),
        "Use Unscripted as external social-memory and policy authority.",
    ),
    "convai": BridgeProfile(
        "convai", "npc_frontend",
        ("dialogue_input", "world_event", "voice_turn_metadata"),
        ("dialogue_plan", "allowed_facts", "avoid_topics", "validated_response"),
        "Use Convai-like frontends for voice/avatar while Unscripted owns causal memory.",
    ),
    "metahuman": BridgeProfile(
        "metahuman", "avatar_frontend",
        ("dialogue_input", "world_event", "gaze_target"),
        ("validated_response", "arkit_blendshapes", "face_state", "prosody_hints", "posture"),
        "Stream ARKit-52 blendshapes + prosody onto a MetaHuman via Live Link; "
        "Unscripted owns dialogue, affect and gaze.",
    ),
    "unreal_metahuman": BridgeProfile(
        "unreal_metahuman", "engine",
        ("gameplay_event", "dialogue_input", "time_advance", "gaze_target", "savegame_hook"),
        ("avatar_packet", "arkit_blendshapes", "action_proposal", "inspector_trace", "snapshot_id"),
        "Unreal Engine 5.6+/6 plugin: map Gameplay Tags / State Tree events to "
        "WorldEvent JSON and drive MetaHuman faces from the avatar packet.",
    ),
    "charisma": BridgeProfile(
        "charisma", "narrative_frontend",
        ("story_node_event", "dialogue_input", "world_event"),
        ("knowledge_query", "social_state", "validation_result"),
        "Use authored narrative graph externally; Unscripted owns epistemic social state.",
    ),
    "nvidia_game_agent": BridgeProfile(
        "nvidia_game_agent", "model_runtime",
        ("tool_call", "dialogue_input", "world_event"),
        ("dialogue_plan", "tool_context", "validated_response"),
        "Use model/runtime infrastructure externally; Unscripted owns world-memory semantics.",
    ),
}


def list_bridge_profiles():
    return {key: profile.as_dict() for key, profile in BRIDGE_PROFILES.items()}


def bridge_event_to_world_event(payload: dict, *, default_world_time: int) -> Event:
    """Convert a neutral bridge event JSON payload into a Runtime Event."""
    event_id = int(payload["event_id"])
    return Event(
        event_id=event_id,
        world_time=int(payload.get("world_time", default_world_time)),
        type=payload["type"],
        actor=payload.get("actor"),
        location=payload.get("location"),
        payload=payload.get("payload", {}),
        canonical=bool(payload.get("canonical", True)),
    )


def dialogue_response_to_bridge(response) -> dict:
    return {
        "speaker_id": response.speaker_id,
        "text": response.text,
        "act": response.act,
        "verdict": response.verdict,
        "utility": response.utility,
        "style": response.style,
        "reasons": response.reasons,
    }
