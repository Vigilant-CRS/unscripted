// `usc/topology.py`. Why not everyone knows everything.
//
// Diffusion answers *how* information moves. This answers *where it stops*,
// which in a city-sized cast matters more: left to co-location and trust alone,
// a claim eventually reaches anyone who shares a room with anyone, and a
// long-running world has plenty of time.
//
// Knowledge is not a hierarchy. A street vendor knows more about the local gang
// than a corporate director does, so a single pyramid would be wrong. A claim is
// classified on several independent axes and a listener is reachable on some and
// not others.
//
// ORDER NOTE. `circles()` returns a Python `set`, whose iteration order is not
// defined by the language -- and the module never relies on it: every place the
// contents leave this file they go through `sorted()`. So `std::set` is the
// right container here, exactly where `OrderedMap` is right elsewhere. Reading
// which is which is the whole job.
#pragma once

#include <algorithm>
#include <cmath>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"

namespace usc {

/// How freely a claim travels once somebody holds it. A multiplier on the
/// chance of passing it on, NOT a hard gate: people do leak restricted things,
/// and a model where they never do is not a model of people.
inline double transmissibility_for(const std::string& classification) {
    if (classification == "public")     return 1.0;
    if (classification == "common")     return 0.85;
    if (classification == "local")      return 0.6;
    if (classification == "trade")      return 0.45;  // shop talk: passed on
    if (classification == "restricted") return 0.2;   // readily, but only to
    if (classification == "secret")     return 0.05;  // those who care
    return 0.85;                                      // TRANSMISSIBILITY.get(..., 0.85)
}

inline constexpr const char* DEFAULT_CLASS = "common";

/// What a world declares about one kind of claim.
struct KnowledgeClass {
    std::string predicate;
    std::string classification = DEFAULT_CLASS;
    std::string domain = "street";
    /// Groups, roles or factions whose members will pass this on. Empty means
    /// anyone. This restricts CIRCULATION, never perception: seeing a thing you
    /// have no clearance for is exactly how interesting trouble starts.
    std::vector<std::string> access;
    /// Places where it circulates at all. Empty means everywhere.
    std::vector<std::string> locality;
    double transmissibility = 0.85;

    Json as_json() const {
        Json out = Json::object();
        out["predicate"] = predicate;
        out["classification"] = classification;
        out["domain"] = domain;
        Json who = Json::array();
        for (const std::string& one : access) who.push(Json(one));
        out["access"] = who;
        Json where = Json::array();
        for (const std::string& one : locality) where.push(Json(one));
        out["locality"] = where;
        out["transmissibility"] = py_round(transmissibility, 3);
        return out;
    }
};

/// The declared class of a claim, or a neutral default.
/// The class a pack declared for one named predicate.
///
/// Split out of `class_for` because the read model walks the whole predicate
/// table and has no proposition to hand -- the alternative was a second copy of
/// six defaults.
inline KnowledgeClass class_of(const std::string& predicate, const Json* spec) {
    KnowledgeClass out;
    out.predicate = predicate;
    if (!spec || spec->kind() != Json::Kind::Object) {
        out.transmissibility = transmissibility_for(out.classification);
        return out;
    }
    const Json* classification = spec->find("classification");
    if (classification && !classification->is_null())
        out.classification = classification->as_string();
    const Json* domain = spec->find("domain");
    if (domain && !domain->is_null()) out.domain = domain->as_string();
    for (const Json& one : spec->at("access").items()) out.access.push_back(one.as_string());
    for (const Json& one : spec->at("locality").items()) out.locality.push_back(one.as_string());
    const Json* declared = spec->find("transmissibility");
    out.transmissibility = (declared && !declared->is_null())
        ? declared->as_double()
        : transmissibility_for(out.classification);
    return out;
}

/// The declared class of a claim, or a neutral default.
inline KnowledgeClass class_for(const Json& world_predicates, const Proposition& claim) {
    return class_of(claim.predicate, world_predicates.find(claim.predicate));
}

/// Every group this character belongs to: networks, roles, factions.
///
/// One flat set on purpose. A claim circulating among engineers and one
/// circulating in the night shift are the same kind of restriction, and
/// separate namespaces would only mean writing the rule twice.
inline std::set<std::string> circles(const Agent& agent) {
    std::set<std::string> found;
    for (const std::string& network : agent.networks) found.insert(network);
    for (const Json& role : agent.roles) {
        if (role.kind() == Json::Kind::Object) {
            // Python's `if role.get("role")` is a truthiness test, so an empty
            // string does not become a circle.
            const Json* name = role.find("role");
            if (name && !name->is_null() && !name->py_str().empty())
                found.insert(name->py_str());
            const Json* context = role.find("context");
            if (context && !context->is_null() && !context->py_str().empty())
                found.insert(context->py_str());
        } else {
            found.insert(role.py_str());
        }
    }
    for (const Json& identity : agent.identities) {
        if (identity.kind() != Json::Kind::Object) continue;
        const Json* group = identity.find("group");
        if (group && !group->is_null() && !group->py_str().empty())
            found.insert(group->py_str());
    }
    return found;
}

inline std::set<std::string> shared_circles(const Agent& speaker, const Agent& listener) {
    std::set<std::string> mine = circles(speaker), theirs = circles(listener), both;
    std::set_intersection(mine.begin(), mine.end(), theirs.begin(), theirs.end(),
                          std::inserter(both, both.begin()));
    return both;
}

/// Characters who belong to more than one circle, and to which.
///
/// These are the people through whom anything crosses between groups. Worth
/// naming because a world where nothing crosses is as wrong as one where
/// everything does, and because "who could this have reached" is a question a
/// designer asks constantly.
inline OrderedMap<std::vector<std::string>> bridges(
        const OrderedMap<Agent>& agents) {
    OrderedMap<std::vector<std::string>> out;
    for (const auto& entry : agents) {
        std::set<std::string> mine = circles(entry.second);
        if (mine.size() > 1)
            out[entry.second.id] = std::vector<std::string>(mine.begin(), mine.end());
    }
    return out;
}

/// Would this speaker pass this claim to this listener? A multiplier in [0,1]
/// and a reason.
///
/// Not a yes/no, because every one of these is a tendency. Zero is reserved for
/// the two cases that really are categorical: a claim that does not circulate
/// here at all, and a listener outside a closed circle.
inline std::pair<double, std::pair<std::string, Json>> may_pass_on(
        const Json& world_predicates, const Proposition& claim,
        const Agent& speaker, const Agent& listener,
        const Json& place_id = Json()) {
    KnowledgeClass knowledge = class_for(world_predicates, claim);

    bool here_is_known = !place_id.is_null()
                      && !(place_id.kind() == Json::Kind::String && place_id.as_string().empty());
    if (!knowledge.locality.empty() && here_is_known
        && std::find(knowledge.locality.begin(), knowledge.locality.end(),
                     place_id.py_str()) == knowledge.locality.end()) {
        Json detail = Json::object();
        detail["predicate"] = knowledge.predicate;
        detail["here"] = place_id;
        Json where = Json::array();
        for (const std::string& one : knowledge.locality) where.push(Json(one));
        detail["circulates_in"] = where;
        return {0.0, {"topology.wrong_place", detail}};
    }

    if (!knowledge.access.empty()) {
        std::set<std::string> allowed(knowledge.access.begin(), knowledge.access.end());
        std::set<std::string> theirs = circles(listener);
        bool any = false;
        for (const std::string& one : allowed)
            if (theirs.count(one)) { any = true; break; }
        if (!any) {
            Json detail = Json::object();
            detail["predicate"] = knowledge.predicate;
            Json restricted = Json::array();
            for (const std::string& one : allowed) restricted.push(Json(one));
            detail["restricted_to"] = restricted;
            Json belongs = Json::array();
            for (const std::string& one : theirs) belongs.push(Json(one));
            detail["listener_belongs_to"] = belongs;
            return {0.0, {"topology.outside_the_circle", detail}};
        }
    }

    double weight = knowledge.transmissibility;
    Json detail = Json::object();
    detail["predicate"] = knowledge.predicate;
    detail["classification"] = knowledge.classification;
    detail["transmissibility"] = py_round(knowledge.transmissibility, 3);

    // Inside a shared circle, things move more readily than between strangers
    // who merely happen to be in the same room.
    std::set<std::string> common = shared_circles(speaker, listener);
    if (!common.empty()) {
        weight = std::min(1.0, weight * 1.35);
        Json shared = Json::array();
        for (const std::string& one : common) shared.push(Json(one));
        detail["shared_circles"] = shared;
    }

    // Shop talk reaches people who work the same trade, and bores everyone else.
    if (!knowledge.domain.empty() && knowledge.domain != "street") {
        double interest = listener.competence_in(knowledge.domain);
        weight *= 0.4 + 0.6 * std::min(1.0, interest * 2.0);
        detail["listener_competence"] = py_round(interest, 3);
    }

    return {std::max(0.0, std::min(1.0, weight)),
            {"topology.transmissibility", detail}};
}

// --------------------------------------------------------------- attention ---

/// How many new claims this character can properly take in per day.
///
/// `int(round(x))` in Python rounds HALF TO EVEN, so `round(6.5)` is 6.
/// `std::round` rounds half away from zero and would give 7. `std::nearbyint`
/// under the default rounding mode is the one that matches, and this is the
/// only place in the port where a bare `round()` on a float appears.
inline long long attention_budget(const Agent& agent) {
    double base = 6.0;
    double budget = std::nearbyint(base * (0.5 + agent.trait("curiosity")));
    return std::max(1LL, static_cast<long long>(budget));
}

/// Consume one unit. False means they are full for today.
///
/// Day-bounded rather than continuous, because attention recovers by sleeping
/// and because a per-day figure is something an author can reason about.
inline bool spend_attention(Agent& agent, long long world_time) {
    // Python's `//` FLOORS; C++ `/` truncates toward zero. They agree for a
    // positive world time and disagree for a negative one -- which a world
    // never has today, and which a port should not quietly depend on staying
    // true. One line, and the class of bug it prevents is not findable later.
    long long today = world_time >= 0 ? world_time / 1440
                                      : -(((-world_time) + 1439) / 1440);
    if (agent.attention_day != today) {
        agent.attention_day = today;
        agent.attention_spent = 0;
    }
    if (agent.attention_spent >= attention_budget(agent)) return false;
    agent.attention_spent += 1;
    return true;
}

}  // namespace usc
