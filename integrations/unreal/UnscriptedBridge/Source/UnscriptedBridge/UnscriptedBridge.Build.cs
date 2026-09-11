// Copyright Unscripted. Drop-in UE5 plugin module.
using UnrealBuildTool;

public class UnscriptedBridge : ModuleRules
{
    public UnscriptedBridge(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = ModuleRules.PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            // Json is PUBLIC, not private: UnscriptedClient.h puts
            // TSharedPtr<FJsonObject> in the FUnscriptedJsonReceived delegate, and that
            // delegate is part of the public API -- a game module binding a
            // handler to GetJson needs the type, not just the forward
            // declaration. Private would compile here and fail in the project
            // that consumes it, which is the worst place to find out.
            "Json",
        });

        // HTTP is used only from the .cpp; JsonUtilities likewise.
        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "HTTP",
            "JsonUtilities",
        });
    }
}
