// `usc/metahuman.py`. The bridge to a face.
//
// Unscripted owns WHY a character feels and says something; MetaHuman owns
// how the face looks. This maps an affect state -- PAD mood plus active OCC
// emotions -- onto ARKit-52 blendshape weights, a compact face summary, gaze
// aversion, prosody hints for a synthesiser, and a posture from the Frijda
// action tendencies.
//
// Everything here is pure and deterministic: identical affect in, identical
// packet out, so avatar output stays reproducible and replayable like the rest
// of the runtime. No rendering, no network, no dependency.
#pragma once

#include <algorithm>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "usc/affect.hpp"
#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/contracts.hpp"
#include "usc/pysum.hpp"
#include "usc/types.hpp"

namespace usc {

namespace metahuman {

/// ARKit-52 facial display templates per OCC emotion FAMILY, at full intensity.
/// Weights are symmetric -- left and right are expanded below -- and stay in
/// [0,1]. The names are the canonical Live Link Face identifiers.
inline const OrderedMap<OrderedMap<double>>& emotion_display() {
    static const OrderedMap<OrderedMap<double>>* table = [] {
        OrderedMap<double> smile;
        smile["mouthSmile"] = 0.85; smile["cheekSquint"] = 0.45;
        smile["eyeSquint"] = 0.30; smile["browInnerUp"] = 0.10;
        smile["mouthDimple"] = 0.30;
        OrderedMap<double> sadness;
        sadness["mouthFrown"] = 0.70; sadness["browInnerUp"] = 0.65;
        sadness["eyeSquint"] = 0.20; sadness["mouthShrugLower"] = 0.25;
        sadness["mouthStretch"] = 0.15;
        OrderedMap<double> fear;
        fear["eyeWide"] = 0.80; fear["browInnerUp"] = 0.85;
        fear["browOuterUp"] = 0.55; fear["jawOpen"] = 0.30;
        fear["mouthStretch"] = 0.45;
        OrderedMap<double> anger;
        anger["browDown"] = 0.85; anger["noseSneer"] = 0.45;
        anger["eyeSquint"] = 0.40; anger["mouthPress"] = 0.55;
        anger["jawForward"] = 0.30;
        OrderedMap<double> disgust;
        disgust["noseSneer"] = 0.80; disgust["mouthFrown"] = 0.35;
        disgust["browDown"] = 0.30; disgust["mouthShrugUpper"] = 0.40;

        auto* fresh = new OrderedMap<OrderedMap<double>>();
        // Positive valence -> the smile family.
        for (const char* one : {"joy", "gratification", "hope", "relief",
                                "admiration", "gratitude", "liking", "pride"})
            (*fresh)[one] = smile;
        // Loss and negative valence at low arousal -> sadness.
        for (const char* one : {"distress", "disappointment", "shame", "remorse"})
            (*fresh)[one] = sadness;
        (*fresh)["fear"] = fear;                       // high-arousal threat
        (*fresh)["anger"] = anger;                     // high-arousal antagonism
        (*fresh)["reproach"] = anger;
        (*fresh)["disliking"] = disgust;               // aversion
        return fresh;
    }();
    return *table;
}

/// Blendshape stems that exist as symmetric left/right pairs in ARKit.
inline const std::set<std::string>& symmetric_stems() {
    static const std::set<std::string>* stems = new std::set<std::string>{
        "browDown", "browOuterUp", "eyeWide", "eyeSquint", "eyeLookDown",
        "cheekSquint", "noseSneer", "mouthSmile", "mouthFrown", "mouthPress",
        "mouthStretch", "mouthDimple"};
    return *stems;
}

/// Strip the target suffix: `anger@player` becomes `anger`.
inline std::string base_emotion(const std::string& key) {
    std::size_t at = key.find('@');
    return at == std::string::npos ? key : key.substr(0, at);
}

namespace detail_ {

/// Add a stem weight, expanding a symmetric stem into its left/right keys.
inline void accumulate(std::map<std::string, double>& weights,
                       const std::string& stem, double value) {
    if (symmetric_stems().count(stem)) {
        weights[stem + "Left"] += value;
        weights[stem + "Right"] += value;
    } else {
        weights[stem] += value;
    }
}

}  // namespace detail_

/// ARKit-52 blendshape weights in [0,1].
///
/// Active discrete emotions drive the bulk of the expression; the slow PAD mood
/// supplies a resting expression that fills the remaining expressive budget, so
/// a neutral, calm character is a faint mood tint rather than a frozen mask.
inline Json affect_to_blendshapes(const AffectState& affect, int precision = 4) {
    // A std::map, because Python returns them SORTED and the ordering is part of
    // the packet an engine reads.
    std::map<std::string, double> weights;

    double total_emotion = 0.0;
    for (const auto& entry : affect.active_emotions) {
        double intensity = clamp01(entry.second);
        total_emotion += intensity;
        const OrderedMap<double>* templ = emotion_display().find(base_emotion(entry.first));
        if (!templ) continue;
        for (const auto& stem : *templ)
            detail_::accumulate(weights, stem.first, stem.second * intensity);
    }

    // Resting mood tint, scaled down as discrete emotion fills the budget.
    double headroom = clamp01(1.0 - total_emotion);
    double p = affect.mood.p, a = affect.mood.a, d = affect.mood.d;
    if (p > 0) {
        detail_::accumulate(weights, "mouthSmile", 0.30 * p * headroom);
        detail_::accumulate(weights, "cheekSquint", 0.15 * p * headroom);
    } else if (p < 0) {
        detail_::accumulate(weights, "mouthFrown", 0.30 * -p * headroom);
        detail_::accumulate(weights, "browInnerUp", 0.25 * -p * headroom);
    }
    if (a > 0)                       // alertness widens the eyes a touch
        detail_::accumulate(weights, "eyeWide", 0.20 * a * headroom);
    if (d < 0) {                     // low dominance: submissive brow, lowered gaze
        detail_::accumulate(weights, "browInnerUp", 0.20 * -d * headroom);
        detail_::accumulate(weights, "eyeLookDown", 0.25 * -d * headroom);
    }

    Json out = Json::object();
    for (const auto& entry : weights)
        if (entry.second > 0) out[entry.first] = py_round(clamp01(entry.second), precision);
    return out;
}

/// The strongest active emotion and its intensity, else a coarse resting label.
inline std::pair<std::string, double> dominant_emotion(const AffectState& affect) {
    std::string best_type = "neutral";
    double best_intensity = 0.0;
    for (const auto& entry : affect.active_emotions)
        if (entry.second > best_intensity) {
            best_type = base_emotion(entry.first);
            best_intensity = entry.second;
        }
    if (best_type == "neutral") {
        double p = affect.mood.p;
        if (p > 0.15) return {"content", py_round(std::min(1.0, p), 3)};
        if (p < -0.15) return {"downcast", py_round(std::min(1.0, -p), 3)};
    }
    return {best_type, py_round(best_intensity, 3)};
}

/// How strongly the character avoids eye contact, in [0,1].
inline double gaze_aversion(const AffectState& affect) {
    double shame = 0.0, fear = 0.0;
    for (const auto& entry : affect.active_emotions) {
        std::string base = base_emotion(entry.first);
        if (base == "shame" || base == "remorse") shame = std::max(shame, entry.second);
        if (base == "fear") fear = std::max(fear, entry.second);
    }
    double submissive = std::max(0.0, -affect.mood.d);
    return py_round(clamp01(0.9 * shame + 0.4 * fear + 0.35 * submissive), 4);
}

/// Prosody hints for a downstream voice provider.
inline Json prosody(const AffectState& affect) {
    double p = affect.mood.p, a = affect.mood.a;
    Json out = Json::object();
    // Arousal speeds and lifts the voice; valence adds a gentler lift.
    out["speech_rate"] = py_round(1.0 + 0.30 * a, 3);
    out["pitch_shift"] = py_round(0.18 * a + 0.10 * p, 3);
    out["loudness"] = py_round(clamp01(0.5 + 0.35 * a), 3);
    return out;
}

/// A coarse body posture from the strongest action-tendency class.
inline std::string posture(const OrderedMap<double>* action_tendencies) {
    static const std::vector<std::pair<std::string, std::vector<std::string>>> rules = {
        {"aggressive", {"attack", "threaten", "confront", "sanction", "assert",
                        "display"}},
        {"retreat", {"flee", "hide", "withdraw", "conceal", "evade", "avoid",
                     "seek_safety"}},
        {"approach", {"affiliate", "approach", "help", "share", "cooperate", "lead"}}};
    if (!action_tendencies || action_tendencies->empty()) return "neutral";
    std::string best_label = "neutral";
    double best_score = 0.0;
    for (const auto& rule : rules) {
        // `sum(max(0.0, ...))` -- and `sum` compensates, which cannot bite on at
        // most seven values all in [0,1].
        PySum score;
        for (const std::string& one : rule.second)
            score.add(std::max(0.0, action_tendencies->get(one, 0.0)));
        if (score.value() > best_score) {
            best_label = rule.first;
            best_score = score.value();
        }
    }
    return best_score > 0.15 ? best_label : "neutral";
}

/// The full face state for one character at the current instant.
inline Json affect_to_face(const AffectState& affect,
                           const OrderedMap<double>* action_tendencies = nullptr,
                           const Json& gaze_target = Json()) {
    auto dominant = dominant_emotion(affect);
    double aversion = gaze_aversion(affect);

    Json active = Json::object();
    for (const auto& entry : affect.active_emotions)
        active[base_emotion(entry.first)] = py_round(entry.second, 3);

    Json emotion = Json::object();
    emotion["dominant"] = dominant.first;
    emotion["intensity"] = dominant.second;
    emotion["valence"] = py_round(affect.mood.p, 4);
    emotion["arousal"] = py_round(affect.mood.a, 4);
    emotion["dominance"] = py_round(affect.mood.d, 4);
    emotion["active"] = active;

    Json gaze = Json::object();
    gaze["target"] = gaze_target;
    gaze["aversion"] = aversion;
    gaze["make_contact"] = aversion < 0.35;

    Json out = Json::object();
    out["emotion"] = emotion;
    out["blendshapes"] = affect_to_blendshapes(affect);
    out["gaze"] = gaze;
    out["prosody"] = prosody(affect);
    out["posture"] = posture(action_tendencies);
    return out;
}

/// One JSON object an engine plugin needs per turn: what to say, how it feels,
/// and how to voice it.
///
/// Also what the line COMMITTED to and what it did to the world. An engine that
/// only receives text can render a talking face; with this it can show a journal
/// entry, mark a claim as heard by a bystander, or put a tell on a character who
/// just lied.
inline Json build_avatar_packet(const DialogueResponse& response,
                                const AffectState& affect,
                                const OrderedMap<double>* action_tendencies = nullptr,
                                const Json& gaze_target = Json()) {
    Json out = affect_to_face(affect, action_tendencies, gaze_target);

    Json spoken = Json::array();
    std::string honesty = "honest";
    for (const Json& reason : response.reasons) {
        const std::vector<Json>& parts = reason.items();
        if (parts.size() < 3) continue;
        const Json& detail = parts[2];
        if (detail.kind() == Json::Kind::Object) {
            const Json* said = detail.find("spoken");
            if (said && said->kind() == Json::Kind::Array)
                for (const Json& utterance : said->items()) {
                    Json row = Json::object();
                    row["proposition"] = utterance.get("proposition");
                    row["text"] = utterance.get("rendered");
                    row["certainty"] = utterance.get("certainty");
                    row["honesty"] = utterance.get("honesty");
                    const Json* heard = utterance.find("heard_by");
                    Json who = Json::array();
                    if (heard) for (const Json& one : heard->items()) who.push(one);
                    row["heard_by"] = who;
                    spoken.push(row);
                    const Json* how = utterance.find("honesty");
                    if (how && !how->is_null() && how->py_str() != "honest")
                        honesty = how->py_str();
                }
        }
    }
    // A lie is what was SAID, never what was planned: a cover story replaced by
    // a deflection asserted nothing and must not come back labelled a lie.

    out["speaker_id"] = response.speaker_id;
    out["text"] = response.text;
    out["act"] = response.act;
    out["verdict"] = response.verdict;
    out["utility"] = response.utility;
    out["style"] = response.style;
    Json reasons = Json::array();
    for (const Json& one : response.reasons) reasons.push(one);
    out["reasons"] = reasons;
    /// Whether this line was true to the speaker's own beliefs. A game may use
    /// it for a tell, for a detective mechanic, or not at all -- but it must not
    /// be INFERRED from the text, which is exactly the point.
    out["honesty"] = honesty;
    /// The propositions this line actually asserted, and who overheard it.
    out["asserted"] = spoken;
    return out;
}

}  // namespace metahuman

}  // namespace usc
