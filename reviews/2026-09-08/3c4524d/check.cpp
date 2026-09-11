// Native counterchecks against the shipped headers. Prints observed results.
#include <iomanip>
#include <iostream>
#include <filesystem>
#include "usc/belief.hpp"
#include "usc/pack_loader.hpp"
#include "usc/sdk.hpp"

void origins(int prior_repeats, int cycles, int after_reentry) {
    usc::BeliefEngine engine;
    usc::OrderedMap<usc::Belief> beliefs;
    auto prop = usc::Proposition::from_json(usc::Json::parse(
        R"({"predicate":"body:alive","slots":{"agent":"subject"}})"));
    long long clock = 0;
    auto hear = [&](const std::string& origin, bool neutral) {
        ++clock;
        engine.update(beliefs, prop, "+", neutral ? 0.0 : .9,
                      neutral ? 0.0 : .9, neutral ? 1.0 / 6.0 : 0.0,
                      usc::Json(clock), usc::Json(origin), usc::Json(clock),
                      usc::Json("speaker"));
    };
    hear("pinned", true);
    hear("one-report", false);
    auto* belief = beliefs.find(prop.core_key());
    const double ceiling = belief->logit_val * engine.max_origin_contribution();
    for (int i = 0; i < prior_repeats; ++i) hear("one-report", false);
    for (int cycle = 0; cycle < cycles; ++cycle) {
        for (long long i = 0; i < engine.params().origin_limit - 1; ++i)
            hear("filler-" + std::to_string(i), true);
        hear("one-report", false);
        for (int i = 0; i < after_reentry; ++i) hear("one-report", false);
    }
    std::cout << "prior_repeats=" << prior_repeats << " cycles=" << cycles
              << " after_reentry=" << after_reentry
              << " logit=" << belief->logit_val << " ceiling=" << ceiling
              << " spent=" << belief->unrecognised_spent
              << " p=" << belief->expected_prob() << '\n';
}

int main(int argc, char** argv) {
    std::cout << std::setprecision(17);
    origins(8, 1, 0);
    origins(0, 100, 1);
    if (argc > 1) {
        std::vector<std::string> characters;
        for (const auto& entry : std::filesystem::directory_iterator(
                 std::filesystem::path(argv[1]) / "characters"))
            if (entry.path().extension() == ".json")
                characters.push_back(entry.path().filename().string());
        std::sort(characters.begin(), characters.end());
        auto world = usc::load_world_pack(argv[1], characters);
        usc::RuntimeConfig config;
        config.world_pack_path = argv[1];
        usc::UnscriptedRuntime runtime(config, world);
        runtime.attach();
        for (int i = 1; i <= 5; ++i) {
            auto answer = runtime.respond("agent:barkeep_12", "clinic");
            std::size_t spoken = 0;
            for (const auto& reason : answer.reasons)
                if (reason.items().size() >= 3 &&
                    reason.items()[0].as_string() == "dialogue.direct_answer") {
                    const auto* moves = reason.items()[2].find("spoken");
                    if (moves) spoken += moves->items().size();
                }
            std::cout << "turn=" << i << " verdict=" << answer.verdict
                      << " spoken=" << spoken << " text=" << answer.text << '\n';
        }
    }
}
