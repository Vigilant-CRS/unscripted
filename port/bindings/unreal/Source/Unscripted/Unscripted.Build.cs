// Build rules for the Unreal module.
//
// The runtime is compiled INTO the module rather than linked as a shared
// library, and that is not a preference: several consoles forbid loading a
// dynamic library at all, and a plugin that works on PC and not on the target
// is worse than one that never worked. It costs nothing -- the core is
// header-only above the C ABI, so this adds exactly one translation unit.
using UnrealBuildTool;
using System.IO;

public class Unscripted : ModuleRules
{
    public Unscripted(ReadOnlyTargetRules Target) : base(Target)
    {
        // NO PRECOMPILED HEADER, and this is downstream of the exception
        // setting below rather than a preference. A shared PCH is compiled once
        // for every module that uses it, with one exception setting; a module
        // that needs a different one cannot share it, and the symptom is that
        // `bEnableExceptions` appears to be ignored -- every `throw` in the core
        // still fails to compile. Each file here includes what it needs.
        PCHUsage = PCHUsageMode.NoPCHs;
        // The core is written to C++17 and compiled here as C++20, because
        // Unreal 5.8 removed the C++17 setting outright -- "no longer allowed,
        // code will not compile with this version". C++17 source builds under
        // C++20 unchanged, and the core is compiled and tested at BOTH standards
        // so this is not a hope. Older engines accept `Cpp17` if a studio
        // prefers it.
        CppStandard = CppStandardVersion.Cpp20;
        // EXCEPTIONS ARE ON, and a studio should know why rather than find out.
        // The core refuses things by throwing -- a save from another game, a
        // pack that will not read, time running backwards -- and the C ABI
        // catches every one of them and returns a status code, so NOTHING
        // escapes into engine code. The core still needs them to compile.
        //
        // The first build of this module had them off, because the ABI's
        // guarantee reads like the core does not use them. It got as far as
        // `cannot use 'throw' with exceptions disabled`, twenty errors in.
        //
        // The alternative -- an exception-free core -- would mean threading a
        // status through every layer of the simulation to make one boundary
        // tidier. If a target platform forbids exceptions outright, that is the
        // change to make, and it is a real piece of work rather than a flag.
        bEnableExceptions = true;
        // The core does not use RTTI either, and Unreal disables it by default.
        bUseRTTI = false;

        PublicDependencyModuleNames.AddRange(new string[] { "Core", "Json" });
        PrivateDependencyModuleNames.AddRange(new string[]
            { "CoreUObject", "Engine" });

        // WHERE THE CORE IS. Searched for rather than assumed, because this
        // plugin gets copied: in the repository it sits at `port/bindings/unreal`
        // and the core is two directories up, and in a game it sits wherever the
        // studio put it. So walk up looking for the C ABI header, and let
        // `UNSCRIPTED_PORT_ROOT` override when the core lives somewhere else entirely.
        //
        // Failing LOUDLY here matters. Without it the first sign of a wrong path
        // is a hundred lines of "usc.h: No such file or directory" from a
        // compiler that has no idea what it was looking for.
        string PortRoot = System.Environment.GetEnvironmentVariable("UNSCRIPTED_PORT_ROOT");
        if (string.IsNullOrEmpty(PortRoot))
        {
            string Search = ModuleDirectory;
            for (int Up = 0; Up < 8 && PortRoot == null; Up++)
            {
                string Candidate = Path.Combine(Search, "port", "cpp");
                if (File.Exists(Path.Combine(Candidate, "abi", "usc.h")))
                {
                    PortRoot = Candidate;
                }
                Search = Path.GetFullPath(Path.Combine(Search, ".."));
            }
        }
        if (string.IsNullOrEmpty(PortRoot)
            || !File.Exists(Path.Combine(PortRoot, "abi", "usc.h")))
        {
            throw new BuildException(
                "Unscripted: cannot find the C++ core. It was not above " +
                ModuleDirectory + " and UNSCRIPTED_PORT_ROOT is not set. Point " +
                "UNSCRIPTED_PORT_ROOT at the runtime's port/cpp directory.");
        }
        PublicIncludePaths.Add(Path.Combine(PortRoot, "abi"));
        PrivateIncludePaths.Add(Path.Combine(PortRoot, "include"));


        // The one C++ file in the core. Everything else is headers.
        //
        // Unreal's unity build concatenates translation units, and the core's
        // headers define a great many inline functions in namespace `usc`. That
        // is safe, but it makes for very large unity blobs, so this module opts
        // out and compiles its files on their own.
        bUseUnity = false;
    }
}
