"""Deterministic NPC and starting-knowledge generation.

The generator converts environment, appearance and optional role/faction hints
into production world-pack character JSON plus initial subjective knowledge. It
does not call a language model and does not invent unrestricted state.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict

from .contracts import DEFAULT_PLAYER_ID
from .determinism import derive_seed, seeded_uniform


#: Neutral fallback name pools. A pack supplies its own through
#: ``world.json: {"name_pools": {"given": [...], "family": [...]}}`` -- names carry a
#: setting, and generated characters should sound like they belong to the world
#: they are generated into.
DEFAULT_GIVEN_NAMES = [
    "Ari", "Bex", "Cato", "Dara", "Eli", "Faye", "Galen", "Hana",
    "Ivo", "Juno", "Kara", "Lio", "Mara", "Niko", "Orin", "Pia",
]
DEFAULT_FAMILY_NAMES = ["Vale", "Rook", "Stone", "Mira", "Cross", "Nox", "Aldar"]

ROLE_BY_PLACE = {
    "surveillance": ("role:officer", "watchman"),
    "privacy": ("role:fixer", "informant"),
    "noise": ("role:bartender", "barkeep"),
    "default": ("role:trader", "resident"),
}

APPEARANCE_RULES = {
    "uniform": {"role": "role:officer", "identity": "officer", "status": 0.65, "resources": 0.50},
    "tailored_suit": {"role": "role:officer", "identity": "executive", "status": 0.85, "resources": 0.85},
    "apron": {"role": "role:bartender", "identity": "service_worker", "status": 0.45, "resources": 0.45},
    "red_cyberjacket": {"role": "role:fixer", "identity": "gang_member", "status": 0.38, "resources": 0.42},
    "worn_jacket": {"role": "role:trader", "identity": "hustler", "status": 0.25, "resources": 0.12},
    "gray_coat": {"role": "role:trader", "identity": "journalist", "status": 0.50, "resources": 0.45},
    "medical_coat": {"role": "role:fixer", "identity": "medic", "status": 0.55, "resources": 0.50},
}


@dataclass
class CharacterGenerationRequest:
    count: int = 1
    location_id: str | None = None
    faction_id: str | None = None
    appearances: list[str] = field(default_factory=list)
    role_hints: list[str] = field(default_factory=list)
    seed: str = "generated"
    id_prefix: str = "agent:gen"
    #: Who the generated characters have a starting relationship with. Defaults to
    #: the SDK's default player id only because a bare request has nothing better;
    #: callers that configured a different player must pass it.
    player_id: str = DEFAULT_PLAYER_ID

    @staticmethod
    def from_dict(data: dict) -> "CharacterGenerationRequest":
        return CharacterGenerationRequest(
            count=int(data.get("count", 1)),
            location_id=data.get("location_id"),
            faction_id=data.get("faction_id"),
            appearances=list(data.get("appearances", [])),
            role_hints=list(data.get("role_hints", [])),
            seed=data.get("seed", "generated"),
            id_prefix=data.get("id_prefix", "agent:gen"),
            player_id=data.get("player_id", DEFAULT_PLAYER_ID),
        )


@dataclass
class GeneratedWorldContent:
    characters: list[dict]
    initial_beliefs: list[dict]

    def as_dict(self):
        return asdict(self)


def generate_characters(world_data: dict, request: CharacterGenerationRequest) -> GeneratedWorldContent:
    places = world_data.get("places", {})
    factions = world_data.get("factions", [])
    location_id = request.location_id or _first_key(places) or "place:unknown"
    place = places.get(location_id, {})
    pools = world_data.get("name_pools") or {}
    given_names = list(pools.get("given") or DEFAULT_GIVEN_NAMES)
    family_names = list(pools.get("family") or DEFAULT_FAMILY_NAMES)
    faction_id = request.faction_id or _faction_for_location(factions, location_id)
    characters = []
    beliefs = []

    for idx in range(request.count):
        seed = derive_seed(request.seed, location_id, faction_id or "", idx, "character_generator")
        appearance_token = _pick(request.appearances, seed) or _appearance_from_place(place, seed)
        appearance = _appearance_dict(appearance_token)
        profile = _profile_from_context(
            idx=idx,
            seed=seed,
            location_id=location_id,
            place=place,
            faction_id=faction_id,
            appearance_token=appearance_token,
            appearance=appearance,
            role_hints=request.role_hints,
            id_prefix=request.id_prefix,
            player_id=request.player_id,
            given_names=given_names,
            family_names=family_names,
        )
        characters.append(profile)
        beliefs.extend(_initial_beliefs_for(profile, location_id, place))
    return GeneratedWorldContent(characters=characters, initial_beliefs=beliefs)


def write_generated_content(pack_path: str, content: GeneratedWorldContent) -> list[str]:
    """Append generated content to a world pack. Returns written file paths."""
    chardir = os.path.join(pack_path, "characters")
    os.makedirs(chardir, exist_ok=True)
    written = []
    for character in content.characters:
        fn = _safe_filename(character["id"]) + ".json"
        path = os.path.join(chardir, fn)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(character, f, indent=2, sort_keys=True)
            f.write("\n")
        written.append(path)

    initial_path = os.path.join(pack_path, "initial_state.json")
    initial = {"beliefs": []}
    if os.path.exists(initial_path):
        with open(initial_path, "r", encoding="utf-8") as f:
            initial = json.load(f)
    existing = initial.setdefault("beliefs", [])
    existing.extend(content.initial_beliefs)
    with open(initial_path, "w", encoding="utf-8") as f:
        json.dump(initial, f, indent=2, sort_keys=True)
        f.write("\n")
    written.append(initial_path)
    return written


def _profile_from_context(*, idx, seed, location_id, place, faction_id,
                          appearance_token, appearance, role_hints, id_prefix,
                          player_id, given_names, family_names):
    app_rule = APPEARANCE_RULES.get(appearance_token, {})
    role = app_rule.get("role") or _role_from_place(place, role_hints)
    identity = app_rule.get("identity") or _identity_from_role(role)
    public = _name(seed, idx, given_names)
    agent_id = f"{id_prefix}_{_slug(public)}_{idx + 1}"
    status = _clamp01(app_rule.get("status", _status_from_place(place, seed)))
    resources = _clamp01(app_rule.get("resources", _resources_from_status(status, seed)))
    big_five = _big_five(place, role, seed)
    schwartz = _values(place, role, identity)
    needs = _needs(place, role, resources)
    education = _education(role, identity)
    identities = [{"id": identity, "group": faction_id or f"district:{_slug(location_id)}",
                   "accessibility": round(0.65 + 0.25 * seeded_uniform(_subseed(seed, "identity")), 2)}]
    return {
        "id": agent_id,
        "class": "core:NPCAgent",
        "names": {"public": public, "objective": f"{public} {_surname(seed, family_names)}"},
        "big_five": big_five,
        "schwartz": schwartz,
        "needs": needs,
        "identities": identities,
        "roles": [{"role": role, "context": faction_id or location_id}],
        "appearance": appearance,
        "education": {"domains": education},
        "relationships": {player_id: {"trust": 0.3, "liking": 0.0, "familiarity": 0.0}},
        "secrets": [],
        "goals": [{"content": _goal(role, identity),
                   "priority": round(0.55 + 0.35 * seeded_uniform(_subseed(seed, "goal")), 2)}],
        "social_status": round(status, 2),
        "resources": round(resources, 2),
        "location": location_id,
    }


def _initial_beliefs_for(profile: dict, location_id: str, place: dict) -> list[dict]:
    agent_id = profile["id"]
    role = profile["roles"][0]["role"]
    beliefs = [
        {
            "agent": agent_id,
            "proposition": {
                "predicate": "space:exactly_at",
                "slots": {"entity": agent_id, "place": location_id},
                "polarity": "+"
            },
            "summary": f"{profile['names']['public']} knows where they are stationed.",
            "origin_event": f"seed:{agent_id}:location",
            "trust": 0.96,
            "competence": 0.95,
            "importance": 0.45
        },
        {
            "agent": agent_id,
            "proposition": {
                "predicate": "core:holds_role",
                "slots": {"agent": agent_id, "role": role, "context": profile["roles"][0]["context"]},
                "polarity": "+"
            },
            "summary": f"{profile['names']['public']} understands their local role.",
            "origin_event": f"seed:{agent_id}:role",
            "trust": 0.92,
            "competence": 0.90,
            "importance": 0.55
        }
    ]
    for predicate, key in (
        ("place:has_surveillance", "surveillance_level"),
        ("place:has_privacy", "privacy_level"),
        ("place:has_noise", "noise_level"),
    ):
        if key in place:
            level = _band(place[key])
            beliefs.append({
                "agent": agent_id,
                "proposition": {
                    "predicate": predicate,
                    "slots": {"place": location_id, "level": level},
                    "polarity": "+"
                },
                "summary": f"{profile['names']['public']} knows the local {key.replace('_', ' ')} is {level}.",
                "origin_event": f"seed:{agent_id}:{key}",
                "trust": 0.90,
                "competence": 0.85,
                "importance": 0.40
            })
    return beliefs


def _role_from_place(place, role_hints):
    if role_hints:
        return role_hints[0] if role_hints[0].startswith("role:") else f"role:{role_hints[0]}"
    scores = {
        "surveillance": place.get("surveillance_level", 0.0),
        "privacy": place.get("privacy_level", 0.0),
        "noise": place.get("noise_level", 0.0),
    }
    key = max(scores.items(), key=lambda kv: kv[1])[0]
    return ROLE_BY_PLACE.get(key, ROLE_BY_PLACE["default"])[0]


def _appearance_from_place(place, seed):
    if place.get("surveillance_level", 0.0) > 0.65:
        return "uniform"
    if place.get("privacy_level", 0.0) > 0.65:
        return "gray_coat"
    if place.get("noise_level", 0.0) > 0.50:
        return "apron"
    return _pick(["worn_jacket", "gray_coat", "tailored_suit"], seed)


def _big_five(place, role, seed):
    return {
        "openness": round(_clamp01(0.45 + 0.25 * seeded_uniform(_subseed(seed, "openness"))), 2),
        "conscientiousness": round(_clamp01(0.45 + 0.25 * place.get("surveillance_level", 0.0)), 2),
        "extraversion": round(_clamp01(0.35 + 0.35 * place.get("noise_level", 0.0)), 2),
        "agreeableness": round(_clamp01(0.45 + (0.10 if role in ("role:bartender", "role:trader") else -0.05)), 2),
        "emotional_stability": round(_clamp01(0.55 - 0.20 * place.get("noise_level", 0.0)
                                             + 0.10 * place.get("privacy_level", 0.0)), 2),
    }


def _values(place, role, identity):
    values = {
        "security": round(_clamp01(0.45 + 0.35 * place.get("surveillance_level", 0.0)), 2),
        "self_direction": round(_clamp01(0.35 + 0.25 * place.get("privacy_level", 0.0)), 2),
        "benevolence": 0.45,
    }
    if role == "role:officer":
        values.update({"conformity": 0.70, "power": 0.50})
    if identity in ("executive", "gang_member"):
        values.update({"power": 0.75, "achievement": 0.60})
    return values


def _needs(place, role, resources):
    needs = {
        "safety": round(_clamp01(0.35 + 0.25 * place.get("surveillance_level", 0.0)), 2),
        "income": round(_clamp01(0.80 - 0.55 * resources), 2),
    }
    if role in ("role:bartender", "role:trader"):
        needs["recognition"] = 0.45
    return needs


def _education(role, identity):
    base = {"general": 0.45, "street": 0.45}
    if role == "role:officer":
        base.update({"law": 0.70, "street": 0.55})
    if role == "role:bartender":
        base.update({"gossip": 0.75, "street": 0.65})
    if identity == "executive":
        base.update({"corporate": 0.85, "general": 0.80})
    if identity == "medic":
        base.update({"medicine": 0.80, "general": 0.70})
    return base


def _goal(role, identity):
    if role == "role:officer":
        return "keep_order"
    if identity == "executive":
        return "manage_reputation"
    if role == "role:bartender":
        return "protect_regulars"
    if identity == "hustler":
        return "make_rent"
    return "stay_useful"


def _identity_from_role(role):
    return {
        "role:officer": "officer",
        "role:bartender": "bartender",
        "role:fixer": "fixer",
        "role:trader": "trader",
    }.get(role, "resident")


def _status_from_place(place, seed):
    return 0.30 + 0.25 * place.get("surveillance_level", 0.0) + 0.15 * seeded_uniform(_subseed(seed, "status"))


def _resources_from_status(status, seed):
    return status * 0.75 + 0.20 * seeded_uniform(_subseed(seed, "resources"))


def _appearance_dict(token):
    if not token:
        return {}
    return {"garment": f"item:{token}"}


def _faction_for_location(factions, location_id):
    for faction in factions:
        if location_id in faction.get("territory", []):
            return faction.get("id")
    return None


def _first_key(mapping):
    return next(iter(mapping), None)


def _pick(items, seed):
    if not items:
        return None
    return items[int(seeded_uniform(seed) * len(items)) % len(items)]


def _name(seed, idx, pool):
    return pool[(int(seeded_uniform(_subseed(seed, "name")) * len(pool)) + idx) % len(pool)]


def _surname(seed, pool):
    return pool[int(seeded_uniform(_subseed(seed, "surname")) * len(pool)) % len(pool)]


def _safe_filename(value):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value.replace("agent:", "")).strip("_")


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _subseed(seed: bytes, salt: str) -> bytes:
    return derive_seed(seed.hex(), "character", salt, 0, "subseed")


def _band(value):
    value = float(value)
    if value >= 0.67:
        return "high"
    if value <= 0.33:
        return "low"
    return "medium"
