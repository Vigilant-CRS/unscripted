// Runs `belief_cases.json` through the ported belief engine and prints the
// resulting belief store as JSON, with every double written as its raw 64 bits.
//
// Bits rather than decimals, for the same reason `bit_probe` does it: two
// numbers that print identically to fifteen places can still be different
// doubles, and the difference between them is the difference between two worlds
// a thousand ticks later.
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

#include "usc/belief.hpp"
#include "usc/json.hpp"

namespace {

std::string read_file(const char* path) {
    std::ifstream file(path);
    std::ostringstream buffer;
    buffer << file.rdbuf();
    return buffer.str();
}

/// A double as its raw bits, tagged so it cannot be mistaken for a number that
/// happened to be written the same way.
usc::Json bits_of(double value) {
    std::uint64_t raw;
    std::memcpy(&raw, &value, sizeof raw);
    char buffer[32];
    std::snprintf(buffer, sizeof buffer, "b:%016llx",
                  static_cast<unsigned long long>(raw));
    return usc::Json(std::string(buffer));
}

/// Rewrite every number in a blob as its bit pattern, recursively.
usc::Json to_bits(const usc::Json& value) {
    switch (value.kind()) {
        case usc::Json::Kind::Real:
            return bits_of(value.as_double());
        case usc::Json::Kind::Array: {
            usc::Json out = usc::Json::array();
            for (const auto& item : value.items()) out.push(to_bits(item));
            return out;
        }
        case usc::Json::Kind::Object: {
            usc::Json out = usc::Json::object();
            for (const auto& entry : value.fields())
                out.fields()[entry.first] = to_bits(entry.second);
            return out;
        }
        default:
            return value;
    }
}

usc::Proposition proposition_from(const usc::Json& update) {
    usc::Proposition prop;
    prop.predicate = update.get("predicate").as_string();
    const usc::Json* slots = update.find("slots");
    if (slots) for (const auto& entry : slots->fields()) prop.slots[entry.first] = entry.second;
    prop.polarity = "+";
    return prop;
}

}  // namespace

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "belief_cases.json";
    usc::Json document = usc::Json::parse(read_file(path));

    usc::Json report = usc::Json::object();
    usc::BeliefEngine engine;

    for (const usc::Json& scenario : document.at("cases").items()) {
        usc::OrderedMap<usc::Belief> beliefs;
        usc::Json traces = usc::Json::array();

        for (const usc::Json& update : scenario.at("updates").items()) {
            long long repeat = 1;
            if (const usc::Json* found = update.find("repeat")) repeat = found->as_int(1);

            for (long long step = 0; step < repeat; ++step) {
                usc::Proposition claim = proposition_from(update);
                // `store_negated` files the claim under its own core key while
                // asserting the opposite -- how a denial of a distinct
                // proposition reaches the contradiction scan.
                if (update.get("store_negated").as_bool()) claim.polarity = "-";

                usc::Json origin = update.get("origin");
                // "vary" means a fresh origin per repetition: the case is about
                // the provenance trim, not about the correlation discount.
                if (origin.kind() == usc::Json::Kind::String && origin.as_string() == "vary")
                    origin = usc::Json(static_cast<long long>(step));

                usc::Json claim_id = update.get("claim_id");
                if (repeat > 1)
                    claim_id = usc::Json(claim_id.as_string() + ":" + std::to_string(step));

                std::vector<usc::Reason> reasons = engine.update(
                    beliefs, claim, update.get("polarity").as_string(),
                    update.get("trust").as_double(), update.get("competence").as_double(),
                    update.get("skepticism").as_double(), claim_id, origin,
                    update.get("world_time"), update.get("speaker"));

                // Only the last trace of a repeated update is kept, so a case
                // with 400 repetitions does not bury the comparison.
                if (step + 1 == repeat) {
                    usc::Json trace = usc::Json::array();
                    for (const usc::Reason& reason : reasons) {
                        usc::Json row = usc::Json::object();
                        row["code"] = reason.code;
                        row["amount"] = reason.amount;
                        row["detail"] = reason.detail;
                        trace.push(row);
                    }
                    traces.push(trace);
                }
            }
        }

        usc::Json store = usc::Json::object();
        for (const auto& entry : beliefs)
            store.fields()[entry.first] = entry.second.as_json();

        usc::Json result = usc::Json::object();
        result["beliefs"] = store;
        result["reasons"] = traces;
        report.fields()[scenario.get("id").as_string()] = to_bits(result);
    }

    std::printf("%s\n", report.dump(2).c_str());
    return 0;
}
