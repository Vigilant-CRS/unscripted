// `usc/sdk.py`. The surface a game binds to.
//
// Everything below the SDK is a mechanism; this is where the mechanisms are
// wired to a player. One turn of text goes in, a parsed command comes out, the
// world moves, and a character answers -- and every one of those steps is a
// module that has already been ported and held to Python on its own.
//
// WHAT IS NOT HERE, and why:
//
//   - the STORE. Every `if self.store:` in the reference is a write to SQLite,
//     never a read that changes an outcome. A console's save system is the
//     host's; the snapshot layer hands it one blob.
//   - the VOICE and AVATAR paths. A synthesiser and a face rig are engine-side
//     by definition, and the packets they take are already produced by modules
//     the host can call directly.
//   - PACK VALIDATION. A shipped game loads a pack and never validates one.
#pragma once

#include <algorithm>
#include <set>
#include <string>
#include <vector>

#include "usc/commitment.hpp"
#include "usc/content.hpp"
#include "usc/contracts.hpp"
#include "usc/grounding.hpp"
#include "usc/inspect.hpp"
#include "usc/parser.hpp"
#include "usc/revision.hpp"
#include "usc/runtime.hpp"
#include "usc/tuning_bind.hpp"
#include "usc/snapshot.hpp"
#include "usc/world.hpp"

namespace usc {

class UnscriptedRuntime {
public:
    /// How many bystanders, at most, overhear an exchange.
    static constexpr std::size_t EARSHOT = 3;

    RuntimeConfig config;
    World& world;
    Runtime core;
    RuleBasedParserProvider parser;

    UnscriptedRuntime(RuntimeConfig settings, World& setting)
        : config(std::move(settings)), world(setting), core(setting) {
        core.population_lod = config.population_lod;
        core.climate.set_enabled(config.climate);
        core.pursuit.set_enabled(config.pursuit);
        core.pursuit.set_media(config.media);
        core.contagion.set_enabled(config.contagion);
        core.common_knowledge.set_enabled(config.common_knowledge);
        core.notes.set_enabled(config.notes);
        core.promises.set_enabled(config.promises);
        core.standing.set_enabled(config.standing);
        // HOW THIS WORLD WORKS IS CONTENT. Applied after every engine exists, so
        // a pack overrides a default rather than racing it, and recorded in the
        // trace -- a scene behaving oddly should not need somebody to diff a
        // JSON file against the source of the runtime. Same position in the
        // sequence as the reference, which matters: `pursuit.set_notes` below
        // reads a value this may have changed.
        std::vector<TuningReason> tuned = apply_tuning(core, setting.tuning);
        if (!tuned.empty()) core.last_traces["_tuning"] = tuned;
        // Notes follow the note layer, not a switch of their own: somebody who
        // can reach nobody writes it down only if writing exists here at all.
        core.pursuit.set_notes(core.notes.enabled());
        core.actions_out.enabled = config.action_bridge;
        core.actions_out.timeout_minutes = config.action_timeout_minutes;
        core.player_id = config.player_id;
        core.validator.canon_mode = config.canon_mode;
    }

    /// Everything `create()` does that is not reading the pack or opening a
    /// store: put the player in the world, put the cast where their DAY says
    /// they should be rather than where the character files happened to list
    /// them, and seed whatever the pack says people already believe.
    ///
    /// Separate from the constructor because a host that built its world some
    /// other way -- a save, a generator, a test -- still wants exactly this.
    void attach() {
        std::string start = config.player_start_location
            ? *config.player_start_location : world.player_start;
        if (start.empty())
            throw std::invalid_argument(
                "This world pack declares no places, so the player has nowhere to "
                "start. Set scenario.json: player_start, or the config's "
                "player_start_location.");
        if (!world.places.find(start))
            throw std::invalid_argument("Player start location '" + start
                                        + "' is not a place in this pack.");
        Agent* player = world.agents.find(config.player_id);
        if (!player) {
            Agent fresh;
            fresh.id = config.player_id;
            fresh.set_location(Json(start));
            fresh.big_five["agreeableness"] = 0.5;
            fresh.big_five["emotional_stability"] = 0.5;
            fresh.initialise_affect();
            world.agents[fresh.id] = fresh;
        } else {
            player->set_location(Json(start));
        }
        // The Runtime is constructed before the player exists -- Python builds
        // the world, adds the player, and only then constructs it. So the two
        // things the Runtime derives from the cast are rebuilt here: the routine
        // table, and the decay watermarks, without which the player is the one
        // character population LOD would never catch up.
        core.routines = OrderedMap<Routine>();
        for (const auto& entry : world.agents)
            core.routines[entry.first] = Routine::from_json(entry.second.routine);
        for (const auto& entry : world.agents)
            if (!core.last_decay().contains(entry.first))
                core.last_decay()[entry.first] = world.world_time;
        core.routine.seed(world, core.routines);
        if (config.load_initial_state) load_initial_state();
    }

    // ------------------------------------------------------------- the turn --

    ParsedCommand interpret_input(const std::string& text) const {
        const Agent* player = world.agents.find(config.player_id);
        return parser.parse(text, config.player_id,
                            player ? player->location().py_str() : std::string(),
                            world);
    }

    EventReceipt emit_event(const Event& event) {
        TraceMap traces = core.process_event(event);
        EventReceipt receipt;
        receipt.event_id = event.event_id;
        receipt.event_type = event.type;
        receipt.world_time = event.world_time;
        for (const auto& entry : traces) receipt.observed_by.push_back(entry.first);
        std::sort(receipt.observed_by.begin(), receipt.observed_by.end());
        return receipt;
    }

    /// Advance world time. Time is MONOTONIC: rewinding it would silently
    /// corrupt every memory activation, which is a function of elapsed time.
    void advance_time(long long minutes) {
        if (minutes < 0)
            throw std::invalid_argument(
                "World time is monotonic; cannot advance by "
                + std::to_string(minutes) + " minutes. Use a snapshot to rewind.");
        core.advance_time(minutes);
    }

    TurnResult submit_player_text(const std::string& text) {
        ParsedCommand parsed = interpret_input(text);
        Agent& player = *world.agents.find(config.player_id);

        auto answer = [&](const std::string& message) {
            TurnResult out;
            out.world_time = world.world_time;
            out.location_id = player.location().py_str();
            out.parsed = parsed;
            out.message = message;
            return out;
        };

        if (parsed.intent == "quit") {
            TurnResult out = answer("Session ended.");
            out.done = true;
            return out;
        }
        if (parsed.intent == "help") return answer(HELP_TEXT);
        if (parsed.intent == "noop") return answer("");
        if (parsed.intent == "unknown")
            return answer("I could not map that to a safe action. Try 'help'.");
        if (parsed.intent == "observe")
            return answer(describe_location(player.location().py_str()));
        if (parsed.intent == "move") return move_player(parsed);
        if (parsed.intent == "wear") return wear(parsed);
        if (parsed.intent == "wait") {
            advance_time(parsed.minutes);
            TurnResult out = answer(
                "Time advances by " + std::to_string(parsed.minutes) + " minutes.\n"
                + describe_location(player.location().py_str()));
            out.world_time = world.world_time;
            out.developer_trace = format_last_trace(core, "_director");
            return out;
        }
        if (parsed.intent == "listen_radio") return listen_radio(parsed);
        if (parsed.intent == "inspect") {
            std::string target = parsed.target_id.truthy() ? parsed.target_id.py_str()
                                                           : default_target();
            std::string trace = target.empty() ? inspect_world() : inspect_agent(target);
            TurnResult out = answer(trace);
            out.developer_trace = trace;
            return out;
        }

        std::string target = parsed.target_id.truthy() ? parsed.target_id.py_str()
                                                       : default_target();
        if (target.empty())
            return answer("No reachable NPC target is clear from that command.");
        parsed.target_id = target;

        static const std::set<std::string> reachable = {
            "ask", "say", "claim", "promise", "threaten", "accuse", "attack", "assist"};
        if (reachable.count(parsed.intent)) {
            const Agent* other = world.agents.find(target);
            if (other && other->location().py_str() != player.location().py_str())
                return answer(agent_name(target) + " is not reachable from "
                              + world.place_label(player.location().py_str())
                              + ". Move closer or emit an engine event.");
        }

        static const std::set<std::string> social = {
            "ask", "say", "claim", "promise", "threaten", "accuse", "assist"};
        if (social.count(parsed.intent)) {
            TurnResult out;
            out.world_time = world.world_time;
            out.location_id = player.location().py_str();
            out.parsed = parsed;
            out.receipts = handle_social_input(parsed);
            DialogueResponse response = respond(
                target, parsed.topic.truthy() ? parsed.topic.py_str() : std::string());
            out.npc_response = response;
            out.developer_trace = inspect_agent(target);
            out.message = agent_name(target) + ": \"" + response.text + "\"";
            out.world_time = world.world_time;
            return out;
        }

        if (parsed.intent == "attack") return attack(parsed);
        return answer("The command parsed, but no runtime handler is registered "
                      "for it.");
    }

    /// What a character says, when the player has addressed them.
    DialogueResponse respond(const std::string& agent_id,
                             const std::string& topic = "",
                             const std::string& interlocutor_id = "") {
        std::string interlocutor = interlocutor_id.empty() ? config.player_id
                                                           : interlocutor_id;
        Agent& agent = *world.agents.find(agent_id);
        core.catch_up(agent);   // LOD: decay current before speaking

        std::vector<Reason> gate_reasons;
        std::optional<DialogueResponse> direct =
            direct_answer(agent_id, interlocutor, topic, &gate_reasons);
        if (direct) return *direct;

        // Falling through to deliberation must not erase WHY the direct answer
        // was withheld: `say()` overwrites the agent's trace, so a secret gate
        // would have produced an unexplained deflection -- the one line a studio
        // most needs explained.
        Runtime::Spoken raw = core.say(agent_id, interlocutor);
        std::vector<Reason> reasons = gate_reasons;
        for (const Reason& reason : raw.reasons) reasons.push_back(reason);
        core.last_traces[agent_id] = reasons;

        DialogueResponse out;
        out.speaker_id = agent_id;
        out.text = raw.text;
        out.act = raw.act;
        out.verdict = raw.verdict;
        out.utility = raw.utility;
        for (const Reason& one : reasons) out.reasons.push_back(one.as_json());
        out.style = raw.style;
        return out;
    }

    void load_initial_state() {
        if (initial_state_loaded_) return;
        initial_state_loaded_ = true;
        for (const Json& belief : world.initial_beliefs.items()) {
            Proposition prop = Proposition::from_json(belief.at("proposition"));
            const Json* summary = belief.find("summary");
            const Json* trust = belief.find("trust");
            const Json* competence = belief.find("competence");
            const Json* importance = belief.find("importance");
            seed_belief(belief.at("agent").as_string(), prop,
                        (summary && summary->truthy()) ? summary->py_str() : prop.str(),
                        belief.at("origin_event"),
                        trust ? trust->as_double() : 0.75,
                        competence ? competence->as_double() : 0.75,
                        importance ? importance->as_double() : 0.6);
        }
    }

    // ------------------------------------------------------------ read model --

    std::string agent_name(const std::string& agent_id) const {
        const Agent* agent = world.agents.find(agent_id);
        if (!agent) return agent_id;
        return agent->public_name.truthy() ? agent->public_name.py_str() : agent_id;
    }

    std::string describe_location(const std::string& location_id) const {
        const Json* place = world.places.find(location_id);
        std::vector<std::string> lines = {world.place_label(location_id)};
        auto level = [&place](const char* key) {
            const Json* found = place ? place->find(key) : nullptr;
            return format_fixed(found ? found->as_double() : 0.0, 2);
        };
        lines.push_back("noise=" + level("noise_level")
                        + " surveillance=" + level("surveillance_level")
                        + " privacy=" + level("privacy_level"));
        std::vector<std::string> here;
        for (const auto& entry : world.agents)
            if (entry.second.location().py_str() == location_id
                && entry.first != config.player_id)
                here.push_back(agent_name(entry.first));
        lines.push_back(here.empty() ? "NPCs: none visible"
                                     : "NPCs: " + joined(here, ", "));
        std::vector<std::string> exits;
        for (const std::string& one : world.exits_from(location_id))
            exits.push_back(world.place_label(one));
        lines.push_back("Exits: " + joined(exits, ", "));
        return joined(lines, "\n");
    }

    std::string inspect_agent(const std::string& agent_id) {
        const Agent* agent = world.agents.find(agent_id);
        if (!agent) return "no such character: " + agent_id;
        return format_beliefs(*agent) + "\n" + format_memory(*agent, world.world_time)
             + "\n" + format_affect(*agent) + "\n" + format_last_trace(core, agent_id);
    }

    std::string inspect_world() const {
        std::vector<std::string> lines = {
            "  world t=" + std::to_string(world.world_time)
            + " seed=" + world.global_seed};
        for (const auto& entry : world.agents)
            lines.push_back("    " + entry.first + " @ "
                            + entry.second.location().py_str());
        return joined(lines, "\n");
    }

    Json export_state() const { return usc::export_state(world, core); }
    Json inspect_state(const Json& blob) const { return usc::inspect_state(blob, world); }
    ImportResult import_state(const Json& blob) {
        return usc::import_state(blob, world, core);
    }

    /// Expose a source: recompute everything they convinced anyone of.
    std::vector<Reason> discredit(const std::string& source_id, double factor = 0.25,
                                  const std::string& reason = "exposed",
                                  const std::string& predicate = "") {
        Revision revision = usc::discredit(world, source_id, factor, reason, predicate);
        core.last_traces["_revision"] = revision.reasons;
        return revision.reasons;
    }

private:
    static std::string joined(const std::vector<std::string>& parts,
                              const std::string& separator) {
        std::string out;
        for (std::size_t i = 0; i < parts.size(); ++i) {
            if (i) out += separator;
            out += parts[i];
        }
        return out;
    }

    /// Who the player means when they address nobody in particular.
    ///
    /// The scene's authored focus agents, then the sole NPC present, then the
    /// first by id. The focus order used to be three hardcoded character ids
    /// from the reference pack.
    std::string default_target() const {
        const Agent* player = world.agents.find(config.player_id);
        if (!player) return "";
        std::set<std::string> nearby;
        for (const auto& entry : world.agents)
            if (entry.first != config.player_id
                && entry.second.location().py_str() == player->location().py_str())
                nearby.insert(entry.first);
        for (const std::string& preferred : world.focus_agents)
            if (nearby.count(preferred)) return preferred;
        return nearby.empty() ? std::string() : *nearby.begin();
    }

    TurnResult make_result(const ParsedCommand& parsed, const std::string& message) {
        const Agent* player = world.agents.find(config.player_id);
        TurnResult out;
        out.world_time = world.world_time;
        out.location_id = player ? player->location().py_str() : std::string();
        out.parsed = parsed;
        out.message = message;
        return out;
    }

    TurnResult move_player(const ParsedCommand& parsed) {
        Agent& player = *world.agents.find(config.player_id);
        std::vector<std::string> exits = world.exits_from(player.location().py_str());
        std::string to = parsed.location_id.py_str();
        if (std::find(exits.begin(), exits.end(), to) == exits.end())
            return make_result(parsed, "You cannot move directly to "
                                       + world.place_label(to) + ".");
        player.set_location(parsed.location_id);
        Event ev;
        ev.event_id = world.new_event_id();
        ev.world_time = world.world_time;
        ev.type = "move";
        ev.actor = config.player_id;
        ev.location = player.location();
        Json payload = Json::object();
        payload["summary"] = "player arrives at " + player.location().py_str();
        ev.payload = payload;
        EventReceipt receipt = emit_event(ev);
        TurnResult out = make_result(parsed, describe_location(player.location().py_str()));
        out.receipts.push_back(receipt);
        return out;
    }

    TurnResult wear(const ParsedCommand& parsed) {
        Agent& player = *world.agents.find(config.player_id);
        const Json* garment = parsed.metadata.find("garment");
        if (!garment || !garment->truthy()) {
            std::vector<std::string> known;
            for (const auto& entry : world.appearance_reactions.fields())
                if (entry.first.empty() || entry.first[0] != '_')
                    known.push_back(entry.first);
            std::sort(known.begin(), known.end());
            if (known.empty())
                return make_result(parsed,
                                   "This world does not say what any garment means.");
            std::vector<std::string> plain;
            for (const std::string& one : known) plain.push_back(readable(one));
            return make_result(parsed, "Nothing here answers to that. This world "
                                       "knows: " + joined(plain, ", "));
        }
        Json wardrobe = player.appearance.truthy() ? player.appearance.copy()
                                                   : Json::object();
        wardrobe["garment"] = *garment;
        player.appearance = wardrobe;
        return make_result(parsed, "You are wearing " + readable(garment->py_str())
                                   + ". Nobody has been told; they can see it.");
    }

    /// `id.split(":")[-1].replace("_", " ")`.
    static std::string readable(const std::string& id) {
        std::size_t colon = id.rfind(':');
        std::string tail = colon == std::string::npos ? id : id.substr(colon + 1);
        std::replace(tail.begin(), tail.end(), '_', ' ');
        return tail;
    }

    TurnResult listen_radio(const ParsedCommand& parsed) {
        std::vector<long long> due;
        for (const Event& e : world.scenario_events)
            if (e.type == "broadcast") due.push_back(e.world_time);
        std::string message;
        if (!due.empty()) {
            long long soonest = *std::min_element(due.begin(), due.end());
            advance_time(std::max(0LL, soonest - world.world_time));
            message = "You catch the next city-news bulletin.";
        } else {
            advance_time(15);
            message = "Only recycled adverts and static are on the public band.";
        }
        const Agent& player = *world.agents.find(config.player_id);
        TurnResult out = make_result(
            parsed, message + "\n" + describe_location(player.location().py_str()));
        out.developer_trace = inspect_world();
        return out;
    }

    /// With `standing` on, an act is put into the world as a CLAIM as well as an
    /// event, so that it is perceived, believed, passed on and doubted by the
    /// machinery that already exists. Off, nothing is attached and the payload is
    /// byte for byte what it was.
    Json conduct_claim(const std::string& predicate, const std::string& victim_id) const {
        if (!core.standing.enabled() || victim_id.empty()) return Json::object();
        Json slots = Json::object();
        slots["who"] = victim_id;
        slots["by"] = config.player_id;
        Json claim = Json::object();
        claim["predicate"] = predicate;
        claim["slots"] = slots;
        claim["polarity"] = std::string("+");
        // `valid_start` is what individuates the INCIDENT, and leaving it off was
        // a real defect: every unkindness the player ever did to one person
        // collapsed into a single proposition, so six separate threats were one
        // claim heard six times and the correlation discount -- correctly --
        // refused to be persuaded by the repetition. With it, a repeated REPORT
        // of one incident is still one incident, while a second act is a second
        // thing to have done.
        claim["valid_start"] = world.world_time;
        Json out = Json::object();
        out["proposition"] = claim;
        return out;
    }

    Event player_event(const std::string& type, Json payload) {
        Event ev;
        ev.event_id = world.new_event_id();
        ev.world_time = world.world_time;
        ev.type = type;
        ev.actor = config.player_id;
        ev.location = world.agents.find(config.player_id)->location();
        ev.payload = std::move(payload);
        return ev;
    }

    std::vector<EventReceipt> handle_social_input(const ParsedCommand& parsed) {
        std::vector<EventReceipt> receipts;
        std::string target = parsed.target_id.py_str();
        std::string topic = parsed.topic.truthy() ? parsed.topic.py_str() : "None";

        if (parsed.intent == "ask" && parsed.proposition) {
            // A QUESTION IS NOT AN ASSERTION. This carried the proposition on a
            // "claim" event, so everyone in earshot -- including the person being
            // asked -- updated their belief as though the player had stated it as
            // fact. Asking twenty times would have walked any belief to certainty
            // from nothing.
            Json payload = Json::object();
            payload["proposition"] = parsed.proposition->as_json();
            payload["summary"] = "player asks about " + topic;
            payload["importance"] = 0.45;
            payload["origin_event"] = "player_turn_" + std::to_string(world.world_time);
            receipts.push_back(emit_event(player_event("question", payload)));
            for (const EventReceipt& one :
                 topic_reactions(parsed.topic, parsed.target_id))
                receipts.push_back(one);
        } else if (parsed.intent == "claim" && parsed.proposition) {
            Json payload = Json::object();
            payload["proposition"] = parsed.proposition->as_json();
            payload["summary"] = std::string("player makes a claim");
            payload["importance"] = 0.5;
            payload["origin_event"] = "player_claim_" + std::to_string(world.world_time);
            receipts.push_back(emit_event(player_event("claim", payload)));
        } else if (parsed.intent == "promise" && parsed.proposition) {
            Json payload = Json::object();
            payload["proposition"] = parsed.proposition->as_json();
            payload["summary"] = "player promised to pay " + parsed.amount.py_str()
                               + " credits";
            payload["importance"] = 0.75;
            // WHO IT WAS MADE TO, on the event rather than only in the trust
            // bump: a promise to nobody in particular is a statement of intent
            // and the ledger has to tell them apart.
            payload["target"] = parsed.target_id;
            Json appraisal = Json::object();
            appraisal["desirability"] = 0.25;
            payload["appraisal"] = appraisal;
            receipts.push_back(emit_event(player_event("promise", payload)));
            // Making one is rewarded immediately, which was fine while nothing
            // ever came due and is the exact asymmetry that made promises free.
            apply_trust(target, config.player_id, +0.35, "promise_made");
        } else if (parsed.intent == "assist") {
            // The counterpart to `threaten`, and until recently there was none.
            // Kind acts are quieter than cruel ones -- lower severity, lower
            // importance -- which is why `standing` weights `helped` below
            // `mistreated` rather than treating decency as symmetrical.
            Json payload = conduct_claim("helped", target).copy();
            payload["summary"] = "player helps " + target;
            payload["severity"] = 0.3;
            payload["importance"] = 0.5;
            payload["target"] = parsed.target_id;
            Json appraisal = Json::object();
            appraisal["desirability"] = 0.5;
            appraisal["agency"] = std::string("other");
            appraisal["praiseworthiness"] = 0.5;
            payload["appraisal"] = appraisal;
            receipts.push_back(emit_event(player_event("gift", payload)));
            apply_trust(target, config.player_id, +0.30, "helped");
        } else if (parsed.intent == "threaten") {
            Json payload = conduct_claim("mistreated", target).copy();
            payload["summary"] = "player threatens " + target;
            payload["severity"] = 0.6;
            payload["importance"] = 0.7;
            // Who it was done TO. Previously only in the summary string, which
            // meant no layer could act on it -- including the one that exists to
            // make a group react when one of its own is hurt.
            payload["target"] = parsed.target_id;
            Json appraisal = Json::object();
            appraisal["desirability"] = -0.6;
            appraisal["agency"] = std::string("other");
            appraisal["praiseworthiness"] = -0.4;
            payload["appraisal"] = appraisal;
            receipts.push_back(emit_event(player_event("threat", payload)));
            apply_trust(target, config.player_id, -0.45, "threatened");
        } else if (parsed.intent == "accuse") {
            Json payload = Json::object();
            payload["summary"] = "player accuses " + target + " about " + topic;
            payload["importance"] = 0.65;
            Json appraisal = Json::object();
            appraisal["desirability"] = -0.3;
            payload["appraisal"] = appraisal;
            receipts.push_back(emit_event(player_event("claim", payload)));
        }
        return receipts;
    }

    TurnResult attack(const ParsedCommand& parsed) {
        Agent& player = *world.agents.find(config.player_id);
        std::string target = parsed.target_id.truthy() ? parsed.target_id.py_str()
                                                       : default_target();
        Json payload = conduct_claim("mistreated", target).copy();
        payload["summary"] = "player attacks " + target;
        payload["severity"] = 0.8;
        payload["importance"] = 0.9;
        payload["target"] = target;
        Json appraisal = Json::object();
        appraisal["desirability"] = -0.8;
        appraisal["agency"] = std::string("other");
        appraisal["praiseworthiness"] = -0.6;
        appraisal["target"] = config.player_id;
        payload["appraisal"] = appraisal;
        EventReceipt receipt = emit_event(player_event("attack", payload));

        Agent* victim = world.agents.find(target);
        if (victim) core.catch_up(*victim);   // LOD: react from current affect
        Json situation = Json::object();
        situation["injured"] = true;
        situation["threatened"] = true;
        situation["threat_severity"] = 0.8;
        Runtime::Decision decision = core.decide(target, config.player_id, situation);

        std::string extra;
        if (decision.chosen.action.action_id == "mobilize_allies") {
            Runtime::Mobilized mob = core.mobilize(target, 1.0);
            std::vector<std::string> lines;
            for (const Reason& reason : mob.reasons)
                lines.push_back(reason.detail.get("ally").py_str() + " "
                                + reason.detail.get("outcome").py_str()
                                + " (p=" + format_fixed(reason.amount, 2) + ")");
            extra = "\n" + joined(lines, "\n");
        }
        TurnResult out = make_result(
            parsed, agent_name(target) + " reacts with "
                    + decision.chosen.action.action_id + "." + extra);
        out.receipts.push_back(receipt);
        std::vector<std::string> trace;
        for (const Reason& reason : decision.reasons)
            trace.push_back(py_repr(reason.as_json()));
        out.developer_trace = joined(trace, "\n");
        (void)player;
        return out;
    }

    /// Fire the events a pack authored for this topic being raised.
    ///
    /// Some subjects are themselves an act: asking a gang fixer about her hidden
    /// brother is a threat to her. That is a fact about a particular world, so it
    /// is authored in `topics.json` rather than special-cased here.
    std::vector<EventReceipt> topic_reactions(const Json& topic_id,
                                              const Json& addressee_id) {
        std::vector<EventReceipt> receipts;
        if (!topic_id.truthy()) return receipts;
        const Topic* topic = world.topics.find(topic_id.py_str());
        if (!topic) return receipts;
        for (const Json& spec : topic->resolved_reactions(
                 config.player_id,
                 addressee_id.truthy() ? addressee_id.py_str() : std::string())) {
            const Json* declared = spec.find("payload");
            Json payload = (declared && declared->truthy()) ? declared->copy()
                                                            : Json::object();
            if (!payload.find("topic")) payload["topic"] = topic->topic_id;
            Event ev;
            ev.event_id = world.new_event_id();
            ev.world_time = world.world_time;
            ev.type = spec.at("type").as_string();
            const Json* actor = spec.find("actor");
            ev.actor = (actor && actor->truthy()) ? *actor : Json(config.player_id);
            const Json* where = spec.find("location");
            ev.location = (where && where->truthy())
                ? *where : world.agents.find(config.player_id)->location();
            ev.payload = payload;
            receipts.push_back(emit_event(ev));
        }
        return receipts;
    }

    void seed_belief(const std::string& agent_id, const Proposition& prop,
                     const std::string& summary, const Json& origin_event,
                     double trust, double competence, double importance) {
        Agent* agent = world.agents.find(agent_id);
        if (!agent) return;
        core.belief.update(agent->beliefs, prop, prop.polarity, trust, competence,
                           agent->skepticism(),
                           Json("seed:" + origin_event.py_str()), origin_event,
                           world.world_time);
        auto item = std::make_shared<MemoryItem>();
        item->memory_id = "mem:" + origin_event.py_str();
        item->owner = agent_id;
        item->type = "episodic";
        item->content = summary;
        item->proposition = prop;
        item->importance = importance;
        item->emotional_valence = 0.0;
        item->source_conf = trust;
        core.memory.encode(agent->memory, item, world.world_time);
    }

    void apply_trust(const std::string& owner_id, const std::string& subject_id,
                     double amount, const std::string& reason) {
        Agent* owner = world.agents.find(owner_id);
        if (!owner) return;
        std::vector<Reason> reasons;
        core.relationship.apply(
            *owner, {trust_delta(owner_id, subject_id, amount, reason, "sdk")},
            reasons);
        std::vector<Reason>& bucket = core.last_traces[owner_id];
        for (const Reason& one : reasons) bucket.push_back(one);
    }

    /// Which of this character's protected facts are already public.
    ///
    /// Empty whenever the common-knowledge layer is off, which is what keeps the
    /// secret machinery byte-identical without it.
    std::set<std::string> keys_out(const Agent& agent) const {
        std::set<std::string> out;
        if (!core.common_knowledge.enabled()) return out;
        for (const std::string& key : protected_keys(secrets_of(agent)))
            if (core.common_knowledge.is_out(key, agent.id)) out.insert(key);
        return out;
    }

    /// Has this secret stopped working?
    ///
    /// EVERY fact it protects has to be public, not merely one: a secret
    /// guarding three things is still doing a job while one of them is unknown.
    /// A secret that protects nothing in particular is never spent this way --
    /// there is nothing for a crowd to have witnessed.
    bool secret_is_out(const Agent& agent, const Secret& secret) const {
        if (!core.common_knowledge.enabled() || secret.protects.empty()) return false;
        for (const std::string& key : secret.protects)
            if (!core.common_knowledge.is_out(key, agent.id)) return false;
        return true;
    }

    static std::vector<Secret> secrets_of(const Agent& agent) {
        std::vector<Secret> out;
        for (const Json& row : agent.secrets) out.push_back(Secret::from_json(row));
        return out;
    }

    /// Who is close enough to hear this exchange, deterministically.
    std::vector<std::string> earshot(const Agent& speaker,
                                     const std::string& addressee) const {
        std::vector<std::string> others;
        for (const auto& entry : world.agents)
            if (entry.second.location().py_str() == speaker.location().py_str()
                && entry.first != speaker.id && entry.first != addressee)
                others.push_back(entry.first);
        std::sort(others.begin(), others.end());
        if (others.empty()) return {addressee};
        std::vector<std::uint8_t> seed = derive_seed(world.global_seed, speaker.id,
                                                     addressee, world.world_time,
                                                     "earshot");
        std::size_t start = static_cast<std::size_t>(seeded_uniform(seed)
                                                     * others.size());
        std::vector<std::string> out = {addressee};
        std::size_t take = std::min(EARSHOT, others.size());
        for (std::size_t i = 0; i < take; ++i)
            out.push_back(others[(start + i) % others.size()]);
        return out;
    }

    /// Which competence applies to this claim, per the world's declaration.
    std::string domain_for(const Proposition& proposition) const {
        const Json* found = world.predicate_domains.find(proposition.predicate);
        return found ? found->py_str() : "street";
    }

    /// Which incident a spoken claim traces back to.
    ///
    /// The origin travels with the CLAIM, not with the mouth it came out of --
    /// the same rule diffusion has always followed. Dialogue did not follow it:
    /// every answer minted `said_<speaker>_<time>`, so asking one person the same
    /// question twice produced two origins and the runtime counted its own
    /// repetition as independent corroboration.
    ///
    /// A LIE IS DIFFERENT. An honest answer passes on evidence that already
    /// existed and inherits the origin of the speaker's own belief; a lie has no
    /// evidential ancestor, so the origin names the speaker.
    ///
    /// IT NAMES THE CLAIM AS WELL, and the second half was missing. The origin
    /// used to be `said_<speaker>_<world_time>`, so the same person telling the
    /// same lie in a later minute minted a SECOND origin and the runtime counted
    /// its own repetition as independent corroboration. Keying it on the
    /// proposition makes one liar telling one lie one source however often they
    /// are asked, while a different lie from the same mouth is still a different
    /// origin.
    std::string spoken_origin(const Agent& agent, const SemanticMove& move) const {
        const Belief* own = move.proposition
            ? agent.beliefs.find(move.proposition->core_key()) : nullptr;
        if (move.honesty != "lie" && own) {
            // `if own.primary_origin:` -- truthiness, so a belief whose first
            // origin is an empty string falls through to the speaker's own name.
            const std::string* origin = own->primary_origin();
            if (origin && !origin->empty()) return *origin;
        }
        return "said_" + agent.id + "_"
             + (move.proposition ? move.proposition->core_key() : std::string());
    }

    /// Emit what was committed as a real claim event, and say who heard it.
    ///
    /// Until this existed, an NPC's answer had no epistemic consequence at all:
    /// a character could tell the player the seal had failed with four people in
    /// the room and none of them learned anything.
    ///
    /// Only the COMMITMENT is emitted. The provider's wording is presentation and
    /// never reaches the belief system, which is what makes the text layer
    /// replaceable without changing the simulation.
    Json speak_aloud(const Agent& agent, const std::vector<SemanticMove>& moves,
                     const std::string& addressee) {
        Json spoken = Json::array();
        for (const SemanticMove& move : moves) {
            if (!move.is_factual() || !move.proposition) continue;
            double strength = move.certainty == "certain" ? 1.0
                            : move.certainty == "probable" ? 0.8
                            : move.certainty == "uncertain" ? 0.55 : 0.8;
            Json payload = Json::object();
            payload["proposition"] = move.proposition->as_json();
            // A conversation is not a public announcement. Without a bound,
            // answering one question in a crowded place updated every person in
            // it, which is both wrong and quadratic: measured at 600 agents, 825
            // events produced 137,000 belief updates.
            Json audience = Json::array();
            for (const std::string& one : earshot(agent, addressee)) audience.push(one);
            payload["audience"] = audience;
            payload["summary"] = agent.id + " said so to " + addressee;
            payload["importance"] = 0.45;
            payload["assertion_strength"] = strength;
            payload["domain"] = domain_for(*move.proposition);
            Json said = Json::object();
            said["addressee"] = addressee;
            said["act"] = move.act;
            said["certainty"] = move.certainty;
            said["honesty"] = move.honesty;
            payload["spoken"] = said;
            payload["origin_event"] = spoken_origin(agent, move);

            Event ev;
            ev.event_id = world.new_event_id();
            ev.world_time = world.world_time;
            ev.type = "claim";
            ev.actor = agent.id;
            ev.location = agent.location();
            ev.payload = payload;
            EventReceipt receipt = emit_event(ev);

            Json row = Json::object();
            row["proposition"] = move.proposition->core_key();
            row["rendered"] = move.rendered();
            row["certainty"] = move.certainty;
            row["honesty"] = move.honesty;
            Json heard = Json::array();
            std::vector<std::string> listeners;
            // Agent ids only. The trace map also carries the layer buckets --
            // `_promises`, `_common_knowledge` and the rest -- and those were
            // being reported as people who heard the line.
            for (const std::string& one : receipt.observed_by)
                if (one != agent.id && !(one.size() && one[0] == '_'))
                    listeners.push_back(one);
            std::sort(listeners.begin(), listeners.end());
            for (const std::string& one : listeners) heard.push(one);
            row["heard_by"] = heard;
            spoken.push(row);
        }
        return spoken;
    }

    /// How this character words an answer on this topic, given what they believe.
    ///
    /// The engine ships NO factual sentences: an `inform` line has to come from
    /// the pack, because only the pack knows what is true in its world.
    Json answer_phrasing(const Agent& agent, const std::string& topic_id,
                         const std::optional<Proposition>& query) const {
        const Topic* topic = topic_id.empty() ? nullptr : world.topics.find(topic_id);
        if (!topic || !query || !topic->phrasings.truthy()) return Json::object();
        const Belief* belief = agent.beliefs.find(query->core_key());
        if (!belief) return Json::object();
        bool holds = belief->expected_prob() >= 0.5;
        bool affirmed = query->polarity == "+" ? holds : !holds;
        return topic->phrasing_for(affirmed);
    }

    /// Keep only the moves the authored answer actually words.
    ///
    /// A pack authors a phrasing per TOPIC, and it says one thing: whether the
    /// topic's own query holds. Any other proposition the selection reached for
    /// has no sentence behind it, so committing to it means asserting something
    /// nobody says -- the mismatch between the player and the room that
    /// controlled release exists to prevent, arriving from the runtime's own side
    /// rather than a provider's.
    ///
    /// With no phrasing there is nothing factual to say at all: the realizer
    /// falls back to a stance line, and a stance line asserts nothing.
    static Commitment only_what_can_be_said(const Commitment& commitment,
                                            const Json& phrasing,
                                            const std::optional<Proposition>& query) {
        std::vector<SemanticMove> keep, dropped;
        bool has_phrasing = phrasing.truthy();
        std::string covered = query ? query->core_key() : std::string();
        for (const SemanticMove& move : commitment.moves) {
            if (!move.is_factual()) keep.push_back(move);
            else if (has_phrasing && !covered.empty()
                     && move.proposition->core_key() == covered) keep.push_back(move);
            else dropped.push_back(move);
        }
        if (dropped.empty()) return commitment;
        Commitment out;
        out.moves = keep;
        out.forbidden = commitment.forbidden;
        out.max_sentences = commitment.max_sentences;
        out.reasons = commitment.reasons;
        Json why = Json::object();
        Json gone = Json::array();
        for (const SemanticMove& move : dropped) gone.push(move.rendered());
        why["dropped"] = gone;
        Json kept = Json::array();
        for (const SemanticMove& move : keep)
            if (move.is_factual()) kept.push(move.rendered());
        why["kept"] = kept;
        why["note"] = std::string("no authored phrasing words these, so nothing "
                                  "commits to them and nothing propagates");
        out.reasons.push_back({"commitment.unsayable_dropped",
                               static_cast<double>(dropped.size()), why});
        return out;
    }

    /// The proposition a belief must be relevant to for this topic. Authored.
    std::optional<Proposition> topic_query(const std::string& topic_id) const {
        const Topic* topic = topic_id.empty() ? nullptr : world.topics.find(topic_id);
        if (!topic) return std::nullopt;
        Json query = topic->resolved_query(config.player_id);
        if (!query.truthy()) return std::nullopt;
        return Proposition::from_json(query);
    }

    std::optional<DialogueResponse> direct_answer(const std::string& agent_id,
                                                  const std::string& interlocutor,
                                                  const std::string& topic,
                                                  std::vector<Reason>* gate_reasons);

    std::optional<DialogueResponse> tell_a_lie(Agent& agent,
                                               const std::string& interlocutor,
                                               const std::string& topic,
                                               const Secret& secret,
                                               ConversationState& conv);

    DialogueResponse deliver(Agent& agent, const std::string& interlocutor,
                             DialoguePlan& plan, const Commitment& commitment,
                             ConversationState& conv, const std::string& topic,
                             const std::string& kind = "direct_answer",
                             const std::vector<Reason>& extra_reasons = {});

    static Reason as_reason(const Json& row) {
        const std::vector<Json>& parts = row.items();
        return Reason{parts.at(0).py_str(), parts.at(1).as_double(), parts.at(2)};
    }

    bool initial_state_loaded_ = false;
};

/// The answer a character gives when they actually have something to say.
///
/// Returns nothing when they do not, or will not -- and the caller falls through
/// to ordinary deliberation, carrying the reason WHY it fell through.
inline std::optional<DialogueResponse> UnscriptedRuntime::direct_answer(
        const std::string& agent_id, const std::string& interlocutor,
        const std::string& topic, std::vector<Reason>* gate_reasons) {
    if (topic.empty()) return std::nullopt;
    Agent& agent = *world.agents.find(agent_id);

    // Multi-turn continuity: this conversation persists across turns, and across
    // save and load.
    std::string conv_id = "conv_" + agent_id + "_" + interlocutor;
    if (!core.conversations.contains(conv_id)) {
        ConversationState fresh;
        fresh.conv_id = conv_id;
        fresh.participants = {agent_id, interlocutor};
        core.conversations[conv_id] = fresh;
    }
    ConversationState& conv = *core.conversations.find(conv_id);
    long long times_asked = conv.discussed_topics.get(topic, 0);   // before this turn
    std::optional<Proposition> topic_prop = topic_query(topic);

    // 1. THE TRUST GATE FIRST. Any secret this character holds that guards this
    //    topic decides whether they will engage with the subject at all --
    //    before, and independently of, whether they happen to have something
    //    sayable. Checking it after the fact filter hid the gate exactly when
    //    the character's only knowledge of the topic WAS the protected
    //    proposition. Its predecessor read `topic == "milan"`, so the protection
    //    existed for one character in one pack.
    std::vector<Secret> mine = secrets_of(agent);
    std::vector<Secret> guarding = secrets_guarding(mine, topic);

    // A secret that is common knowledge in this character's own community has
    // stopped being one. Concealment is not about who has found out, it is about
    // whether everybody knows that everybody has -- and once they do, refusing to
    // discuss it protects nothing and only marks you as the person refusing.
    std::vector<Secret> spent, still_guarding;
    for (const Secret& one : guarding)
        (secret_is_out(agent, one) ? spent : still_guarding).push_back(one);
    if (!spent.empty()) {
        guarding = still_guarding;
        Json why = Json::object();
        why["agent"] = agent.id;
        why["topic"] = topic;
        Json ids = Json::array();
        for (const Secret& one : spent) ids.push(one.secret_id);
        why["secrets"] = ids;
        why["note"] = std::string("it is out in the open; denying it protects nothing");
        core.last_traces["_common_knowledge"].push_back(
            {"common_knowledge.secret_spent", static_cast<double>(spent.size()), why});
    }

    // How open the room is to a stranger shifts what the player's trust is worth
    // here -- the same person, in a place that has just had a killing in it, gets
    // less. Zero when the climate layer is off.
    double trust = std::max(0.0, std::min(1.0,
        agent.trust_in(interlocutor)
        + core.climate.modifiers(agent.location().py_str())
              .at("stranger_trust").as_double()));

    std::vector<Secret> withholding;
    for (const Secret& one : guarding)
        if (trust < one.min_trust) withholding.push_back(one);

    if (!withholding.empty()) {
        // Refuse, or LIE? A character with an authored cover story and little
        // commitment to the truth says something else instead of falling silent
        // -- and what they say is a real claim, from them, which the listener may
        // later find contradicted.
        for (const Secret& one : withholding) {
            if (!agent.will_lie_about(has_cover_story(one), one.min_trust))
                continue;
            std::optional<DialogueResponse> deceit =
                tell_a_lie(agent, interlocutor, topic, one, conv);
            if (deceit) return deceit;
            break;                       // `next(...)` takes the FIRST that will
        }
    }
    if (!withholding.empty()) {
        double required = withholding.front().min_trust;
        for (const Secret& one : withholding) required = std::min(required, one.min_trust);
        Json why = Json::object();
        why["topic"] = topic;
        why["trust"] = py_round(trust, 3);
        why["required"] = required;
        Json ids = Json::array();
        for (const Secret& one : withholding) ids.push(one.secret_id);
        why["secrets"] = ids;
        why["note"] = std::string("below authored trust threshold; will not discuss");
        Reason gate{"dialogue.secret_gate", trust, why};
        if (gate_reasons) gate_reasons->push_back(gate);
        core.last_traces[agent_id] = {gate};
        return std::nullopt;
    }

    // 2. What they may say. A PROTECTED proposition is never an allowed fact at
    //    any trust level -- trust unlocks engagement, not disclosure -- so it
    //    cannot reach a text provider's context at all.
    std::set<std::string> protect = protected_keys(mine);
    for (const std::string& out : keys_out(agent)) protect.erase(out);

    std::vector<Candidate> candidates;
    for (const auto& entry : agent.beliefs) {
        const Belief& belief = entry.second;
        double probability = belief.expected_prob();
        double confidence = std::max(probability, 1.0 - probability);
        if (confidence < 0.6) continue;
        double fit = topic_prop ? relevance(belief.proposition, *topic_prop) : 1.0;
        if (topic_prop && fit == 0.0) continue;
        bool affirmed = probability >= 0.5;
        Proposition fact = affirmed ? belief.proposition : belief.proposition.negated();
        if (protect.count(belief.proposition.core_key()) || protect.count(fact.str()))
            continue;
        Candidate candidate;
        candidate.proposition = belief.proposition;
        candidate.confidence = confidence;
        candidate.relevance = fit;
        candidate.affirmed = affirmed;
        candidates.push_back(candidate);
    }
    if (candidates.empty()) return std::nullopt;

    // THE decision that used to belong to the text layer. The runtime picks
    // which of the relevant things this character says; the realizer renders it.
    // Seeded, so the answer varies between worlds and stays replayable in one.
    const std::vector<Secret>& forbidding = guarding.empty() ? mine : guarding;
    Commitment commitment = select(
        candidates, "assert", 2,
        {world.global_seed, agent_id, std::to_string(conv.turn_count),
         std::to_string(world.world_time), "dialogue"},
        avoid_labels(forbidding));
    // NOTHING IS COMMITTED THAT THE ANSWER CANNOT SAY. The phrasing authored for
    // this topic words ONE claim -- the topic's own query -- and the selection
    // above could pick two. The second was propagated to everyone in the room by
    // a sentence that never mentioned it.
    Json phrasing = answer_phrasing(agent, topic, topic_prop);
    commitment = only_what_can_be_said(commitment, phrasing, topic_prop);
    std::vector<std::string> facts = commitment.rendered_facts();
    if (facts.empty()) return std::nullopt;

    StyleVector style = core.style_for(agent, interlocutor);
    DialoguePlan plan;
    plan.speaker = agent_id;
    plan.addressee = interlocutor;
    plan.dialogue_act = "inform";
    plan.goal = "answer";
    if (!agent.goals.empty()) {
        const Json* content = agent.goals.front().find("content");
        if (content) plan.goal = content->py_str();
    }
    plan.avoid_topics = avoid_labels(forbidding);
    plan.style = style.as_json();
    plan.phrasing = phrasing;
    plan.request_id = "direct:" + agent_id + ":" + std::to_string(world.world_time)
                    + ":" + std::to_string(conv.turn_count);
    plan.commit(commitment);
    // A re-asked topic gets a terser answer: the character already told them
    // this. NOT catchable with the deterministic realizer, and worth saying so:
    // `max_length` reaches an external provider's prompt and nothing else, so
    // halving it changes what a language model is asked for and cannot change a
    // template. It is here because the day a provider is attached it is the
    // difference between a character repeating themselves at length and one
    // getting to the point.
    if (times_asked >= 1) plan.max_length = std::max(10LL, plan.max_length / 2);
    return deliver(agent, interlocutor, plan, commitment, conv, topic);
}

/// Say the authored cover story instead of refusing.
///
/// Four things are kept apart, and this is where they separate: what the speaker
/// BELIEVES, what they WANT, what they SAY, and what they intend the listener to
/// believe afterwards. The move carries the cover story as its proposition and
/// the speaker's real confidence in it as `believed_probability`, so the
/// divergence is on the record rather than implied.
///
/// The lie is a real claim from a real person. The listener acquires it with this
/// character as its origin -- which is what makes it refutable later, and what
/// makes exposing the liar do something.
inline std::optional<DialogueResponse> UnscriptedRuntime::tell_a_lie(
        Agent& agent, const std::string& interlocutor, const std::string& topic,
        const Secret& secret, ConversationState& conv) {
    Json tmpl = resolve_template(secret.cover_story, config.player_id, interlocutor);
    if (!tmpl.truthy()) return std::nullopt;
    if (tmpl.kind() != Json::Kind::Object || !tmpl.find("predicate"))
        return std::nullopt;                 // Python catches the parse failure
    Proposition claim = Proposition::from_json(tmpl);

    const Belief* held = agent.beliefs.find(claim.core_key());
    double really_thinks = held ? held->expected_prob() : 0.0;

    SemanticMove move;
    move.act = "assert";
    move.proposition = claim;
    move.certainty = CERTAIN;
    move.disclosure = DIRECT;
    move.honesty = LIE;
    move.believed_probability = really_thinks;

    Json why = Json::object();
    why["secret"] = secret.secret_id;
    why["asserted"] = claim.str();
    why["speaker_believes_it_with"] = py_round(really_thinks, 3);
    why["truthfulness"] = py_round(agent.value("truthfulness"), 3);
    why["stake"] = secret.min_trust;
    why["note"] = std::string("cover story: the stake outweighed their honesty");

    Commitment lie;
    lie.moves = {move};
    lie.forbidden = avoid_labels({secret});
    lie.reasons = {{"dialogue.deception", 1.0, why}};

    StyleVector style = core.style_for(agent, interlocutor);
    DialoguePlan plan;
    plan.speaker = agent.id;
    plan.addressee = interlocutor;
    plan.dialogue_act = "inform";
    plan.goal = "protect " + secret.secret_id;
    plan.avoid_topics = avoid_labels({secret});
    plan.style = style.as_json();
    plan.phrasing = secret.cover_phrasings.truthy() ? secret.cover_phrasings
                                                    : Json::object();
    plan.request_id = "lie:" + agent.id + ":" + std::to_string(world.world_time)
                    + ":" + std::to_string(conv.turn_count);
    plan.commit(lie);
    plan.stance = "deceptive";
    return deliver(agent, interlocutor, plan, lie, conv, topic, "deception");
}

/// Realize, validate, release, and let the world hear what was committed.
///
/// Both the honest answer and the lie come through here, and they go through
/// exactly the same checks. A lie is not a special case of speaking -- it is an
/// ordinary commitment whose proposition happens not to be what the speaker
/// believes -- so giving it its own release path would be the place a bug hides.
inline DialogueResponse UnscriptedRuntime::deliver(
        Agent& agent, const std::string& interlocutor, DialoguePlan& plan,
        const Commitment& commitment, ConversationState& conv,
        const std::string& topic, const std::string& kind,
        const std::vector<Reason>& extra_reasons) {
    const std::string& agent_id = agent.id;
    std::vector<std::string> facts = plan.allowed_facts;
    std::vector<Reason> provider_reasons;
    bool fallback_used = false;

    // The deterministic realizer never fails, so the provider-failure branch
    // Python carries has nothing to catch here: an external provider lives on
    // the host side of the C ABI, and this is where its answer would arrive.
    // WHICH REALIZER WROTE THE LINE, tracked rather than assumed: the
    // commitment check has to ask the one that produced the text, and reading a
    // flag left on the other object is how a fallback line came to be judged by
    // a call that never made it.
    TemplateRealizer* wrote_it = &core.realizer;
    std::string text = wrote_it->realize(plan, StyleVector::from_json(plan.style));
    bool authored = TemplateRealizer::IS_DETERMINISTIC;

    std::vector<std::string>& recent = conv.recent_lines;
    std::string off = CANON_OFF;
    ValidationResult result = core.validator.check(text, plan, agent, recent,
                                                   authored ? &off : nullptr);
    // A REJECTION IS TWO DIFFERENT ANSWERS, and treating them as one was the
    // defect. An UNSAFE line must not be released and its commitment must not
    // reach the world. A REPEATED line is a quality objection: the runtime looks
    // for another complete wording of the same commitment, and failing that says
    // it again -- rather than letting an earlier sentence decide whether a later
    // fact enters the society.
    if (result.verdict != ACCEPT) {
        if (is_unsafe(result)) {
            fallback_used = true;
            for (const Json& one : result.reasons)
                provider_reasons.push_back(as_reason(one));
            Json why = Json::object();
            why["from_verdict"] = result.verdict;
            provider_reasons.push_back({"dialogue.validation_fallback", 1.0, why});
            plan.dialogue_act = plan.fallback_template_id;
            // A deflection has to deflect. `lookup` prefers the authored phrasing
            // over the act, so leaving it in place released the same sentence
            // again and called it a fallback.
            plan.phrasing = Json::object();
            wrote_it = &core.fallback_realizer;
            text = wrote_it->realize(plan, StyleVector::from_json(plan.style));
            result = core.validator.check(text, plan, agent, recent, &off);
        } else {
            bool reworded = false;
            for (const std::string& spare : core.fallback_realizer.variants(
                     plan, StyleVector::from_json(plan.style))) {
                if (spare == text) continue;
                ValidationResult retry =
                    core.validator.check(spare, plan, agent, recent, &off);
                if (retry.verdict == ACCEPT) {
                    Json why = Json::object();
                    why["was"] = text;
                    why["now"] = spare;
                    Json codes = Json::array();
                    for (const Json& one : result.reasons)
                        codes.push(one.items().empty() ? Json(std::string())
                                                       : one.items()[0]);
                    why["why"] = codes;
                    provider_reasons.push_back({"dialogue.reworded", 1.0, why});
                    text = spare;
                    result = retry;
                    wrote_it = &core.fallback_realizer;
                    reworded = true;
                    break;
                }
            }
            if (!reworded) {
                for (const Json& one : result.reasons)
                    provider_reasons.push_back(as_reason(one));
                Json why = Json::object();
                why["verdict"] = result.verdict;
                why["note"] = std::string("a quality objection, not a safety one; "
                                          "the commitment stands");
                provider_reasons.push_back({"dialogue.released_anyway", 1.0, why});
                // AND THE VERDICT SAYS SO. Releasing the line while returning the
                // rejection left status, emission and audit disagreeing: from the
                // fourth identical question onward the claim reached the room,
                // `accepted_output` was blank and the caller got REJECT_SOFT, so a
                // client that hides rejected answers showed the player nothing the
                // room had just heard. One decision, recorded once.
                result.verdict = ACCEPT;
            }
        }
    }
    recent.push_back(text);
    if (recent.size() > 5)
        recent.erase(recent.begin(), recent.end() - 5);   // bound the anti-repeat window
    long long times_now = topic.empty() ? 0 : conv.note_topic(topic, world.world_time);

    // What was COMMITTED enters the world, never what the provider wrote. If the
    // line was replaced by a fallback the commitment is void: nothing was
    // actually asserted, so nothing may propagate. The player must never read a
    // deflection while the room hears an assertion.
    bool expressed = wrote_it->expressed_commitment;
    if (!expressed) {
        Json why = Json::object();
        Json committed = Json::array();
        for (const std::string& one : plan.allowed_facts) committed.push(one);
        why["committed"] = committed;
        why["note"] = std::string("no authored phrasing carries this; nothing was "
                                  "asserted");
        provider_reasons.push_back({"dialogue.commitment_unexpressed", 1.0, why});
    }

    std::vector<SemanticMove> spoken_moves;
    if (!fallback_used && expressed) spoken_moves = plan.moves;
    Json spoken = speak_aloud(agent, spoken_moves, interlocutor);

    std::vector<Reason> reasons = provider_reasons;
    for (const Reason& one : commitment.reasons) reasons.push_back(one);
    Json why = Json::object();
    why["topic"] = topic.empty() ? Json() : Json(topic);
    Json listed = Json::array();
    for (const std::string& one : facts) listed.push(one);
    why["facts"] = listed;
    why["spoken"] = spoken;
    why["times_asked"] = times_now;
    why["turn"] = conv.turn_count;
    reasons.push_back({"dialogue." + kind, 1.0, why});
    for (const Reason& one : extra_reasons) reasons.push_back(one);
    for (const Json& one : result.reasons) reasons.push_back(as_reason(one));
    if (times_now > 1) {
        Json repeated = Json::object();
        repeated["topic"] = topic;
        repeated["note"] = std::string("player re-asked; answer kept terse");
        reasons.push_back({"dialogue.topic_repeated",
                           static_cast<double>(times_now), repeated});
    }
    ++conv.turn_count;
    core.last_traces[agent_id] = reasons;

    DialogueResponse out;
    out.speaker_id = agent_id;
    out.text = text;
    out.act = plan.dialogue_act;
    out.verdict = result.verdict;
    out.utility = 1.0;
    for (const Reason& one : reasons) out.reasons.push_back(one.as_json());
    out.style = plan.style;
    return out;
}

}  // namespace usc
