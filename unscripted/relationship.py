"""Part C -- cross-cutting state owners (spec v0.5 §4; review P1.3, P1.4).

RelationshipEngine owns the relationship vector incl. trust (asymmetric kinetics,
positive/negative applied separately). ReputationEngine owns audience-specific
reputation. IdentityEngine owns salient identity (softmax with a neutral baseline
and temporal inertia).
"""
from __future__ import annotations
import math
from .types import clamp01, clamp_signed


class RelationshipEngine:
    module_id = "relationship"
    version = "0.6.0"

    def __init__(self, params=None):
        # slow up, fast down (spec §4.2); positive/negative applied separately (review P1.3)
        self.params = {"eta_up": 0.10, "eta_down": 0.40, "eta_other": 0.20}
        if params:
            self.params.update(params)

    def apply(self, agent, deltas, reasons):
        """Apply staged relationship deltas to the owned vector."""
        # group by (subject, field)
        grouped = {}
        for d in deltas:
            grouped.setdefault((d.key.subject_id, d.key.field), []).append(d)
        for (subject, field), ds in grouped.items():
            rel = agent.relationships.setdefault(subject, {})
            cur = rel.get(field, 0.3 if field == "trust" else 0.0)
            pos = sum(d.amount for d in ds if d.amount >= 0)
            neg = sum(d.amount for d in ds if d.amount < 0)
            if field == "trust":
                new = cur + self.params["eta_up"] * pos + self.params["eta_down"] * neg
            else:
                new = cur + self.params["eta_other"] * (pos + neg)
            new = clamp01(new) if field in ("trust", "respect", "fear", "dependence") else clamp_signed(new)
            rel[field] = new
            reasons.append(("relationship.applied", round(new - cur, 4),
                            {"subject": subject, "field": field,
                             "pos": round(pos, 3), "neg": round(neg, 3),
                             "reasons": [d.reason for d in ds]}))


class ReputationEngine:
    module_id = "reputation"
    version = "0.6.0"

    def __init__(self, params=None):
        self.params = {"eta_image": 0.25, "eta_rep": 0.10, "decay": 0.001}
        if params:
            self.params.update(params)

    def apply(self, agent, deltas, reasons):
        for d in deltas:
            store = agent.reputation.setdefault(d.key.subject_id, {})
            dim = d.key.dimension or "general"
            cur = store.get(dim, 0.0)
            new = clamp_signed(cur + d.amount)
            store[dim] = new
            reasons.append(("reputation.applied", round(new - cur, 4),
                            {"subject": d.key.subject_id, "dimension": dim, "reason": d.reason}))


class IdentityEngine:
    module_id = "identity"
    version = "0.6.0"

    def __init__(self, params=None):
        # review P1.4: neutral/self baseline + inertia to prevent rapid switching
        self.params = {"beta": 4.0, "w_acc": 1.0, "w_comp": 1.0, "w_norm": 1.0, "w_threat": 1.0,
                       "neutral_fit": 0.4, "inertia": 0.5}
        if params:
            self.params.update(params)

    def salience(self, agent, context, threat_by_identity=None):
        """Softmax over identities + a neutral 'self' baseline (spec §4.4, review P1.4)."""
        p = self.params
        threat_by_identity = threat_by_identity or {}
        fits = {}
        for ident in agent.identities:
            iid = ident["id"]
            acc = ident.get("accessibility", 0.5)
            comp = context.get("comparative_fit", {}).get(iid, 0.0)  # meta-contrast (needs context set)
            norm = context.get("normative_fit", {}).get(iid, 0.0)
            threat = threat_by_identity.get(iid, 0.0)
            fits[iid] = p["w_acc"] * acc + p["w_comp"] * comp + p["w_norm"] * norm + p["w_threat"] * threat
        fits["_neutral"] = p["neutral_fit"]   # absolute baseline: "no identity strongly salient"
        # softmax
        mx = max(fits.values())
        exps = {k: math.exp(p["beta"] * (v - mx)) for k, v in fits.items()}
        z = sum(exps.values())
        sal = {k: v / z for k, v in exps.items()}
        # inertia toward previous salience (owned state: persisted with the agent, so
        # a restored save resumes with the same switching inertia it had at save time)
        prev = agent.identity_salience
        if prev:
            sal = {k: p["inertia"] * prev.get(k, 0.0) + (1 - p["inertia"]) * v for k, v in sal.items()}
            z2 = sum(sal.values())
            sal = {k: v / z2 for k, v in sal.items()}
        agent.identity_salience = sal
        top = max(sal.items(), key=lambda kv: kv[1])
        return top[0], sal
