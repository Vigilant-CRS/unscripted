// `usc/routine.py`. What makes a cast a society rather than a tableau.
//
// Characters never moved. Whoever a pack placed somewhere stood there for the
// rest of the session, so in two of the three reference packs no two characters
// ever shared a place and the diffusion layer -- the thing that makes
// information travel -- could not fire at all. The benchmark reported it as SKIP
// rather than as a pass, which is how it surfaced.
//
// The model is deliberately the small one that buys the most: a schedule of
// places by time of day, authored per character. Not pathfinding, not
// needs-driven planning, not GOAP. It gets people into the same room at the same
// time for reasons an author chose, which is the precondition for everything the
// runtime already does well.
//
// THE RUNTIME COUPLING IS A PARAMETER HERE, not a dependency. Python reaches
// through `runtime` for the action bridge, the climate layer and the event
// ledger; none of those is ported yet, and faking them would be worse than
// naming the seam. `step()` takes a callback and reports what it would have
// emitted, so the part that is ported is exercised for real and the part that is
// not is visibly absent.
#pragma once

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <functional>
#include <stdexcept>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/world.hpp"

namespace usc {

inline constexpr long long MINUTES_PER_DAY = 1440;

/// `"07:30"` -> 450 minutes past midnight. A plain integer is accepted too.
///
/// Throws on anything else, deliberately: a routine time an author mistyped is a
/// character who is in the wrong place all session, and finding that at load is
/// worth an exception.
inline long long parse_clock(const Json& value) {
    if (value.is_number() && value.kind() != Json::Kind::Bool) {
        long long minutes = value.as_int() % MINUTES_PER_DAY;
        // Python's `%` on a negative int returns a POSITIVE remainder; C++ does
        // not. An author writing -30 means half an hour before midnight.
        return minutes < 0 ? minutes + MINUTES_PER_DAY : minutes;
    }
    const std::string text = value.py_str();
    std::size_t start = text.find_first_not_of(" \t\n\r");
    std::size_t stop = text.find_last_not_of(" \t\n\r");
    std::string trimmed = start == std::string::npos ? "" : text.substr(start, stop - start + 1);

    std::size_t colon = trimmed.find(':');
    bool shaped = colon != std::string::npos && colon >= 1 && colon <= 2
               && trimmed.size() == colon + 3;
    if (shaped)
        for (std::size_t i = 0; i < trimmed.size(); ++i)
            if (i != colon && !std::isdigit(static_cast<unsigned char>(trimmed[i])))
                shaped = false;
    if (!shaped)
        throw std::invalid_argument(
            "Routine time must be HH:MM or minutes past midnight, got '" + text + "'");

    long long hours = std::stoll(trimmed.substr(0, colon));
    long long minutes = std::stoll(trimmed.substr(colon + 1));
    if (hours < 0 || hours >= 24 || minutes < 0 || minutes >= 60)
        throw std::invalid_argument("Routine time out of range: '" + text + "'");
    return hours * 60 + minutes;
}

struct RoutineBlock {
    long long start = 0;
    std::string place;
    std::string activity;
};

/// One character's schedule: which place, at which time of day.
class Routine {
public:
    Routine() = default;

    explicit Routine(std::vector<RoutineBlock> blocks) : blocks_(std::move(blocks)) {
        // Stable, because Python's `sorted` is: two blocks declared for the same
        // minute keep the order the author wrote them in, and the later one wins
        // in `block_at`.
        std::stable_sort(blocks_.begin(), blocks_.end(),
                         [](const RoutineBlock& a, const RoutineBlock& b) {
                             return a.start < b.start;
                         });
    }

    static Routine from_json(const Json& entries) {
        std::vector<RoutineBlock> blocks;
        for (const Json& entry : entries.items()) {
            const Json* activity = entry.find("activity");
            blocks.push_back({parse_clock(entry.at("from")),
                              entry.at("place").as_string(),
                              activity && !activity->is_null() ? activity->py_str() : ""});
        }
        return Routine(std::move(blocks));
    }

    bool empty() const { return blocks_.empty(); }
    const std::vector<RoutineBlock>& blocks() const { return blocks_; }

    /// The block in force at this world time, wrapping past midnight.
    ///
    /// Before the first block of the day a character is still in the last block
    /// of the previous one -- which is what makes an overnight block work
    /// without the author writing it twice.
    const RoutineBlock* block_at(long long world_time) const {
        if (blocks_.empty()) return nullptr;
        long long minute = world_time % MINUTES_PER_DAY;
        if (minute < 0) minute += MINUTES_PER_DAY;      // Python's % is positive
        const RoutineBlock* chosen = &blocks_.back();   // yesterday's last block
        for (const RoutineBlock& block : blocks_) {
            if (block.start <= minute) chosen = &block;
            else break;
        }
        return chosen;
    }

private:
    std::vector<RoutineBlock> blocks_;
};

using RoutineReason = Reason;

/// `HH:MM`, zero-padded, as the f-string writes it.
inline std::string clock_string(long long minute) {
    // Sized for the full range of the type, not for the range a caller should
    // pass. The compiler is right that a `long long` does not fit in sixteen
    // bytes, and silencing it with a cast would trade a warning for a truncation
    // nobody would ever look for.
    char buffer[48];
    std::snprintf(buffer, sizeof buffer, "%02lld:%02lld", minute / 60, minute % 60);
    return buffer;
}

class RoutineEngine {
public:
    struct Params {
        /// Emit a world event when somebody arrives. On by default: an arrival
        /// is observable, and "who was where when" is the raw material of a
        /// detective scene. Importance is low, so these consolidate away before
        /// anything that matters to a character.
        bool emit_events = true;
        double arrival_importance = 0.15;
    };

    RoutineEngine() = default;
    explicit RoutineEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }

    /// What a move would tell the rest of the runtime, for a caller that has an
    /// event ledger to put it on. Ignored when none is supplied.
    using OnArrival = std::function<void(const Agent&, const std::string& place,
                                         const std::string& origin,
                                         const std::string& activity)>;

    /// Whoever walks brings the mood of where they came from.
    ///
    /// `climate.carried(from, to)`, supplied by the caller because this module
    /// has no business knowing the climate layer exists. Nothing happens when
    /// the layer is off, and nothing happens when no caller supplies it -- which
    /// is what a probe does.
    ///
    /// The return value used to be discarded on the Python side. The mood really
    /// did travel and the drift was measurable, but nothing could SEE it happen,
    /// so the one mechanism the climate layer is documented around was invisible
    /// in every trace.
    using CarriedMood = std::function<std::vector<RoutineReason>(
        const std::string& from, const std::string& to)>;

    /// With an engine attached, the runtime does not move anyone: it ASKS, and
    /// the character stays where the player can see them until the engine says
    /// otherwise.
    ///
    /// Supplied by the caller because this module has no business knowing the
    /// action bridge exists. Returns the intent id when one was issued, an empty
    /// string when the character is already mid-act, and nothing at all when
    /// there is no bridge or it is off -- which is when this module moves them
    /// itself, exactly as it always did.
    struct MoveRequest {
        bool bridged = false;      // an engine owns this move
        bool issued = false;       // ... and a fresh intent was raised for it
        std::string intent_id;
    };
    using RequestMove = std::function<MoveRequest(
        const Agent&, const std::string& place, const std::string& origin,
        const std::string& activity, long long start)>;

    /// Place everyone where their routine says they should be right now.
    ///
    /// Called once at startup, so a session does not begin with the cast
    /// standing wherever the character files happened to list -- which, for an
    /// overnight start time, is the wrong place by several hours.
    std::vector<RoutineReason> seed(World& world,
                                    const OrderedMap<Routine>& routines) {
        std::vector<RoutineReason> reasons;
        for (Agent* agent : sorted_cast(world)) {
            const Routine* routine = routines.find(agent->id);
            if (!routine || routine->empty()) continue;
            const RoutineBlock* block = routine->block_at(world.world_time);
            if (!block) continue;
            applied_[agent->id] = block->start;
            if (agent->location().py_str() == block->place) continue;
            Json detail = Json::object();
            detail["agent"] = agent->id;
            detail["from"] = agent->location();
            detail["place"] = block->place;
            detail["activity"] = block->activity;
            reasons.push_back({"routine.placed", static_cast<double>(block->start), detail});
            agent->set_location(Json(block->place));
        }
        return reasons;
    }

    /// Advance routines over the elapsed window and move whoever is due.
    ///
    /// A window longer than a day still lands everyone correctly: the block in
    /// force at the END of the window is where they belong, and blocks they
    /// would have passed through are skipped rather than replayed -- a week-long
    /// time skip must not emit a week of arrivals.
    std::vector<RoutineReason> step(World& world, const OrderedMap<Routine>& routines,
                                    long long delta_minutes,
                                    const OnArrival& on_arrival = nullptr,
                                    const CarriedMood& carried = nullptr,
                                    const RequestMove& request_move = nullptr) {
        if (delta_minutes <= 0) return {};
        std::vector<RoutineReason> reasons;
        for (Agent* agent : sorted_cast(world)) {
            const Routine* routine = routines.find(agent->id);
            if (!routine || routine->empty()) continue;
            const RoutineBlock* block = routine->block_at(world.world_time);
            if (!block) continue;
            const long long* seen = applied_.find(agent->id);
            if (seen && *seen == block->start && agent->location().py_str() == block->place)
                continue;
            // `_applied` is stamped either way, so a character the engine could
            // not walk is late for THIS block rather than being asked again every
            // tick for the rest of it.
            applied_[agent->id] = block->start;
            if (agent->location().py_str() == block->place) continue;
            const std::string origin = agent->location().py_str();

            if (request_move) {
                MoveRequest asked = request_move(*agent, block->place, origin,
                                                 block->activity, block->start);
                if (asked.bridged) {
                    if (!asked.issued) continue;      // already mid-act
                    Json detail = Json::object();
                    detail["agent"] = agent->id;
                    detail["from"] = origin;
                    detail["to"] = block->place;
                    detail["activity"] = block->activity;
                    detail["intent"] = asked.intent_id;
                    reasons.push_back({"routine.move_requested",
                                       static_cast<double>(block->start), detail});
                    continue;
                }
            }

            for (RoutineReason& row : perform_move(world, *agent, block->place,
                                                   block->activity, block->start,
                                                   on_arrival, carried))
                reasons.push_back(std::move(row));
        }
        return reasons;
    }

    /// Actually relocate a character and let the world notice.
    ///
    /// The one place a routine move happens, so a move an engine confirmed and a
    /// move the runtime made itself are the same event with the same perception,
    /// memory and ledger consequences. Only the moment differs.
    std::vector<RoutineReason> perform_move(World& world, Agent& agent,
                                            const std::string& place,
                                            const std::string& activity = "",
                                            std::optional<long long> start = std::nullopt,
                                            const OnArrival& on_arrival = nullptr,
                                            const CarriedMood& carried = nullptr) {
        const std::string origin = agent.location().py_str();
        agent.set_location(Json(place));
        long long when = start ? *start : world.world_time % MINUTES_PER_DAY;

        std::vector<RoutineReason> travelled;
        if (carried) travelled = carried(origin, place);

        Json detail = Json::object();
        detail["agent"] = agent.id;
        detail["from"] = origin;
        detail["to"] = place;
        detail["activity"] = activity;
        detail["time_of_day"] = clock_string(when);
        std::vector<RoutineReason> reasons = travelled;
        reasons.push_back({"routine.moved", static_cast<double>(when), detail});

        if (params_.emit_events && on_arrival) on_arrival(agent, place, origin, activity);
        return reasons;
    }

    /// Where every character is scheduled to be at a given time.
    ///
    /// The query a detective scene is built on, and the one an author needs to
    /// see whether their cast ever actually meets.
    OrderedMap<std::string> whereabouts(World& world, const OrderedMap<Routine>& routines,
                                        long long world_time) const {
        OrderedMap<std::string> out;
        // Insertion order of the cast, NOT sorted -- unlike `seed` and `step`,
        // which sort. The difference is in the Python and is kept.
        for (const auto& entry : world.agents) {
            const Routine* routine = routines.find(entry.first);
            const RoutineBlock* block = (routine && !routine->empty())
                ? routine->block_at(world_time) : nullptr;
            out[entry.first] = block ? block->place : entry.second.location().py_str();
        }
        return out;
    }

    /// Places where two or more characters coincide over a day.
    ///
    /// An authoring aid and a validation input: a pack whose cast never shares a
    /// place cannot produce a rumour, and that should be visible before
    /// playtesting rather than after.
    OrderedMap<std::vector<std::string>> meeting_opportunities(
            World& world, const OrderedMap<Routine>& routines,
            long long samples = 24) const {
        OrderedMap<std::set<std::string>> found;
        long long step_minutes = std::max(1LL, MINUTES_PER_DAY / std::max(1LL, samples));
        for (long long minute = 0; minute < MINUTES_PER_DAY; minute += step_minutes) {
            OrderedMap<std::vector<std::string>> occupancy;
            for (const auto& entry : whereabouts(world, routines, minute))
                occupancy[entry.second].push_back(entry.first);
            for (const auto& entry : occupancy)
                if (entry.second.size() >= 2)
                    found[entry.first].insert(entry.second.begin(), entry.second.end());
        }
        OrderedMap<std::vector<std::string>> out;
        for (const auto& entry : found)
            out[entry.first] = std::vector<std::string>(entry.second.begin(),
                                                        entry.second.end());
        return out;
    }

private:
    /// `sorted(world.agents.values(), key=lambda a: a.id)`.
    static std::vector<Agent*> sorted_cast(World& world) {
        std::vector<Agent*> cast;
        for (auto& entry : world.agents) cast.push_back(&entry.second);
        std::sort(cast.begin(), cast.end(),
                  [](const Agent* a, const Agent* b) { return a->id < b->id; });
        return cast;
    }

    Params params_;
    /// agent id -> the block start last applied, so a character is moved on a
    /// transition rather than re-placed on every tick.
    ///
    /// UNOBSERVABLE IN THE PORTED SUBSET, and worth saying so rather than
    /// pretending otherwise. Deleting every write to it changes nothing that any
    /// probe case can see: without the action bridge a move always succeeds, and
    /// the check one line below -- "are they already there" -- reaches the same
    /// conclusion. It becomes load-bearing when the bridge lands, because then a
    /// character the engine could not walk must be LATE for this block rather
    /// than asked to walk again on every tick for the rest of it. A mutation
    /// that removes it is not caught, and that is a fact about how much of the
    /// runtime is ported, not a gap in the cases.
    OrderedMap<long long> applied_;
};

}  // namespace usc
