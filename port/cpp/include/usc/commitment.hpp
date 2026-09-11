// `usc/commitment.py`. What a character commits to saying, before any words
// exist.
//
// The runtime used to hand a text provider a LIST of facts the character was
// permitted to mention, and which of them reached the listener was then the
// provider's choice. Harmless for a template realizer; for a language model it
// means the MODEL decides what information enters the society, because a spoken
// claim is a real event that moves other characters' beliefs. The claim "the
// text layer decides only how it is phrased" was not true.
//
// A commitment is the fix. The runtime selects the exact propositions to assert,
// with what force and how openly, and the text layer renders that and nothing
// else. Selection is a runtime decision, so it is seeded, replayable and in the
// event log.
//
// The same structure carries deception: a lie is a move whose proposition is not
// what the speaker holds. Nothing else in the pipeline has to know the
// difference, which is why the two arrive together.
#pragma once

#include <algorithm>
#include <cmath>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/determinism.hpp"
#include "usc/json.hpp"
#include "usc/reason.hpp"
#include "usc/ontology.hpp"
#include "usc/pyround.hpp"

namespace usc {

/// How openly a move is made. Affects phrasing, not what is asserted.
inline constexpr const char* DIRECT = "direct";
inline constexpr const char* PARTIAL = "partial";
inline constexpr const char* HEDGED = "hedged";

/// How sure the speaker sounds. Derived from confidence unless overridden.
inline constexpr const char* CERTAIN = "certain";
inline constexpr const char* PROBABLE = "probable";
inline constexpr const char* UNCERTAIN = "uncertain";

/// Why a move's proposition differs from the speaker's belief, if it does.
inline constexpr const char* HONEST = "honest";
inline constexpr const char* LIE = "lie";
inline constexpr const char* EXAGGERATION = "exaggeration";
inline constexpr const char* UNDERSTATEMENT = "understatement";

/// Sound as sure as you are. One place, so every path agrees.
inline std::string certainty_for(double confidence) {
    if (confidence >= 0.85) return CERTAIN;
    if (confidence >= 0.65) return PROBABLE;
    return UNCERTAIN;
}

/// One thing a character commits to doing with a sentence.
///
/// `proposition` is what is ASSERTED, which is not necessarily what the speaker
/// believes -- `believed_probability` records the latter, and `honesty` says why
/// they differ. A listener updates on the assertion; the speaker's own belief is
/// untouched by their own speech.
struct SemanticMove {
    std::string act = "assert";              // assert | deny | evade | advise | greet
    std::optional<Proposition> proposition;  // absent for non-factual acts
    std::string certainty = PROBABLE;
    std::string disclosure = DIRECT;
    std::string honesty = HONEST;
    /// What the speaker actually holds. Absent when the act carries no claim.
    std::optional<double> believed_probability;

    bool is_factual() const {
        return proposition.has_value() && (act == "assert" || act == "deny");
    }
    bool is_deceptive() const { return honesty != HONEST; }
    std::string rendered() const { return proposition ? proposition->str() : ""; }

    Json as_json() const {
        Json out = Json::object();
        out["act"] = act;
        out["proposition"] = proposition ? proposition->as_json() : Json();
        out["rendered"] = rendered();
        out["certainty"] = certainty;
        out["disclosure"] = disclosure;
        out["honesty"] = honesty;
        out["believed_probability"] = believed_probability
            ? Json(py_round(*believed_probability, 4)) : Json();
        return out;
    }

    static SemanticMove from_json(const Json& data,
                                  const std::optional<Proposition>& proposition = std::nullopt) {
        SemanticMove out;
        const Json* act = data.find("act");
        if (act && !act->is_null()) out.act = act->py_str();
        out.proposition = proposition;
        const Json* certainty = data.find("certainty");
        if (certainty && !certainty->is_null()) out.certainty = certainty->py_str();
        const Json* disclosure = data.find("disclosure");
        if (disclosure && !disclosure->is_null()) out.disclosure = disclosure->py_str();
        const Json* honesty = data.find("honesty");
        if (honesty && !honesty->is_null()) out.honesty = honesty->py_str();
        const Json* believed = data.find("believed_probability");
        if (believed && believed->is_number()) out.believed_probability = believed->as_double();
        return out;
    }
};

/// A proposition the character could assert, and how well it fits.
struct Candidate {
    Proposition proposition;
    double confidence = 0.0;    // how sure they are, in [0.5, 1]
    double relevance = 1.0;     // how well it answers what was asked
    bool affirmed = true;       // assert it, or assert its negation

    /// `list.remove(x)` removes the first element EQUAL to x, and a Python
    /// dataclass compares by value -- so two candidates identical in every field
    /// are interchangeable and the first goes. Reproduced rather than swapped
    /// for pointer identity, which would remove a different one.
    bool operator==(const Candidate& other) const {
        return confidence == other.confidence && relevance == other.relevance
            && affirmed == other.affirmed
            && proposition.as_json().dump() == other.proposition.as_json().dump();
    }
};

using CommitmentReason = Reason;

/// The complete semantic content of one utterance.
struct Commitment {
    std::vector<SemanticMove> moves;
    std::vector<std::string> forbidden;   // avoid labels; never the secret content
    long long max_sentences = 2;
    std::vector<CommitmentReason> reasons;

    std::vector<Proposition> propositions() const {
        std::vector<Proposition> out;
        for (const SemanticMove& move : moves)
            if (move.proposition) out.push_back(*move.proposition);
        return out;
    }

    std::vector<SemanticMove> factual_moves() const {
        std::vector<SemanticMove> out;
        for (const SemanticMove& move : moves) if (move.is_factual()) out.push_back(move);
        return out;
    }

    std::vector<std::string> rendered_facts() const {
        std::vector<std::string> out;
        for (const SemanticMove& move : factual_moves()) {
            std::string text = move.rendered();
            if (!text.empty()) out.push_back(text);
        }
        return out;
    }

    Json as_json() const {
        Json out = Json::object();
        Json rows = Json::array();
        for (const SemanticMove& move : moves) rows.push(move.as_json());
        out["moves"] = rows;
        Json avoid = Json::array();
        for (const std::string& one : forbidden) avoid.push(Json(one));
        out["forbidden"] = avoid;
        out["max_sentences"] = max_sentences;
        return out;
    }
};

/// Pick what to say. This is the decision the text layer used to make.
///
/// Candidates are ranked by relevance then confidence. Everything within a small
/// band of the best score is treated as EQUALLY GOOD -- and among those the
/// choice is seeded rather than first-past-the-post, so different worlds and
/// different moments produce different answers while any single world stays
/// replayable.
///
/// That is the whole argument against letting a model pick: seeded selection
/// here gives the same unpredictability from the player's side, and stays in the
/// event log.
inline Commitment select(const std::vector<Candidate>& candidates,
                         const std::string& act = "assert", long long limit = 1,
                         const std::vector<std::string>& seed_parts = {},
                         const std::vector<std::string>& forbidden = {},
                         long long max_sentences = 2) {
    Commitment out;
    out.forbidden = forbidden;
    out.max_sentences = max_sentences;

    std::vector<Candidate> ranked = candidates;
    // `(-round(relevance, 4), -round(confidence, 4), str(proposition))` -- the
    // ROUNDED values are the sort key, so two scores that differ in the fifth
    // decimal rank as equal and the proposition's own text breaks the tie. A
    // port sorting on the raw doubles would order them by noise.
    std::stable_sort(ranked.begin(), ranked.end(),
                     [](const Candidate& a, const Candidate& b) {
                         double ar = -py_round(a.relevance, 4), br = -py_round(b.relevance, 4);
                         if (ar != br) return ar < br;
                         double ac = -py_round(a.confidence, 4), bc = -py_round(b.confidence, 4);
                         if (ac != bc) return ac < bc;
                         return a.proposition.str() < b.proposition.str();
                     });
    if (ranked.empty()) return out;

    std::vector<Candidate> pool = ranked;
    std::vector<Candidate> chosen;
    while (!pool.empty() && static_cast<long long>(chosen.size()) < std::max(1LL, limit)) {
        const Candidate best = pool.front();
        std::vector<Candidate> band;
        for (const Candidate& one : pool)
            if (std::fabs(one.relevance - best.relevance) < 1e-9
                && std::fabs(one.confidence - best.confidence) <= 0.05)
                band.push_back(one);

        Candidate pick = band.front();
        if (band.size() > 1) {
            std::vector<std::string> parts = seed_parts;
            parts.push_back("commitment");
            parts.push_back("pick" + std::to_string(chosen.size()));
            if (parts.size() > 6) parts.resize(6);
            if (parts.size() < 5)
                throw std::invalid_argument(
                    "commitment.select needs at least three seed parts: they are "
                    "spliced into derive_seed, which takes five.");
            std::vector<std::uint8_t> seed = derive_seed_parts(
                parts[0], parts[1], parts[2], parts[3], parts[4],
                parts.size() > 5 ? parts[5] : std::string());
            pick = band[seeded_choice(seed, std::vector<double>(band.size(), 1.0))];

            Json detail = Json::object();
            Json among = Json::array();
            for (const Candidate& one : band) among.push(Json(one.proposition.str()));
            detail["among"] = among;
            detail["picked"] = pick.proposition.str();
            out.reasons.push_back({"commitment.seeded_choice",
                                   static_cast<double>(band.size()), detail});
        }

        auto found = std::find(pool.begin(), pool.end(), pick);
        if (found != pool.end()) pool.erase(found);

        SemanticMove move;
        move.act = pick.affirmed ? act : "deny";
        move.proposition = pick.affirmed ? pick.proposition : pick.proposition.negated();
        move.certainty = certainty_for(pick.confidence);
        move.believed_probability = pick.confidence;
        chosen.push_back(pick);
        out.moves.push_back(move);
    }

    Json detail = Json::object();
    Json committed = Json::array();
    for (const SemanticMove& move : out.moves) committed.push(Json(move.rendered()));
    detail["committed"] = committed;
    detail["considered"] = static_cast<long long>(ranked.size());
    detail["note"] = std::string("the runtime chose; the text layer renders");
    out.reasons.push_back({"commitment.selected",
                           static_cast<double>(out.moves.size()), detail});
    return out;
}

/// Turn an honest move into a deceptive one, keeping the real belief on record.
///
/// The speaker's own belief never changes -- lying is not self-persuasion -- and
/// `believed_probability` stays what it was, so the record shows the divergence
/// and a later contradiction is findable.
inline SemanticMove deceive(const SemanticMove& move, const Proposition& assert_instead,
                            const std::string& honesty = LIE) {
    SemanticMove out = move;
    out.proposition = assert_instead;
    out.honesty = honesty;
    return out;
}

}  // namespace usc
