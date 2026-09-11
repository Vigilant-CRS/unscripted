// `usc/notes.py`. A claim that outlives the conversation, and can be read by the
// wrong person.
//
// `medium.hpp` has described three ways of saying something since it was
// written, and only two of them ever happened. `note` sat in the table with its
// numbers and nothing produced one.
//
// It is worth producing, because a note is NOT a slower phone call. It differs
// in one way no other channel does: a conversation is gone the moment it ends,
// and a note is still there. So it can be found by somebody it was not written
// for, which makes it the runtime's first piece of EVIDENCE rather than
// testimony -- a claim with an author attached that the author cannot take back.
//
// WHERE THE DETAIL IS LOST. On a phone the levelling happens in the telling, so
// distortion runs at the moment of the exchange. A note is the other way round:
// whatever is going to be lost is lost when it is WRITTEN -- the tone, the
// hesitation, the thing the author decided not to put in writing -- and after
// that the words are fixed. So this distorts once, at `leave`, and reading is
// faithful. A note that says the wrong thing goes on saying exactly the wrong
// thing to everybody who reads it, which is the difference between a rumour and
// a document.
#pragma once

#include <algorithm>
#include <functional>
#include <set>
#include <string>
#include <vector>

#include "usc/agent.hpp"
#include "usc/belief.hpp"
#include "usc/content.hpp"
#include "usc/determinism.hpp"
#include "usc/distortion.hpp"
#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/medium.hpp"
#include "usc/pyround.hpp"
#include "usc/world.hpp"
#include "usc/knob.hpp"

namespace usc {

/// How many unread notes one place holds before the oldest is thrown out. A
/// bound on save size, not a claim about how many notes a bar can hold.
inline constexpr std::size_t MAX_NOTES_PER_PLACE = 12;

/// How long an unread note stays where it was left. Five days: long enough to
/// cross a routine, short enough that a world does not silt up with messages
/// nobody ever came for.
inline constexpr long long NOTE_LIFETIME_MINUTES = 5 * 24 * 60;

/// The chance per hour that somebody it was NOT written for notices it anyway,
/// before their own curiosity. Deliberately low, and capped at one interception
/// per note: a note everybody reads is a poster. At the first value tried, more
/// notes were intercepted than delivered over a week, which made being read by a
/// stranger the normal fate of a letter rather than the thing that goes wrong.
inline constexpr double INTERCEPT_BASE = 0.02;

struct Note {
    std::string note_id;
    std::string author;
    std::string intended_for;
    std::string place;
    std::string key;
    Proposition proposition;
    std::string polarity;
    std::string origin;
    long long hops = 0;
    long long written_at = 0;
    Json distorted_as;
    std::vector<std::string> read_by;

    Json as_json() const {
        Json out = Json::object();
        out["note_id"] = note_id;
        out["author"] = author;
        out["intended_for"] = intended_for;
        out["place"] = place;
        out["key"] = key;
        out["proposition"] = proposition.as_json();
        out["polarity"] = polarity;
        out["origin"] = origin;
        out["hops"] = hops;
        out["written_at"] = written_at;
        out["distorted_as"] = distorted_as;
        Json readers = Json::array();
        for (const std::string& one : read_by) readers.push(Json(one));
        out["read_by"] = readers;
        return out;
    }
};

using NoteReason = Reason;

/// What the board needs from the rest of the runtime.
struct NoteRuntime {
    /// The diffusion engine's fidelity decay, so a note loses conviction along
    /// the same curve a retelling does.
    double fidelity_decay = 0.80;
    std::function<void(const Event&)> process_event;
    const OrderedMap<Routine>* routines = nullptr;
};

class NoteBoard {
public:
    static constexpr const char* MODULE_ID = "notes";

    /// The three numbers a world pack may set, held as MEMBERS rather than as
    /// the constants above -- a `constexpr` cannot be written at run time, and
    /// a knob that cannot be written is a knob a pack sets in vain. The
    /// constants remain, as the defaults, so the value is still stated once.
    struct Params {
        long long max_per_place = static_cast<long long>(MAX_NOTES_PER_PLACE);
        long long lifetime_minutes = NOTE_LIFETIME_MINUTES;
        double intercept_base = INTERCEPT_BASE;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("max_per_place", &Params::max_per_place),
            knob("lifetime_minutes", &Params::lifetime_minutes),
            knob("intercept_base", &Params::intercept_base),
        };
        return table;
    }

    NoteBoard() = default;
    explicit NoteBoard(bool enabled) : enabled_(enabled) {}

    const Params& params() const { return params_; }
    Params& params() { return params_; }
    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }

    /// Write it down and leave it here, for somebody who is not here.
    ///
    /// Returns false when the layer is off, so a caller can ask unconditionally.
    bool leave(const World& world, const Agent& author, const std::string& intended_for,
               const std::string& place_id, const std::string& key,
               const Belief* belief, const NoteRuntime& runtime,
               std::vector<NoteReason>& reasons) {
        if (!enabled_ || !belief) return false;

        Proposition proposition = belief->proposition;
        std::string polarity = belief->expected_prob() >= 0.5 ? "+" : "-";
        Json distorted_as;

        // What is lost is lost in the writing -- same layer, same rates as any
        // retelling, scaled by how much this medium carries.
        std::vector<std::uint8_t> seed = derive_seed(
            world.global_seed, author.id, intended_for, world.world_time,
            MODULE_ID, "write");
        if (seeded_uniform(seed) < 0.18 * note().distortion_scale()) {
            std::vector<Secret> secrets;
            for (const Json& row : author.secrets) secrets.push_back(Secret::from_json(row));
            const std::set<std::string> protect = protected_keys(secrets);
            const Routine* routine = runtime.routines
                ? runtime.routines->find(author.id) : nullptr;
            auto outcome = distort(
                proposition, author, world,
                derive_seed(world.global_seed, author.id, intended_for,
                            world.world_time, MODULE_ID, "kind"),
                nullptr, std::vector<std::string>(protect.begin(), protect.end()),
                routine);
            if (outcome) {
                proposition = outcome->proposition;
                distorted_as = Json(outcome->kind);
                if (outcome->kind == INVERSION) polarity = polarity == "+" ? "-" : "+";
            }
        }

        ++counter_;
        Note written;
        written.note_id = "note_" + std::to_string(counter_);
        written.author = author.id;
        written.intended_for = intended_for;
        written.place = place_id;
        written.key = key;
        written.proposition = proposition;
        written.polarity = polarity;
        const std::string* primary = belief->primary_origin();
        written.origin = primary ? *primary : ("origin:" + author.id + ":" + key);
        written.hops = belief->hops + 1;
        written.written_at = world.world_time;
        written.distorted_as = distorted_as;

        std::vector<Note>& pile = by_place_[place_id];
        pile.push_back(written);
        // `del pile[:-MAX]` -- the oldest go.
        // `check` refuses anything below 1, and Python's `del pile[:-n]` with
        // n == 0 deletes NOTHING rather than everything. Doing nothing here is
        // what Python does for the one out-of-range value that could reach it.
        if (params_.max_per_place > 0) {
            const std::size_t cap = static_cast<std::size_t>(params_.max_per_place);
            if (pile.size() > cap)
                pile.erase(pile.begin(),
                           pile.end() - static_cast<std::ptrdiff_t>(cap));
        }

        Json detail = Json::object();
        detail["author"] = author.id;
        detail["for"] = intended_for;
        detail["place"] = place_id;
        detail["proposition"] = proposition.str();
        detail["distorted"] = distorted_as;
        detail["note"] = std::string(
            "could not reach them; left word where they were standing");
        reasons.push_back({"note.left", 1.0, detail});
        return true;
    }

    /// Whoever is standing where a note was left may pick it up.
    std::vector<NoteReason> step(World& world, const NoteRuntime& runtime,
                                 long long delta_minutes) {
        if (!enabled_ || delta_minutes <= 0) return {};
        double hours = std::max(1.0, static_cast<double>(delta_minutes) / 60.0);
        std::vector<NoteReason> reasons;

        OrderedMap<std::vector<Agent*>> here;
        for (auto& entry : world.agents) {
            // `if agent.location:` -- truthiness.
            if (entry.second.location().is_null()
                || entry.second.location().py_str().empty()) continue;
            here[entry.second.location().py_str()].push_back(&entry.second);
        }

        for (const std::string& place_id : sorted_places()) {
            std::vector<Note>& pile = by_place_[place_id];
            std::vector<Agent*> occupants;
            if (const std::vector<Agent*>* found = here.find(place_id)) occupants = *found;
            std::sort(occupants.begin(), occupants.end(),
                      [](const Agent* a, const Agent* b) { return a->id < b->id; });

            std::vector<Note> keep;
            for (Note& one : pile) {
                if (world.world_time - one.written_at > params_.lifetime_minutes) {
                    Json detail = Json::object();
                    detail["note"] = one.note_id;
                    detail["author"] = one.author;
                    detail["for"] = one.intended_for;
                    detail["place"] = place_id;
                    detail["note_text"] = std::string("nobody ever came for it");
                    reasons.push_back({"note.went_unread", 0.0, detail});
                    continue;
                }
                bool taken = false;
                for (Agent* reader : occupants) {
                    if (reader->id == one.author) continue;
                    if (std::find(one.read_by.begin(), one.read_by.end(), reader->id)
                        != one.read_by.end()) continue;
                    bool intended = reader->id == one.intended_for;
                    if (!intended) {
                        // Once somebody has nosed at it, it has been seen. A
                        // second and third stranger reading the same note adds
                        // nothing a game can use and multiplies one slip into a
                        // broadcast.
                        if (!one.read_by.empty()) continue;
                        if (!notices(world, *reader, one, hours)) continue;
                    }
                    deliver(world, runtime, *reader, one, place_id, intended, reasons);
                    one.read_by.push_back(reader->id);
                    if (intended) {
                        // It was for them; they take it with them. An
                        // interceptor reads it and puts it back, which is what
                        // makes a note worth intercepting more than once.
                        taken = true;
                        break;
                    }
                }
                if (!taken) keep.push_back(one);
            }
            by_place_[place_id] = keep;
        }
        return reasons;
    }

    std::vector<Note> at(const std::string& place_id) const {
        const std::vector<Note>* found = by_place_.find(place_id);
        return found ? *found : std::vector<Note>();
    }

    Json report() const {
        Json rows = Json::array();
        for (const std::string& place_id : sorted_places())
            for (const Note& one : *by_place_.find(place_id)) rows.push(one.as_json());
        return rows;
    }

    Json as_json() const {
        Json out = Json::object();
        out["enabled"] = enabled_;
        out["counter"] = counter_;
        out["notes"] = report();
        return out;
    }

    void restore(const Json& data) {
        by_place_.clear();
        const Json* counter = data.find("counter");
        counter_ = counter ? counter->as_int() : 0;
        for (const Json& row : data.at("notes").items()) {
            Note one;
            one.note_id = row.at("note_id").py_str();
            one.author = row.at("author").py_str();
            one.intended_for = row.at("intended_for").py_str();
            one.place = row.at("place").py_str();
            one.key = row.at("key").py_str();
            one.proposition = Proposition::from_json(row.at("proposition"));
            const Json* polarity = row.find("polarity");
            one.polarity = (polarity && !polarity->is_null()) ? polarity->py_str() : "+";
            const Json* origin = row.find("origin");
            one.origin = (origin && !origin->is_null()) ? origin->py_str() : "";
            const Json* hops = row.find("hops");
            one.hops = hops ? hops->as_int() : 1;
            const Json* when = row.find("written_at");
            one.written_at = when ? when->as_int() : 0;
            one.distorted_as = row.get("distorted_as");
            for (const Json& who : row.at("read_by").items())
                one.read_by.push_back(who.py_str());
            by_place_[one.place].push_back(one);
        }
    }

private:
    /// Does somebody it was not written for spot it?
    bool notices(const World& world, const Agent& reader, const Note& one,
                 double hours) const {
        double chance = params_.intercept_base * hours * (0.5 + reader.trait("curiosity"));
        std::vector<std::uint8_t> seed = derive_seed(
            world.global_seed, reader.id, one.note_id, world.world_time,
            MODULE_ID, "notice");
        return seeded_uniform(seed) < std::min(0.6, chance);
    }

    /// A read note is an ordinary claim, through the ordinary path.
    ///
    /// No new belief mechanism: it carries the author's origin and hop count, it
    /// is weighed at the medium's trust factor, and nobody overhears it. The one
    /// thing it does that no conversation can is arrive with its author's name
    /// on it when the author is not there to be asked about it.
    void deliver(World& world, const NoteRuntime& runtime, const Agent& reader,
                 const Note& one, const std::string& place_id, bool intended,
                 std::vector<NoteReason>& reasons) {
        double strength = std::pow(runtime.fidelity_decay, static_cast<double>(one.hops))
                        * note().trust_factor;

        Json payload = Json::object();
        payload["proposition"] = one.proposition.as_json();
        payload["asserter_polarity"] = one.polarity;
        payload["origin_event"] = one.origin;
        payload["summary"] = "a note from " + one.author;
        payload["importance"] = 0.35;
        payload["domain"] = std::string("gossip");
        // Nobody overhears a note being read, and the perception layer must not
        // put the author in the room: they are not here.
        Json audience = Json::array();
        audience.push(Json(reader.id));
        payload["audience"] = audience;
        payload["medium"] = std::string("note");
        Json trace = Json::object();
        trace["speaker"] = one.author;
        trace["listener"] = reader.id;
        trace["hops"] = one.hops;
        trace["distorted"] = !one.distorted_as.is_null();
        trace["distortion_kind"] = one.distorted_as;
        trace["distortion_detail"] = Json::object();
        trace["fidelity"] = py_round(strength, 4);
        payload["diffusion"] = trace;
        payload["assertion_strength"] = py_round(strength, 4);

        Event event;
        event.event_id = world.new_event_id();
        event.world_time = world.world_time;
        event.type = "claim";
        event.actor = Json(one.author);
        event.location = Json(place_id);
        event.payload = payload;
        if (runtime.process_event) runtime.process_event(event);

        Json detail = Json::object();
        detail["reader"] = reader.id;
        detail["author"] = one.author;
        detail["for"] = one.intended_for;
        detail["place"] = place_id;
        detail["proposition"] = one.proposition.str();
        detail["origin"] = one.origin;
        detail["note"] = intended
            ? std::string("read by the person it was for")
            : std::string("read by somebody it was not written for, and left "
                          "where it was");
        reasons.push_back({intended ? "note.read" : "note.intercepted",
                           static_cast<double>(one.hops), detail});
    }

    std::vector<std::string> sorted_places() const {
        std::vector<std::string> names;
        for (const auto& entry : by_place_) names.push_back(entry.first);
        std::sort(names.begin(), names.end());
        return names;
    }

    bool enabled_ = false;
    Params params_;
    OrderedMap<std::vector<Note>> by_place_;
    long long counter_ = 0;
};

}  // namespace usc
