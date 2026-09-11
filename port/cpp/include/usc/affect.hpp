// `usc/affect.py`. ALMA: personality sets the PAD baseline, OCC appraisal
// produces discrete emotions, emotions push the PAD vector, mood is the slow
// integral of it, emotions decay fast.
//
// Two things here are order-dependent in a way that is easy to miss, and both
// are preserved rather than tidied:
//
//   - `appraise` merges duplicate emotions into a dict and returns
//     `list(merged.items())`. The order is first-appearance, and it decides the
//     order impulses are added in -- which is floating-point addition, and not
//     associative. Sorting the emotions would change the mood by a bit.
//   - `active_emotions` is walked when decaying and when aggregating action
//     tendencies. Same reason.
//
// Emotion keys carry their target: "anger@player" is not "anger@police", and a
// character angry at one person is not thereby angry at the room.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/types.hpp"
#include "usc/knob.hpp"

namespace usc {

/// Emotion to PAD impulse direction (Mehrabian octants).
inline const OrderedMap<Vec3>& emotion_pad() {
    static const OrderedMap<Vec3>* table = [] {
        auto* fresh = new OrderedMap<Vec3>();
        (*fresh)["joy"]            = {1.0, 0.3, 0.3};
        (*fresh)["gratification"]  = {1.0, 0.3, 0.3};
        (*fresh)["hope"]           = {1.0, 0.2, 0.1};
        (*fresh)["relief"]         = {1.0, 0.2, 0.1};
        (*fresh)["pride"]          = {1.0, 0.4, 0.6};
        (*fresh)["admiration"]     = {1.0, 0.2, -0.1};
        (*fresh)["gratitude"]      = {1.0, 0.2, -0.1};
        (*fresh)["liking"]         = {1.0, 0.2, -0.1};
        (*fresh)["distress"]       = {-1.0, -0.2, -0.4};
        (*fresh)["disappointment"] = {-1.0, -0.2, -0.4};
        (*fresh)["shame"]          = {-1.0, -0.1, -0.6};
        (*fresh)["remorse"]        = {-1.0, -0.1, -0.6};
        (*fresh)["fear"]           = {-1.0, 0.6, -0.7};
        (*fresh)["anger"]          = {-1.0, 0.6, 0.5};
        (*fresh)["reproach"]       = {-1.0, 0.6, 0.5};
        (*fresh)["disliking"]      = {-0.6, 0.1, 0.1};
        return fresh;
    }();
    return *table;
}

/// Emotion to action-class bias (Frijda).
inline const OrderedMap<OrderedMap<double>>& action_tendency_table() {
    static const OrderedMap<OrderedMap<double>>* table = [] {
        auto* fresh = new OrderedMap<OrderedMap<double>>();
        auto add = [&](const char* emotion,
                       std::initializer_list<std::pair<const char*, double>> rows) {
            OrderedMap<double>& row = (*fresh)[emotion];
            for (const auto& entry : rows) row[entry.first] = entry.second;
        };
        add("fear",      {{"flee", 1.0}, {"hide", 0.8}, {"comply", 0.6},
                          {"seek_safety", 0.8}, {"approach", -0.7}, {"attack", -0.8},
                          {"evade", 0.6}});
        add("anger",     {{"attack", 1.0}, {"threaten", 0.9}, {"confront", 0.8},
                          {"comply", -0.6}, {"affiliate", -0.7}});
        add("joy",       {{"affiliate", 0.9}, {"help", 0.7}, {"share", 0.7},
                          {"cooperate", 0.8}});
        add("gratitude", {{"help", 0.9}, {"affiliate", 0.7}, {"cooperate", 0.6}});
        add("distress",  {{"withdraw", 0.8}, {"wait", 0.5}, {"initiate", -0.6}});
        add("pride",     {{"assert", 0.8}, {"display", 0.7}, {"lead", 0.6}});
        add("shame",     {{"withdraw", 0.8}, {"conceal", 0.9}, {"repair_face", 0.7},
                          {"evade", 0.5}});
        add("liking",    {{"approach", 0.8}, {"help", 0.6}});
        add("disliking", {{"avoid", 0.7}, {"sanction", 0.6}});
        add("reproach",  {{"sanction", 0.7}, {"avoid", 0.5}});
        return fresh;
    }();
    return *table;
}

struct AffectState {
    Vec3 mood;
    Vec3 baseline;
    OrderedMap<double> active_emotions;   // "anger@player" -> intensity

    Json as_json() const {
        Json out = Json::object();
        out["mood"] = mood.as_json();
        out["baseline"] = baseline.as_json();
        Json emotions = Json::object();
        for (const auto& entry : active_emotions)
            emotions.fields()[entry.first] = Json(entry.second);
        out["active_emotions"] = emotions;
        return out;
    }

    static AffectState from_json(const Json& doc) {
        AffectState out;
        out.mood = Vec3::from_json(doc.at("mood"));
        out.baseline = Vec3::from_json(doc.at("baseline"));
        for (const auto& entry : doc.at("active_emotions").fields())
            out.active_emotions[entry.first] = entry.second.as_double();
        return out;
    }
};

/// Mehrabian/ALMA linear map. Traits arrive in [0,1] and are converted to
/// [-1,1] first.
inline Vec3 pad_baseline_from_big_five(const OrderedMap<double>& traits) {
    auto trait = [&](const char* name) { return traits.get(name, 0.5); };
    double openness          = 2 * trait("openness") - 1;
    double conscientiousness = 2 * trait("conscientiousness") - 1;
    double extraversion      = 2 * trait("extraversion") - 1;
    double agreeableness     = 2 * trait("agreeableness") - 1;
    double stability         = 2 * trait("emotional_stability") - 1;
    double pleasure = 0.21 * extraversion + 0.59 * agreeableness + 0.19 * stability;
    // Instability raises arousal; S is negated neuroticism, hence the -(-S).
    double arousal  = 0.15 * openness + 0.30 * agreeableness - 0.57 * (-stability);
    double dominance = 0.25 * openness + 0.17 * conscientiousness
                     + 0.60 * extraversion - 0.32 * agreeableness;
    return {clamp_signed(pleasure), clamp_signed(arousal), clamp_signed(dominance)};
}

/// One reason-trace row, matching `belief.hpp`'s.
using AffectReason = Reason;

class AffectEngine {
public:
    struct Params {
        double k_impulse = 0.6;
        double tau_mood = 240.0;
        double tau_emotion = 30.0;
        double epsilon = 0.05;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("k_impulse", &Params::k_impulse),
            knob("tau_mood", &Params::tau_mood),
            knob("tau_emotion", &Params::tau_emotion),
            knob("epsilon", &Params::epsilon),
        };
        return table;
    }

    AffectEngine() = default;
    explicit AffectEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    /// The OCC subset. Returns (emotion, intensity) in first-appearance order.
    std::vector<std::pair<std::string, double>> appraise(const Json& appraisal) const {
        std::vector<std::pair<std::string, double>> out;

        const Json* desirability = appraisal.find("desirability");
        bool has_desirability = desirability && !desirability->is_null();
        double des = has_desirability ? desirability->as_double() : 0.0;

        const Json* agency_field = appraisal.find("agency");
        std::string agency = (agency_field && !agency_field->is_null())
                           ? agency_field->as_string() : "none";

        const Json* praise_field = appraisal.find("praiseworthiness");
        bool has_praise = praise_field && !praise_field->is_null();
        double praise = has_praise ? praise_field->as_double() : 0.0;

        const Json* expect_field = appraisal.find("expectedness");
        double expect = (expect_field && !expect_field->is_null())
                      ? expect_field->as_double() : 0.5;
        double uncertainty = 1.0 - expect;

        const Json* prospect_field = appraisal.find("prospect");
        bool has_prospect = prospect_field && !prospect_field->is_null();
        std::string prospect = has_prospect ? prospect_field->as_string() : "";

        const Json* attraction_field = appraisal.find("attraction");
        bool has_attraction = attraction_field && !attraction_field->is_null();
        double attraction = has_attraction ? attraction_field->as_double() : 0.0;

        // `if appraisal.get("prior_fear")` is a TRUTHINESS test, not a presence
        // test: a prior fear of exactly 0.0 fires nothing. Ported as written.
        const Json* prior_fear = appraisal.find("prior_fear");
        const Json* prior_hope = appraisal.find("prior_hope");
        // THE PROSPECT PAIR, IN THE DIRECTION OCC ACTUALLY STATES IT. Relief
        // follows a feared event NOT happening; one that does happen is
        // fears-confirmed, a distress-family emotion. This was the wrong way
        // round, so a character whose worst expectation came true cheered up.
        // The four cases reuse the existing vocabulary rather than adding names
        // nothing downstream can render.
        if (has_prospect && prospect == "disconfirmed" && truthy(prior_fear))
            out.emplace_back("relief", prior_fear->as_double());
        if (has_prospect && prospect == "confirmed" && truthy(prior_fear))
            out.emplace_back("distress", prior_fear->as_double());     // fears-confirmed
        if (has_prospect && prospect == "disconfirmed" && truthy(prior_hope))
            out.emplace_back("disappointment", prior_hope->as_double());
        if (has_prospect && prospect == "confirmed" && truthy(prior_hope))
            out.emplace_back("joy", prior_hope->as_double());          // satisfaction

        if (has_desirability) {
            if (!has_prospect && uncertainty > 0.3 && des > 0)
                out.emplace_back("hope", des * uncertainty);
            if (!has_prospect && uncertainty > 0.3 && des < 0)
                out.emplace_back("fear", -des * uncertainty);
            if (des > 0)      out.emplace_back("joy", des);
            else if (des < 0) out.emplace_back("distress", -des);
        }

        if (has_praise && agency == "self")
            out.emplace_back(praise > 0 ? "pride" : "shame", std::fabs(praise));
        if (has_praise && agency == "other")
            out.emplace_back(praise > 0 ? "admiration" : "reproach", std::fabs(praise));

        if (has_desirability && has_praise && agency == "other") {
            if (des > 0 && praise > 0)
                out.emplace_back("gratitude", std::min(1.0, des * praise + 0.2));
            if (des < 0 && praise < 0)
                out.emplace_back("anger", std::min(1.0, (-des) * (-praise) + 0.2));
        }

        if (has_attraction)
            out.emplace_back(attraction > 0 ? "liking" : "disliking", std::fabs(attraction));

        // Merge duplicates, keeping the strongest -- and the position of the
        // FIRST occurrence, because that decides the order impulses are summed.
        OrderedMap<double> merged;
        for (const auto& entry : out) {
            double* existing = merged.find(entry.first);
            double best = existing ? std::max(*existing, entry.second) : entry.second;
            merged[entry.first] = clamp01(best);
        }
        std::vector<std::pair<std::string, double>> result;
        for (const auto& entry : merged) result.push_back(entry);
        return result;
    }

    /// Appraise, fire impulses, decay what is active, relax mood toward baseline.
    std::vector<std::pair<std::string, double>> update(
            AffectState& state, const Json& appraisal, double dt,
            std::vector<AffectReason>* reasons = nullptr) const {
        const Json* target_field = appraisal.find("target");
        bool has_target = target_field && !target_field->is_null();
        std::string target = has_target ? target_field->as_string() : "";

        std::vector<std::pair<std::string, double>> fired = appraise(appraisal);
        Vec3 impulse;
        for (const auto& entry : fired) {
            std::string key = has_target ? entry.first + "@" + target : entry.first;
            double* existing = state.active_emotions.find(key);
            double best = existing ? std::max(*existing, entry.second) : entry.second;
            state.active_emotions[key] = clamp01(best);
            const Vec3* direction = emotion_pad().find(entry.first);
            Vec3 push = direction ? *direction : Vec3{};
            impulse = impulse.add(push.scale(entry.second * params_.k_impulse));
            if (reasons) {
                Json detail = Json::object();
                detail["emotion"] = entry.first;
                detail["target"] = has_target ? Json(target) : Json();
                reasons->push_back({"affect.emotion_fired", py_round(entry.second, 3), detail});
            }
        }

        OrderedMap<double> surviving;
        for (const auto& entry : state.active_emotions) {
            double value = entry.second * std::exp(-dt / params_.tau_emotion);
            if (value >= params_.epsilon) surviving[entry.first] = value;
        }
        state.active_emotions = surviving;

        // Exact exponential relaxation rather than a fixed step, so the result
        // does not depend on how the caller chopped up time.
        double homing = dt > 0 ? (1.0 - std::exp(-dt / params_.tau_mood)) : 0.0;
        Vec3 toward = state.baseline.add(state.mood.scale(-1)).scale(homing);
        Vec3 relaxed = state.mood.add(toward);
        // Soft saturation: an impulse pushes less the closer mood already is to
        // the rail, so one strong event cannot slam a character to +/-1 and
        // leave them there.
        Vec3 soft{impulse.p * (1.0 - std::fabs(relaxed.p)),
                  impulse.a * (1.0 - std::fabs(relaxed.a)),
                  impulse.d * (1.0 - std::fabs(relaxed.d))};
        state.mood = relaxed.add(soft).clamped();

        if (reasons && (impulse.p != 0.0 || impulse.a != 0.0 || impulse.d != 0.0)) {
            Json pad = Json::object();
            pad["valence"] = state.mood.p;
            pad["arousal"] = state.mood.a;
            pad["dominance"] = state.mood.d;
            Json detail = Json::object();
            detail["pad"] = pad;
            reasons->push_back({"affect.mood_shift", py_round(impulse.p, 3), detail});
        }
        return fired;
    }

    /// Periodic decay when nothing happened.
    std::vector<std::pair<std::string, double>> decay(
            AffectState& state, double dt,
            std::vector<AffectReason>* reasons = nullptr) const {
        return update(state, Json::object(), dt, reasons);
    }

    /// Aggregate action-class bias across every active emotion.
    OrderedMap<double> action_tendencies(const AffectState& state) const {
        OrderedMap<double> bias;
        for (const auto& entry : state.active_emotions) {
            std::string base = entry.first.substr(0, entry.first.find('@'));
            const OrderedMap<double>* row = action_tendency_table().find(base);
            if (!row) continue;
            for (const auto& weight : *row)
                bias[weight.first] += entry.second * weight.second;
        }
        OrderedMap<double> rounded;
        for (const auto& entry : bias)
            rounded[entry.first] = py_round(clamp_signed(entry.second), 3);
        return rounded;
    }

    /// Emotions directed at one person, by base type.
    static OrderedMap<double> emotions_toward(const AffectState& state,
                                              const std::string& target) {
        OrderedMap<double> out;
        const std::string suffix = "@" + target;
        for (const auto& entry : state.active_emotions) {
            if (entry.first.size() < suffix.size()) continue;
            if (entry.first.compare(entry.first.size() - suffix.size(),
                                    suffix.size(), suffix) != 0) continue;
            out[entry.first.substr(0, entry.first.find('@'))] = entry.second;
        }
        return out;
    }

    double stress(const AffectState& state) const {
        return clamp01(state.mood.a * std::max(0.0, -state.mood.p));
    }

private:
    /// Python truthiness for a JSON value, which is what `if d.get(k):` asks.
    static bool truthy(const Json* value) {
        if (!value || value->is_null()) return false;
        if (value->kind() == Json::Kind::Bool) return value->as_bool();
        if (value->is_number()) return value->as_double() != 0.0;
        if (value->kind() == Json::Kind::String) return !value->as_string().empty();
        return true;
    }

    Params params_;
};

}  // namespace usc
