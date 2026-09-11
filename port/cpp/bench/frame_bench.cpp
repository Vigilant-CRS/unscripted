// What the C++ core costs, in milliseconds. Driven by `tools/frame_bench.py`,
// which builds the pack, runs the same sequence in Python, and prints both.
//
// The port was verified for CORRECTNESS long before anybody measured it: fifty
// of fifty-one modules held to Python bit for bit, five conformance scenarios
// end to end, 504 deliberate defects introduced. Not one number about what it
// COSTS. That is the first question an engine programmer asks and it had no
// answer, so this is the answer.
//
// It prints JSON on stdout and nothing else, so the Python side can read it:
//
//     frame_bench <pack> <hours> <turns>
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "usc/json.hpp"
#include "usc/pack_loader.hpp"
#include "usc/sdk.hpp"

namespace {

double milliseconds_since(std::chrono::steady_clock::time_point start) {
    const std::chrono::duration<double, std::milli> spent =
        std::chrono::steady_clock::now() - start;
    return spent.count();
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 4) {
        std::fprintf(stderr, "usage: frame_bench <pack> <hours> <turns>\n");
        return 2;
    }
    const std::string pack = argv[1];
    const long long hours = std::atoll(argv[2]);
    const long long turns = std::atoll(argv[3]);
    if (hours <= 0 || turns <= 0) {
        std::fprintf(stderr, "hours and turns must both be positive\n");
        return 2;
    }

    // `load_world_pack` takes the character file names rather than walking a
    // directory, because a console reads a packed archive and not a folder. A
    // BENCH is a desktop tool, so it walks the folder and hands over the list --
    // which is exactly the division of labour the loader was shaped for.
    std::vector<std::string> characters;
    const std::filesystem::path folder = std::filesystem::path(pack) / "characters";
    for (const auto& entry : std::filesystem::directory_iterator(folder))
        if (entry.path().extension() == ".json")
            characters.push_back(entry.path().filename().string());
    std::sort(characters.begin(), characters.end());

    usc::World world = usc::load_world_pack(pack, characters);

    usc::RuntimeConfig config;
    config.world_pack_path = pack;
    usc::UnscriptedRuntime runtime(config, world);
    runtime.attach();

    // One untimed hour first, on both sides: the first call touches pages and
    // fills caches that every later one finds warm, and timing it would report
    // the cost of starting rather than the cost of running.
    runtime.advance_time(60);

    std::chrono::steady_clock::time_point start = std::chrono::steady_clock::now();
    for (long long i = 0; i < hours; ++i) runtime.advance_time(60);
    const double hour_ms = milliseconds_since(start) / static_cast<double>(hours);

    std::vector<std::string> ids;
    for (const auto& one : runtime.world.agents) ids.push_back(one.first);
    if (ids.size() < 2) {
        std::fprintf(stderr, "the pack has fewer than two characters\n");
        return 2;
    }
    const std::string speaker = ids[0];
    const std::string listener = ids[1];

    runtime.core.say(speaker, listener);           // warm, untimed
    start = std::chrono::steady_clock::now();
    for (long long i = 0; i < turns; ++i) runtime.core.say(speaker, listener);
    const double turn_ms = milliseconds_since(start) / static_cast<double>(turns);

    long long busiest = 0;
    for (const auto& place : runtime.world.places.fields()) {
        const long long here =
            static_cast<long long>(runtime.world.occupants(place.first).size());
        if (here > busiest) busiest = here;
    }

    usc::Json out = usc::Json::object();
    out["hour_ms"] = usc::Json(hour_ms);
    out["turn_ms"] = usc::Json(turn_ms);
    out["cast"] = usc::Json(static_cast<long long>(runtime.world.agents.size()));
    out["busiest"] = usc::Json(busiest);
    std::printf("%s\n", out.dump().c_str());
    return 0;
}
