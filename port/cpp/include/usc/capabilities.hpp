// `usc/capabilities.py`. Who owns each capability.
//
// Every capability has exactly ONE owner -- built in, external, or off -- which
// is what keeps startup deterministic and stops two implementations of the same
// thing being live at once. A studio that asked for an external text realizer
// and silently got the built-in one would ship the wrong build, so a declaration
// that disagrees with the configuration is REPORTED rather than rewritten.
#pragma once

#include <cctype>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include "usc/contracts.hpp"
#include "usc/json.hpp"
#include "usc/ordered_map.hpp"
#include "usc/pystr.hpp"

namespace usc {

inline const std::set<std::string>& valid_capability_modes() {
    static const std::set<std::string>* modes =
        new std::set<std::string>{"BUILTIN", "EXTERNAL", "DISABLED"};
    return *modes;
}

inline const OrderedMap<std::string>& default_capabilities() {
    static const OrderedMap<std::string>* table = [] {
        auto* fresh = new OrderedMap<std::string>();
        (*fresh)["semantic_parser"] = "BUILTIN";
        (*fresh)["text_realizer"] = "BUILTIN";
        (*fresh)["dialogue_validation"] = "BUILTIN";
        (*fresh)["storage"] = "BUILTIN";
        (*fresh)["inspector"] = "BUILTIN";
        return fresh;
    }();
    return *table;
}

inline const std::set<std::string>& hard_required_capabilities() {
    static const std::set<std::string>* required = new std::set<std::string>{
        "semantic_parser", "text_realizer", "dialogue_validation", "storage"};
    return *required;
}

struct CapabilityPlan {
    OrderedMap<std::string> resolved;
    std::vector<std::string> warnings;
};

/// `str(value or "").upper()`.
inline std::string normalize_capability_mode(const Json& value) {
    std::string text = value.truthy() ? value.py_str() : std::string();
    std::string out;
    for (char c : text)
        out += static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
    return out;
}

inline CapabilityPlan resolve_capabilities(const RuntimeConfig& config) {
    CapabilityPlan plan;
    plan.resolved = default_capabilities();

    for (const auto& entry : config.capabilities.fields()) {
        std::string mode = normalize_capability_mode(entry.second);
        if (!valid_capability_modes().count(mode))
            throw std::invalid_argument("Invalid capability mode for " + entry.first
                                        + ": " + entry.second.py_str());
        plan.resolved[entry.first] = mode;
    }

    for (const std::string& capability : hard_required_capabilities())
        if (plan.resolved.get(capability) == "DISABLED")
            throw std::invalid_argument("Required capability cannot be DISABLED: "
                                        + capability);

    const Json* declared_provider = config.text_realizer.find("provider");
    std::string provider = (declared_provider && declared_provider->truthy())
        ? declared_provider->py_str() : "template";
    std::string declared = plan.resolved.get("text_realizer");
    std::string implied;
    if (provider == "http") {
        implied = "EXTERNAL";
        const Json* endpoint = config.text_realizer.find("endpoint");
        if (!endpoint || !endpoint->truthy())
            throw std::invalid_argument("HTTP text_realizer requires "
                                        "text_realizer.endpoint");
    } else if (provider == "template") {
        implied = "BUILTIN";
    } else {
        throw std::invalid_argument("Unknown text_realizer.provider: " + provider);
    }
    if (!declared.empty() && declared != implied)
        // Silently rewriting an explicit declaration hides a misconfiguration.
        plan.warnings.push_back(
            "capabilities.text_realizer was declared " + declared
            + " but text_realizer.provider='" + provider + "' implies " + implied
            + "; using " + implied + ".");
    plan.resolved["text_realizer"] = implied;

    if (plan.resolved.get("dialogue_validation") != "BUILTIN")
        plan.warnings.push_back("Production mode should keep dialogue_validation "
                                "BUILTIN.");
    return plan;
}

}  // namespace usc
