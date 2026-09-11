// `usc/dialogue.py`. Turning a chosen action into a plan the text layer renders.
//
// Speech act, topic, the facts the character has been COMMITTED to, the topics
// to steer away from -- and never the content of a secret, only its avoid-label,
// so a secret cannot leak by sitting in a prompt.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <vector>

#include "usc/actions.hpp"
#include "usc/agent.hpp"
#include "usc/commitment.hpp"
#include "usc/content.hpp"
#include "usc/json.hpp"
#include "usc/sociolinguistics.hpp"

namespace usc {

struct ConversationState {
    std::string conv_id;
    std::vector<std::string> participants;
    Json active_topic;
    std::set<std::string> common_ground;     // proposition keys both know
    std::vector<std::string> open_questions;
    std::set<std::string> resolved;
    long long turn_count = 0;
    std::vector<std::string> last_acts;
    OrderedMap<long long> discussed_topics;  // topic -> times asked
    long long last_world_time = 0;           // for resume across save/load
    std::vector<std::string> recent_lines;   // anti-repeat

    /// Record that a topic was discussed; return how many times now (>=1).
    long long note_topic(const std::string& topic, long long world_time) {
        discussed_topics[topic] += 1;
        last_world_time = world_time;
        return discussed_topics.get(topic, 0);
    }

    Json as_json() const {
        Json out = Json::object();
        out["conv_id"] = conv_id;
        Json who = Json::array();
        for (const std::string& one : participants) who.push(Json(one));
        out["participants"] = who;
        out["active_topic"] = active_topic;
        out["turn_count"] = turn_count;
        Json acts = Json::array();
        for (const std::string& one : last_acts) acts.push(Json(one));
        out["last_acts"] = acts;
        Json topics = Json::object();
        for (const auto& entry : discussed_topics)
            topics.fields()[entry.first] = Json(entry.second);
        out["discussed_topics"] = topics;
        out["last_world_time"] = last_world_time;
        Json lines = Json::array();
        for (const std::string& one : recent_lines) lines.push(Json(one));
        out["recent_lines"] = lines;
        return out;
    }

    static ConversationState from_json(const Json& doc) {
        ConversationState out;
        out.conv_id = doc.at("conv_id").as_string();
        for (const Json& one : doc.at("participants").items())
            out.participants.push_back(one.py_str());
        out.active_topic = doc.get("active_topic");
        const Json* turns = doc.find("turn_count");
        out.turn_count = turns ? turns->as_int() : 0;
        for (const Json& one : doc.at("last_acts").items()) out.last_acts.push_back(one.py_str());
        for (const auto& entry : doc.at("discussed_topics").fields())
            out.discussed_topics[entry.first] = entry.second.as_int();
        const Json* when = doc.find("last_world_time");
        out.last_world_time = when ? when->as_int() : 0;
        for (const Json& one : doc.at("recent_lines").items())
            out.recent_lines.push_back(one.py_str());
        return out;
    }
};

struct DialoguePlan {
    std::string speaker;
    std::string addressee;
    std::string dialogue_act;
    std::string goal;
    /// What the runtime has COMMITTED this character to saying. The text layer
    /// renders these and selects nothing. Empty means "assert no fact".
    std::vector<SemanticMove> moves;
    /// Rendered form of the committed propositions. A plain list because the
    /// validator licenses specifics against it and persistence stores it; it is
    /// always exactly the commitment, never a menu to choose from.
    std::vector<std::string> allowed_facts;
    /// Topic LABELS to steer away from -- never the secret content.
    std::vector<std::string> avoid_topics;
    std::string stance = "asserted";
    Json style = Json::object();
    std::string fallback_template_id = "deflect";
    long long max_length = 30;
    /// Authored register variants for THIS answer. When empty the realizer falls
    /// back to a stance template and asserts nothing factual.
    Json phrasing = Json::object();
    /// Stable id for this generation, so a line that misses the frame budget can
    /// be matched back to the turn it belongs to when it arrives late.
    std::string request_id;

    /// Adopt a commitment: the moves become the plan's only factual content.
    DialoguePlan& commit(const Commitment& commitment) {
        moves = commitment.moves;
        allowed_facts = commitment.rendered_facts();
        // `if commitment.forbidden:` -- an empty list leaves whatever the plan
        // already had. UNOBSERVABLE from `plan()`, which passes the same avoid
        // labels into both branches, so the commitment's `forbidden` is either
        // that same list or empty when the list itself is. Kept because
        // `commit()` is public and a caller with a commitment from elsewhere
        // would see the difference immediately.
        if (!commitment.forbidden.empty()) avoid_topics = commitment.forbidden;
        return *this;
    }

    std::vector<Proposition> committed_propositions() const {
        std::vector<Proposition> out;
        for (const SemanticMove& move : moves)
            if (move.proposition) out.push_back(*move.proposition);
        return out;
    }

    Json as_json() const {
        Json out = Json::object();
        out["speaker"] = speaker;
        out["addressee"] = addressee;
        out["dialogue_act"] = dialogue_act;
        out["goal"] = goal;
        Json rows = Json::array();
        for (const SemanticMove& move : moves) rows.push(move.as_json());
        out["moves"] = rows;
        Json facts = Json::array();
        for (const std::string& one : allowed_facts) facts.push(Json(one));
        out["allowed_facts"] = facts;
        Json avoid = Json::array();
        for (const std::string& one : avoid_topics) avoid.push(Json(one));
        out["avoid_topics"] = avoid;
        out["stance"] = stance;
        out["style"] = style;
        out["fallback_template_id"] = fallback_template_id;
        out["max_length"] = max_length;
        out["phrasing"] = phrasing;
        out["request_id"] = request_id;
        return out;
    }
};

class DialoguePlanner {
public:
    static constexpr const char* MODULE_ID = "dialogue_planner";

    /// Minimum belief confidence to state something as fact.
    static constexpr double C_ASSERT = 0.6;

    /// Acts that state something about the world. Everything else -- evading,
    /// deflecting, greeting, threatening -- commits to NO fact, and a plan that
    /// commits to no fact hands the text layer nothing to choose from.
    static bool asserts(const std::string& act) {
        return act == "inform" || act == "answer" || act == "confide" || act == "warn";
    }

    DialoguePlan plan(const Agent& agent, ConversationState& conv,
                      const ActionCandidate& chosen, const std::string& addressee,
                      const StyleVector& style, const std::string& goal,
                      const std::string& world_seed = "",
                      long long world_time = 0) const {
        // `chosen_action.action.dialogue_act or "inform"` -- truthiness, so an
        // action that names no act still plans one.
        std::string act = "inform";
        if (!chosen.action.dialogue_act.is_null()
            && !chosen.action.dialogue_act.py_str().empty())
            act = chosen.action.dialogue_act.py_str();

        std::vector<Secret> secrets;
        for (const Json& row : agent.secrets) secrets.push_back(Secret::from_json(row));
        std::vector<std::string> avoid = avoid_labels(secrets);

        DialoguePlan plan;
        plan.speaker = agent.id;
        plan.addressee = addressee;
        plan.dialogue_act = act;
        plan.goal = goal;
        plan.avoid_topics = avoid;
        plan.stance = (act == "evade") ? "deceptive" : "asserted";
        plan.style = style.as_json();

        // THE RUNTIME DECIDES WHAT IS SAID. This used to build a list of every
        // belief above threshold and hand it over, which left the choice of what
        // a character actually discloses to whatever rendered the text.
        if (asserts(act)) {
            std::set<std::string> protect = protected_keys(secrets);
            std::vector<Candidate> candidates;
            for (const auto& entry : agent.beliefs) {
                const Belief& belief = entry.second;
                if (belief.expected_prob() < C_ASSERT) continue;
                if (protect.count(belief.proposition.core_key())
                    || protect.count(belief.proposition.str())) continue;
                candidates.push_back({belief.proposition, belief.expected_prob(), 1.0, true});
            }
            // Five parts, and `select` appends "commitment" and "pickN" then
            // truncates to six -- so "pickN" IS DROPPED and every pick in one
            // turn draws the same seed. Reproduced because it is what happens,
            // not because it is what anybody would design.
            std::vector<std::string> seed_parts = {
                world_seed, agent.id, std::to_string(conv.turn_count),
                std::to_string(world_time), "deliberate"};
            plan.commit(select(candidates, "assert", 1, seed_parts, avoid));
        } else {
            Commitment nothing;
            nothing.forbidden = avoid;
            plan.commit(nothing);
        }

        conv.turn_count += 1;
        conv.last_acts.push_back(act);
        return plan;
    }

    /// Each turn must do something new: three of the same act in a row, and a
    /// fourth of the same, is a loop rather than a conversation.
    bool anti_loop_ok(const ConversationState& conv, const std::string& act) const {
        if (conv.last_acts.size() < 3) return true;
        const auto tail = conv.last_acts.end();
        bool all_same = *(tail - 1) == *(tail - 2) && *(tail - 2) == *(tail - 3);
        return !(all_same && act == *(tail - 1));
    }
};

}  // namespace usc
