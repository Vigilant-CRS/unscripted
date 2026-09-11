// `usc/common_knowledge.py`. Everybody knowing is not the same as everybody
// knowing that everybody knows.
//
//   private   I know it.
//   mutual    We all know it -- and I have no idea whether you do.
//   common    We all know it, we all know we all know, and so on without end.
//
// Lewis (1969) and Aumann (1976) give the definition; Chwe (2001) gives the
// mechanism, and that is the part a game can use. Common knowledge is NOT
// produced by more people finding out. It is produced by a PUBLIC EVENT -- a
// broadcast, an announcement, something said in the open in front of a crowd --
// because what makes it public is that everybody there can see everybody else
// taking it in. A thing whispered to fifty people one at a time is mutual
// knowledge fifty times over and common knowledge to nobody.
//
// WHY A GAME SHOULD CARE: it decides what can be DONE, not what is believed. A
// scandal everyone privately knows is still deniable -- raising it means being
// the one who raised it. The moment it is common knowledge, denying it stops
// working, and that transition is the difference between a player who has
// learned something and a player who has MADE IT PUBLIC.
//
// WHAT IT DELIBERATELY DOES NOT DO: touch the belief maths. A public event does
// not make anybody surer -- it is one origin, weighed once. Treating publicity
// as evidence would be the same error as treating repetition as proof, and this
// runtime exists partly to not make that error.
//
// It also does not union its groups. Two separate public moments about the same
// fact produce two publics, not one merged crowd: somebody who was in the square
// on Tuesday does not thereby know about the people in the bar on Wednesday.
#pragma once

#include <algorithm>
#include <optional>
#include <set>
#include <string>
#include <vector>

#include "usc/events.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ordered_map.hpp"
#include "usc/world.hpp"
#include "usc/knob.hpp"

namespace usc {

/// How many people must take something in at once before the room counts as a
/// crowd rather than a conversation. Two people talking know that they both
/// know; that is mutual knowledge and it is already what a conversation is.
/// Chwe's argument is about an audience, so three is the smallest honest number.
inline constexpr long long MIN_WITNESSES = 3;

/// A place private enough that what is said in it is not said in the open.
/// Packs already declare `privacy_level`, so no world has to be re-authored.
inline constexpr double PUBLIC_PRIVACY = 0.35;

/// Below this an observer only half caught it, and half catching something is
/// not what a public event means.
inline constexpr double MIN_QUALITY = 0.5;

/// How many distinct publics to keep per fact before the oldest is dropped. A
/// bound rather than a claim: unbounded history here would grow a save file for
/// no gameplay gain.
inline constexpr std::size_t MAX_PUBLICS_PER_KEY = 6;

/// Media through which no crowd can see itself. A call reaches one person and a
/// note reaches one reader, however many people either eventually reaches.
inline bool is_private_medium(const std::string& medium) {
    return medium == "phone" || medium == "note";
}

/// The key a fact is public UNDER, which includes what was actually said.
///
/// Publics used to be filed under the bare core key, so a broadcast that
/// somebody was NOT alive marked the claim that they WERE as out in the open.
/// A bare key normalises to the positive reading, because that is what a pack
/// writes when it declares what a secret protects.
inline std::string public_key(const std::string& core_key,
                              const std::string& polarity = "+") {
    if (!core_key.empty() && (core_key[0] == '+' || core_key[0] == '-')) return core_key;
    return polarity + core_key;
}

/// One crowd, one fact, one moment at which it stopped being deniable.
struct Public {
    std::string key;
    std::set<std::string> members;
    long long since = 0;
    std::string how;
    Json place;

    Json as_json() const {
        Json out = Json::object();
        out["key"] = key;
        Json who = Json::array();
        for (const std::string& one : members) who.push(Json(one));
        out["members"] = who;
        out["since"] = since;
        out["how"] = how;
        out["place"] = place;
        return out;
    }
};

using CommonKnowledgeReason = Reason;

class CommonKnowledgeEngine {
public:
    static constexpr const char* MODULE_ID = "common_knowledge";

    /// The three numbers a world pack may set. Members rather than the
    /// `constexpr` constants above, which cannot be written at run time -- and a
    /// knob that cannot be written is a knob a pack sets in vain. The constants
    /// stay as the defaults, so each value is still stated exactly once.
    struct Params {
        long long min_witnesses = MIN_WITNESSES;
        double public_privacy = PUBLIC_PRIVACY;
        double min_quality = MIN_QUALITY;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("min_witnesses", &Params::min_witnesses),
            knob("public_privacy", &Params::public_privacy),
            knob("min_quality", &Params::min_quality),
        };
        return table;
    }

    CommonKnowledgeEngine() = default;
    explicit CommonKnowledgeEngine(bool enabled) : enabled_(enabled) {}

    const Params& params() const { return params_; }
    Params& params() { return params_; }
    bool enabled() const { return enabled_; }
    void set_enabled(bool on) { enabled_ = on; }

    /// Did this event make something common knowledge, and among whom?
    ///
    /// `learned` is who actually took the claim in, supplied by the perception
    /// loop rather than recomputed here -- so this cannot disagree with what the
    /// rest of the runtime thinks people heard.
    std::vector<CommonKnowledgeReason> observe(
            const World& world, const Event& event,
            const std::vector<std::pair<std::string, double>>& learned) {
        if (!enabled_) return {};
        std::optional<Proposition> proposition = event.proposition();
        // A question NAMES a proposition without asserting it, so it cannot make
        // one undeniable.
        if (!proposition || event.type == "question") return {};

        std::string how = how_public(world, event);
        if (how.empty()) return {};

        std::set<std::string> members;
        for (const auto& one : learned)
            if (one.second >= params_.min_quality) members.insert(one.first);
        // The person who said it is part of the crowd that knows it is out, even
        // though they learned nothing by saying it.
        if (!event.actor.is_null()) {
            std::string actor = event.actor.py_str();
            if (!actor.empty() && world.agents.contains(actor)) members.insert(actor);
        }
        if (static_cast<long long>(members.size()) < params_.min_witnesses) return {};

        Public public_moment;
        const Json* asserted = event.payload.find("asserter_polarity");
        std::string polarity = (asserted && !asserted->is_null())
                             ? asserted->py_str() : proposition->polarity;
        if (polarity.empty()) polarity = proposition->polarity;
        public_moment.key = public_key(proposition->core_key(), polarity);
        public_moment.members = members;
        public_moment.since = event.world_time;
        public_moment.how = how;
        public_moment.place = event.location;
        return record(public_moment);
    }

    /// Is this common knowledge among all of these people AT ONCE?
    ///
    /// One crowd has to contain all of them. Two people who each learned it in
    /// front of a different crowd do not have it in common with each other, and
    /// collapsing that distinction would throw away the only thing this models.
    bool is_common(const std::string& key,
                   const std::vector<std::string>& agent_ids) const {
        if (!enabled_ || agent_ids.empty()) return false;
        const std::vector<Public>* crowds = publics_.find(public_key(key));
        if (!crowds) return false;
        for (const Public& one : *crowds) {
            bool all_present = true;
            for (const std::string& who : agent_ids)
                if (!one.members.count(who)) { all_present = false; break; }
            if (all_present) return true;
        }
        return false;
    }

    /// Is this out in the open in front of a crowd this character belongs to?
    ///
    /// The question a secret-holder asks. Not "does my questioner know" -- that
    /// is what trust is for -- but "is there any point in denying it", and there
    /// is not, once the people around you have all watched each other find out.
    bool is_out(const std::string& key, const std::string& agent_id) const {
        if (!enabled_) return false;
        const std::vector<Public>* crowds = publics_.find(public_key(key));
        if (!crowds) return false;
        for (const Public& one : *crowds) if (one.members.count(agent_id)) return true;
        return false;
    }

    std::vector<Public> publics_for(const std::string& key) const {
        const std::vector<Public>* crowds = publics_.find(public_key(key));
        return crowds ? *crowds : std::vector<Public>();
    }

    /// What a designer wants to see: what can no longer be denied, and to whom.
    Json report() const {
        Json rows = Json::array();
        for (const std::string& key : sorted_keys())
            for (const Public& one : *publics_.find(key)) rows.push(one.as_json());
        return rows;
    }

    Json as_json() const {
        Json out = Json::object();
        out["enabled"] = enabled_;
        Json rows = Json::array();
        for (const std::string& key : sorted_keys())
            for (const Public& one : *publics_.find(key)) rows.push(one.as_json());
        out["publics"] = rows;
        return out;
    }

    void restore(const Json& data) {
        publics_.clear();
        const Json* rows = data.find("publics");
        if (!rows) return;
        for (const Json& row : rows->items()) {
            Public one;
            one.key = row.at("key").py_str();
            for (const Json& who : row.at("members").items()) one.members.insert(who.py_str());
            const Json* since = row.find("since");
            one.since = since ? since->as_int() : 0;
            const Json* how = row.find("how");
            one.how = (how && !how->is_null()) ? how->py_str() : "in_the_open";
            one.place = row.get("place");
            publics_[one.key].push_back(one);
        }
    }

private:
    /// Why this was in the open, or empty if it was not.
    std::string how_public(const World& world, const Event& event) const {
        if (event.type == "broadcast")
            // Chwe's canonical case. Everybody listening knows the others are
            // listening, which is what a broadcast IS -- and why regimes care so
            // much more about a transmitter than about a rumour.
            return "broadcast";

        const Json* medium = event.payload.find("medium");
        if (is_private_medium(medium ? medium->py_str() : "in_person")) return "";

        const Json* place = world.places.find(event.location.py_str());
        double privacy = 0.5;
        if (place && place->kind() == Json::Kind::Object) {
            const Json* declared = place->find("privacy_level");
            if (declared) privacy = declared->as_double();
        }
        if (privacy > params_.public_privacy) return "";
        return "in_the_open";
    }

    std::vector<CommonKnowledgeReason> record(const Public& incoming) {
        // Normalise on the way IN as well as out. `observe` already builds a
        // signed key and `public_key` is idempotent for one, but a caller that
        // hands over a bare core key must be filed where the lookups will look.
        Public fresh = incoming;
        fresh.key = public_key(incoming.key);
        std::vector<Public>& crowds = publics_[fresh.key];
        auto contains = [](const std::set<std::string>& small,
                           const std::set<std::string>& big) {
            return std::includes(big.begin(), big.end(), small.begin(), small.end());
        };
        // Already established in front of these people or more of them.
        for (const Public& existing : crowds)
            if (contains(fresh.members, existing.members)) return {};
        // A larger crowd absorbs the smaller ones it contains: those people were
        // there for this too, and keeping both would count one moment twice.
        crowds.erase(std::remove_if(crowds.begin(), crowds.end(),
                                    [&](const Public& one) {
                                        return contains(one.members, fresh.members);
                                    }),
                     crowds.end());
        crowds.push_back(fresh);
        // `del crowds[:-MAX]` -- drop the OLDEST, keeping the newest six.
        if (crowds.size() > MAX_PUBLICS_PER_KEY)
            crowds.erase(crowds.begin(), crowds.end() - MAX_PUBLICS_PER_KEY);

        Json detail = Json::object();
        detail["proposition"] = fresh.key;
        detail["how"] = fresh.how;
        detail["place"] = fresh.place;
        Json who = Json::array();
        for (const std::string& one : fresh.members) who.push(Json(one));
        detail["members"] = who;
        detail["note"] = std::string(
            "not more evidence -- it is now undeniable in front of these people");
        return {{"common_knowledge.established",
                 static_cast<double>(fresh.members.size()), detail}};
    }

    std::vector<std::string> sorted_keys() const {
        std::vector<std::string> keys;
        for (const auto& entry : publics_) keys.push_back(entry.first);
        std::sort(keys.begin(), keys.end());
        return keys;
    }

    bool enabled_ = false;
    Params params_;
    /// fact key -> the crowds in front of which it has been established.
    OrderedMap<std::vector<Public>> publics_;
};

}  // namespace usc
