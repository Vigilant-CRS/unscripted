// `usc/memory.py`. ACT-R base-level activation, cue-based retrieval, capacity
// consolidation, and the judgements drawn out of what is about to be forgotten.
//
// EVERY SORT IN THIS FILE IS STABLE, and that is not a style choice. Python's
// `list.sort` is stable and `std::sort` is not, so on any tie -- two memories of
// equal activation, two of equal importance -- `std::sort` picks an order that
// depends on the implementation and the input length. In `retrieve` that decides
// which memory a character brings up. In `_consolidate` it decides which one is
// destroyed. Both are the kind of divergence that reproduces on one machine and
// not another, and neither would be traced back to a comparator.
//
// `sort(reverse=True)` is stable too: equal elements keep their original order
// rather than being reversed. So it is `stable_sort` with a strict `>`, not
// `stable_sort` ascending followed by a reverse.
#pragma once

#include <algorithm>
#include <cmath>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/determinism.hpp"
#include "usc/ontology.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pyround.hpp"
#include "usc/pysum.hpp"
#include "usc/types.hpp"
#include "usc/knob.hpp"

namespace usc {

/// Type-specific decay. A conclusion drawn from many occasions outlasts any one
/// of them -- which is the point of forming it: the episodes fade, the pattern
/// stays.
inline double decay_for_type(const std::string& type) {
    if (type == "judgement")  return 0.28;
    if (type == "episodic")   return 0.55;
    if (type == "semantic")   return 0.40;
    if (type == "commitment") return 0.30;
    if (type == "emotional")  return 0.25;
    if (type == "summary")    return 0.35;
    if (type == "social")     return 0.40;
    return 0.5;
}

struct MemoryItem {
    std::string memory_id;
    std::string owner;
    std::string type;
    std::string content;
    std::optional<Proposition> proposition;
    double importance = 0.5;
    double emotional_valence = 0.0;
    std::vector<long long> presentations;      // world_times of encode/recall
    Json last_recalled;
    double source_conf = 1.0;
    Json world_time;
    /// For a summary: how many original episodes it stands for. Merging sums
    /// these, so "a lot happened that week" keeps an honest count however often
    /// memory has been compressed.
    long long episodes = 1;
    /// For a judgement: who it is about, and which episodes it came from. A
    /// conclusion that cannot name its evidence is a prejudice, so the pointers
    /// outlive the episodes.
    std::vector<std::string> about;
    std::vector<std::string> evidence;

    /// ACT-R base-level activation, in HOURS, with important things fading
    /// slower.
    ///
    /// Two corrections over the textbook form, both found by watching a long run
    /// rather than by reading the formula. World time is in minutes, and feeding
    /// minutes into a power law put a once-seen memory below threshold after
    /// thirty of them -- a character forgot a murder before the player left the
    /// room. And importance had no effect on recall at all: a witnessed killing
    /// at 0.95 decayed exactly like a passer-by at 0.05. Important things get
    /// rehearsed, so importance slows the exponent rather than adding a one-off
    /// bonus: it changes how long something lasts, not how loudly it scores once.
    double base_activation(long long now, double eps = 1.0,
                           double time_scale = 60.0,
                           double importance_slows_decay = 0.6) const {
        double decay = decay_for_type(type);
        decay *= std::max(0.05, 1.0 - importance_slows_decay
                                      * std::max(0.0, std::min(1.0, importance)));
        double total = 0.0;
        for (long long when : presentations) {
            double gap = std::max(eps, static_cast<double>(now - when)
                                       / std::max(1e-9, time_scale) + eps);
            total += std::pow(gap, -decay);
        }
        if (total <= 0.0) return -10.0;
        return std::log(total);
    }

    /// Restore a saved memory. Every field that influences future activation
    /// round-trips, or a restored save drifts from the session it came from.
    static MemoryItem from_json(const Json& doc, const std::string& owner = "") {
        MemoryItem out;
        out.memory_id = doc.get("memory_id").as_string();
        out.owner = owner.empty() ? doc.get("owner").as_string() : owner;
        out.type = doc.get("type").as_string();
        out.content = doc.get("content").as_string();
        const Json& proposition = doc.at("proposition");
        if (!proposition.is_null()) out.proposition = Proposition::from_json(proposition);
        out.importance = doc.get("importance").as_double();
        out.emotional_valence = doc.get("emotional_valence").as_double();
        for (const Json& when : doc.at("presentations").items())
            out.presentations.push_back(when.as_int());
        out.last_recalled = doc.get("last_recalled");
        const Json* confidence = doc.find("source_conf");
        out.source_conf = confidence ? confidence->as_double(1.0) : 1.0;
        out.world_time = doc.get("world_time");
        const Json* episodes = doc.find("episodes");
        out.episodes = episodes ? episodes->as_int(1) : 1;
        const Json* about_doc = doc.find("about");
        if (about_doc && !about_doc->is_null())
            for (const Json& part : about_doc->items()) out.about.push_back(part.py_str());
        const Json* evidence_doc = doc.find("evidence");
        if (evidence_doc && !evidence_doc->is_null())
            for (const Json& part : evidence_doc->items()) out.evidence.push_back(part.py_str());
        return out;
    }

    Json as_json(const Json& now = Json()) const {
        Json out = Json::object();
        out["memory_id"] = memory_id;
        out["owner"] = owner;
        out["type"] = type;
        out["content"] = content;
        out["importance"] = importance;
        out["emotional_valence"] = emotional_valence;
        out["source_conf"] = source_conf;
        Json seen = Json::array();
        for (long long when : presentations) seen.push(Json(when));
        out["presentations"] = seen;
        out["last_recalled"] = last_recalled;
        out["world_time"] = world_time;
        out["episodes"] = episodes;
        // A judgement without these is a prejudice: `about` is who it concerns
        // and `evidence` names the occasions it was drawn from. They were absent
        // from the record entirely, so save/load turned every conclusion a
        // character had reached into an unattributed sentence -- and
        // consolidation, which finds an existing judgement BY `about`, stopped
        // finding it and started making duplicates.
        Json about_out = Json::array();
        for (const std::string& part : about) about_out.push(Json(part));
        out["about"] = about_out;
        Json evidence_out = Json::array();
        for (const std::string& part : evidence) evidence_out.push(Json(part));
        out["evidence"] = evidence_out;
        out["proposition"] = proposition ? proposition->as_json() : Json();
        if (!now.is_null()) out["activation"] = base_activation(now.as_int());
        return out;
    }
};

/// A memory list, modelled the way Python's is: a list of REFERENCES.
///
/// Not `std::vector<MemoryItem>`. Consolidation appends a summary and a
/// judgement while still holding on to the memories that are about to be
/// dropped, and appending to a vector moves its elements -- so every one of
/// those handles would dangle. In Python that cannot happen, because a list
/// holds references and appending to it does not move the objects. This is the
/// same shape, and it is the reason the first draft of this file was wrong.
using MemoryList = std::vector<std::shared_ptr<MemoryItem>>;

using MemoryReason = Reason;

/// One retrieved memory: its activation, the probability it came back, and which.
struct Retrieved {
    double activation = 0.0;
    double probability = 0.0;
    std::shared_ptr<MemoryItem> memory;
};

class MemoryEngine {
public:
    struct Params {
        /// Was 0.0, which with the corrected time scale meant "anything older
        /// than an hour is gone". -1.5 gives trivia a few hours and something
        /// important weeks.
        double tau_ret = -1.5;
        double noise_s = 0.4;
        long long working_cap = 7;
        double w_topic = 1.0;
        double w_goal = 0.6;
        double w_emotion = 0.5;
        double w_mood_congruence = 0.3;
        long long episodic_cap = 200;
        double interference = 0.3;
        /// Every recall used to append a timestamp forever -- 301 entries after
        /// 300 retrievals, walked by activation and by every save. Old
        /// presentations contribute dt^-d, negligible beside recent ones, so a
        /// rolling window is bounded and faithful.
        long long presentation_window = 32;
        /// Non-episodic memory was uncapped entirely.
        long long total_cap = 600;
        /// Summaries are memories too. Excluding them from consolidation to
        /// avoid compounding loss created an unbounded path instead: one summary
        /// per tick, forever. 1,905 stored against a cap of 600 after 173
        /// simulated days, 1,595 of them summaries.
        long long summary_cap = 40;
    };

    /// Every knob a world pack may set, in the order Python's `params`
    /// dictionary declares them -- insertion order is load-bearing here, and
    /// a table that reorders them exports a different state. A probe holds
    /// this list to the live Python dictionary, name for name and value for
    /// value, so a parameter added above and forgotten here fails a test
    /// rather than becoming a knob that silently does nothing.
    static const std::vector<Knob<Params>>& knobs() {
        static const std::vector<Knob<Params>> table = {
            knob("tau_ret", &Params::tau_ret),
            knob("noise_s", &Params::noise_s),
            knob("working_cap", &Params::working_cap),
            knob("w_topic", &Params::w_topic),
            knob("w_goal", &Params::w_goal),
            knob("w_emotion", &Params::w_emotion),
            knob("w_mood_congruence", &Params::w_mood_congruence),
            knob("episodic_cap", &Params::episodic_cap),
            knob("interference", &Params::interference),
            knob("presentation_window", &Params::presentation_window),
            knob("total_cap", &Params::total_cap),
            knob("summary_cap", &Params::summary_cap),
        };
        return table;
    }

    /// How many occasions before a pattern is worth concluding anything from.
    /// Two is coincidence.
    static constexpr int JUDGEMENT_THRESHOLD = 3;

    MemoryEngine() = default;
    explicit MemoryEngine(const Params& params) : params_(params) {}
    const Params& params() const { return params_; }
    Params& params() { return params_; }

    std::vector<MemoryReason> encode(MemoryList& memories,
                                     std::shared_ptr<MemoryItem> item,
                                     long long world_time) const {
        note_presentation(*item, world_time);
        item->world_time = Json(world_time);
        Json detail = Json::object();
        detail["content"] = item->content;
        detail["type"] = item->type;
        double importance = item->importance;
        memories.push_back(std::move(item));
        return {{"memory.encoded", importance, detail}};
    }

    void reinforce(MemoryItem& item, long long world_time) const {
        note_presentation(item, world_time);
        item.last_recalled = Json(world_time);
    }

    /// Everything above the retrieval threshold, ranked, capped to working
    /// memory.
    /// RETRIEVAL IS A DRAW, NOT A THRESHOLD. `sigmoid((a - tau)/noise) >= 0.5`
    /// is exactly `a >= tau` for any positive noise, so the parameter moved the
    /// number that was reported and never the decision. `seed_parts` supplies
    /// the runtime's own seed algebra; empty keeps the old threshold, for an
    /// engine used with no world around it.
    std::vector<Retrieved> retrieve(MemoryList& memories, long long now,
                                    const std::vector<Proposition>& topics = {},
                                    double mood_valence = 0.0,
                                    const std::vector<std::string>& seed_parts = {}) const {
        std::vector<std::pair<double, std::shared_ptr<MemoryItem>>> scored;
        scored.reserve(memories.size());
        for (const std::shared_ptr<MemoryItem>& handle : memories) {
            MemoryItem& item = *handle;
            double activation = item.base_activation(now);
            if (!topics.empty()) {
                // `max(..., default=0.0)` over a generator that skips memories
                // without a proposition.
                double best = 0.0;
                bool any = false;
                if (item.proposition) {
                    for (const Proposition& topic : topics) {
                        double score = relevance(*item.proposition, topic);
                        if (!any || score > best) { best = score; any = true; }
                    }
                }
                if (!any) best = 0.0;
                activation += params_.w_topic * std::log(1 + best);
            }
            activation += params_.w_emotion * std::fabs(item.emotional_valence);
            activation += params_.w_mood_congruence * mood_valence
                        * (item.emotional_valence >= 0 ? 1 : -1);
            scored.emplace_back(activation, handle);
        }

        // Stable, descending. See the note at the top of this file.
        std::stable_sort(scored.begin(), scored.end(),
                         [](const auto& a, const auto& b) { return a.first > b.first; });

        std::vector<Retrieved> out;
        for (const auto& entry : scored) {
            double probability = sigmoid((entry.first - params_.tau_ret) / params_.noise_s);
            bool came_up;
            if (seed_parts.empty()) {
                came_up = probability >= 0.5;
            } else {
                // Python builds `(*seed_parts, t, module_id, memory_id)[:6]`
                // and hands it to `derive_seed`, which interpolates every slot
                // as a string. `derive_seed_parts` is the spelling that does
                // that without converting anything on the way.
                std::vector<std::string> parts = seed_parts;
                parts.push_back(std::to_string(now));
                parts.push_back("memory");
                parts.push_back(entry.second->memory_id);
                parts.resize(6);
                came_up = seeded_uniform(derive_seed_parts(
                              parts[0], parts[1], parts[2],
                              parts[3], parts[4], parts[5]))
                        < probability;
            }
            bool cue_dependent = !topics.empty() && entry.first > params_.tau_ret - 1.0;
            if (came_up || cue_dependent) {
                if (!(entry.second->last_recalled.is_number()
                      && entry.second->last_recalled.as_int() == now))
                    reinforce(*entry.second, now);      // retrieval strengthens
                out.push_back({py_round(entry.first, 3), py_round(probability, 3),
                               entry.second});
            }
            if (static_cast<long long>(out.size()) >= params_.working_cap) break;
        }
        return out;
    }

    /// Enforce the caps by consolidating the least important, least active
    /// memories into a summary.
    std::vector<MemoryReason> decay_and_consolidate(MemoryList& memories,
                                                    long long now) const {
        std::vector<MemoryReason> reasons;
        auto pool_of = [&](auto predicate) {
            MemoryList pool;
            for (const std::shared_ptr<MemoryItem>& item : memories)
                if (predicate(*item)) pool.push_back(item);
            return pool;
        };
        auto episodic = pool_of([](const MemoryItem& m) { return m.type == "episodic"; });
        append(reasons, consolidate(memories, now, episodic, params_.episodic_cap, "episodic"));
        if (params_.total_cap) {
            auto everything = pool_of([](const MemoryItem& m) { return m.type != "summary"; });
            append(reasons, consolidate(memories, now, everything, params_.total_cap, "total"));
        }
        if (params_.summary_cap) {
            auto summaries = pool_of([](const MemoryItem& m) { return m.type == "summary"; });
            append(reasons, consolidate(memories, now, summaries, params_.summary_cap, "summary"));
        }
        return reasons;
    }

private:
    static void append(std::vector<MemoryReason>& into, std::vector<MemoryReason> more) {
        for (auto& row : more) into.push_back(std::move(row));
    }

    void note_presentation(MemoryItem& item, long long world_time) const {
        item.presentations.push_back(world_time);
        long long window = params_.presentation_window;
        if (window > 0 && static_cast<long long>(item.presentations.size()) > window) {
            // Keep the most recent, which dominate the sum.
            item.presentations.erase(
                item.presentations.begin(),
                item.presentations.end() - static_cast<std::size_t>(window));
        }
    }

    std::vector<MemoryReason> consolidate(MemoryList& memories, long long now,
                                          MemoryList& pool, long long cap,
                                          const std::string& scope) const {
        if (cap <= 0 || static_cast<long long>(pool.size()) <= cap) return {};

        // Ascending by (importance, activation), stable. The least important and
        // least active go first.
        std::stable_sort(pool.begin(), pool.end(),
                         [&](const std::shared_ptr<MemoryItem>& a,
                             const std::shared_ptr<MemoryItem>& b) {
                             if (a->importance != b->importance)
                                 return a->importance < b->importance;
                             return a->base_activation(now) < b->base_activation(now);
                         });
        MemoryList dropping(pool.begin(),
                            pool.begin() + (pool.size() - static_cast<std::size_t>(cap)));
        if (dropping.empty()) return {};

        // Before the detail goes, take what it was evidence FOR. Nine tenths of
        // memory loss in a long run is capacity eviction, and evicting episodes
        // without drawing anything from them means a character can live through
        // the same thing fifty times and conclude nothing.
        std::vector<MemoryReason> reasons = form_judgements(memories, dropping, now);

        long long episodes = 0;
        for (const auto& item : dropping) episodes += item->episodes;

        // The id embeds `len(memories)` AT THIS MOMENT -- after the judgements
        // above have been appended and before the summary is. Recomputing it
        // later from a different length is how a port produces a summary whose
        // name nobody can match to the reason trace that announced it.
        auto summary = std::make_shared<MemoryItem>();
        summary->memory_id = "sum_" + scope + "_" + std::to_string(now) + "_"
                           + std::to_string(memories.size());
        summary->owner = dropping.front()->owner;
        summary->type = "summary";
        summary->content = "(a blur of " + std::to_string(episodes) + " minor moments)";
        summary->importance = 0.3;
        summary->world_time = Json(now);
        summary->presentations = {now};
        summary->episodes = episodes;
        const std::string summary_id = summary->memory_id;

        Json dropped_ids = Json::array();
        for (const auto& item : dropping) dropped_ids.push(Json(item->memory_id));

        memories.push_back(summary);
        for (const auto& doomed : dropping) {
            // `list.remove(m)` removes the first element equal to it -- by
            // identity here, since these are the same objects.
            auto found = std::find(memories.begin(), memories.end(), doomed);
            if (found != memories.end()) memories.erase(found);
        }

        Json detail = Json::object();
        detail["summary"] = summary_id;
        detail["scope"] = scope;
        detail["episodes"] = episodes;
        detail["dropped_ids"] = dropped_ids;
        reasons.push_back({"memory.consolidated",
                           static_cast<double>(dropping.size()), detail});
        return reasons;
    }

    /// Draw what repeats out of what is about to be forgotten.
    ///
    /// The pattern is deliberately narrow: the same predicate, about the same
    /// person, on several separate occasions. That is the shape a character
    /// actually generalises from -- "he keeps doing this" -- and the only one
    /// that can be stated without inventing anything.
    std::vector<MemoryReason> form_judgements(MemoryList& memories,
                                              const MemoryList& expiring,
                                              long long now) const {
        // `sorted(groups.items())` sorts by the (subject, predicate) tuple, so a
        // plain ordered map on that pair is the right container here -- unlike
        // almost everywhere else in this port.
        std::map<std::pair<std::string, std::string>, MemoryList> groups;
        for (const std::shared_ptr<MemoryItem>& item : expiring) {
            if (!item->proposition) continue;
            for (const auto& slot : item->proposition->slots) {
                std::string subject = slot.second.py_str();
                if (subject.rfind("agent:", 0) != 0) continue;
                if (subject == item->owner) continue;
                groups[{subject, item->proposition->predicate}].push_back(item);
            }
        }

        std::vector<MemoryReason> reasons;
        for (const auto& group : groups) {
            const std::string& subject = group.first.first;
            const std::string& predicate = group.first.second;
            const MemoryList& occasions = group.second;
            if (static_cast<int>(occasions.size()) < JUDGEMENT_THRESHOLD) continue;

            PySum valence_sum;
            for (const auto& item : occasions) valence_sum.add(item->emotional_valence);
            double valence = valence_sum.value() / static_cast<double>(occasions.size());

            MemoryList strongest = occasions;
            std::stable_sort(strongest.begin(), strongest.end(),
                             [](const std::shared_ptr<MemoryItem>& a,
                                const std::shared_ptr<MemoryItem>& b) {
                                 return -a->importance < -b->importance;
                             });
            if (strongest.size() > 5) strongest.resize(5);

            std::shared_ptr<MemoryItem> existing;
            for (const std::shared_ptr<MemoryItem>& item : memories) {
                if (item->type != "judgement") continue;
                if (item->about.size() == 2 && item->about[0] == subject
                    && item->about[1] == predicate) { existing = item; break; }
            }

            if (existing) {
                // A pattern that keeps recurring gets firmer, not duplicated.
                existing->episodes += static_cast<long long>(occasions.size());
                existing->importance = std::min(0.95, existing->importance + 0.05);
                existing->emotional_valence = (existing->emotional_valence + valence) / 2.0;
                std::vector<std::string> kept;
                std::size_t keep_from = existing->evidence.size() > 4
                                      ? existing->evidence.size() - 4 : 0;
                for (std::size_t i = keep_from; i < existing->evidence.size(); ++i)
                    kept.push_back(existing->evidence[i]);
                for (std::size_t i = 0; i < strongest.size() && i < 2; ++i)
                    kept.push_back(strongest[i]->memory_id);
                existing->evidence = kept;
                note_presentation(*existing, now);

                Json detail = Json::object();
                detail["about"] = subject;
                detail["pattern"] = predicate;
                detail["occasions"] = existing->episodes;
                detail["content"] = existing->content;
                reasons.push_back({"memory.judgement_reinforced",
                                   static_cast<double>(existing->episodes), detail});
                continue;
            }

            std::string content = subject + " keeps being involved in " + predicate
                                + " (" + std::to_string(occasions.size()) + " times)";
            std::string tail = subject.substr(subject.rfind(':') + 1);

            auto judgement = std::make_shared<MemoryItem>();
            judgement->memory_id = "judge_" + predicate + "_" + tail + "_" + std::to_string(now);
            judgement->owner = occasions.front()->owner;
            judgement->type = "judgement";
            judgement->content = content;
            judgement->importance = std::min(0.9, 0.5 + 0.08 * static_cast<double>(occasions.size()));
            judgement->emotional_valence = valence;
            judgement->world_time = Json(now);
            judgement->presentations = {now};
            judgement->episodes = static_cast<long long>(occasions.size());
            judgement->about = {subject, predicate};
            for (const auto& item : strongest) judgement->evidence.push_back(item->memory_id);

            Json from = Json::array();
            for (const std::string& id : judgement->evidence) from.push(Json(id));
            memories.push_back(judgement);

            Json detail = Json::object();
            detail["about"] = subject;
            detail["pattern"] = predicate;
            detail["occasions"] = static_cast<long long>(occasions.size());
            detail["content"] = content;
            detail["from_episodes"] = from;
            detail["note"] = "the episodes fade; the pattern does not";
            reasons.push_back({"memory.judgement_formed",
                               static_cast<double>(occasions.size()), detail});
        }
        return reasons;
    }

    Params params_;
};

}  // namespace usc
