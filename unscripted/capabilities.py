"""Runtime capability resolution.

Each capability has one owner: BUILTIN, EXTERNAL or DISABLED. The resolver keeps
startup deterministic and prevents ambiguous mixed authority.
"""
from __future__ import annotations

from .contracts import CapabilityPlan


VALID_MODES = {"BUILTIN", "EXTERNAL", "DISABLED"}

DEFAULT_CAPABILITIES = {
    "semantic_parser": "BUILTIN",
    "text_realizer": "BUILTIN",
    "dialogue_validation": "BUILTIN",
    "storage": "BUILTIN",
    "inspector": "BUILTIN",
}

HARD_REQUIRED = {"semantic_parser", "text_realizer", "dialogue_validation", "storage"}


def normalize_mode(value: str) -> str:
    return str(value or "").upper()


def resolve_capabilities(config) -> CapabilityPlan:
    resolved = dict(DEFAULT_CAPABILITIES)
    warnings = []
    for capability, mode in (config.capabilities or {}).items():
        norm = normalize_mode(mode)
        if norm not in VALID_MODES:
            raise ValueError(f"Invalid capability mode for {capability}: {mode}")
        resolved[capability] = norm

    for capability in HARD_REQUIRED:
        if resolved.get(capability) == "DISABLED":
            raise ValueError(f"Required capability cannot be DISABLED: {capability}")

    provider = (config.text_realizer or {}).get("provider", "template")
    declared = resolved.get("text_realizer")
    if provider == "http":
        implied = "EXTERNAL"
        if not (config.text_realizer or {}).get("endpoint"):
            raise ValueError("HTTP text_realizer requires text_realizer.endpoint")
    elif provider == "template":
        implied = "BUILTIN"
    else:
        raise ValueError(f"Unknown text_realizer.provider: {provider}")
    if declared and declared != implied:
        # Silently rewriting an explicit declaration hides a misconfiguration:
        # a studio that asked for EXTERNAL and got BUILTIN would ship the wrong one.
        warnings.append(
            f"capabilities.text_realizer was declared {declared} but text_realizer."
            f"provider={provider!r} implies {implied}; using {implied}.")
    resolved["text_realizer"] = implied

    if resolved.get("dialogue_validation") != "BUILTIN":
        warnings.append("Production mode should keep dialogue_validation BUILTIN.")

    return CapabilityPlan(resolved=resolved, warnings=warnings)
