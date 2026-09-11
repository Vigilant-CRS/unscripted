// Independent input-boundary checks. Compile with:
// g++ -std=c++17 -Iport/cpp/include reviews/2026-09-07/repro_json_2026_09_07.cpp -o /tmp/unscripted-review-json
#include <iomanip>
#include <iostream>
#include "usc/json.hpp"

int main() {
    for (const std::string text : {"{\"a\":1", "{\"a\" 1}", "[1,]", "wat", "1e", "+1"}) {
        try {
            std::cout << "input=" << text << " accepted_as=" << usc::Json::parse(text).dump() << "\n";
        } catch (const std::exception& error) {
            std::cout << " rejected=" << error.what() << "\n";
        }
    }
    const std::string parsed = usc::Json::parse("\"\\ud83d\\ude00\"").as_string();
    std::cout << "emoji_utf8=";
    for (unsigned char byte : parsed)
        std::cout << std::hex << std::setfill('0') << std::setw(2) << static_cast<int>(byte);
    std::cout << " expected=f09f9880\n";
}
