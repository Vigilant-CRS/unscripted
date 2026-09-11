// The C++ core's single translation unit, pulled into this module.
//
// Unreal builds the .cpp files it finds under `Private/`, and the core lives
// outside the plugin -- so rather than teach UnrealBuildTool about a source
// directory somewhere else, which is fragile and version-specific, this one file
// includes it. `abi/` is on the include path, so the path below is stable
// wherever the plugin is copied to.
//
// Including a .cpp is unusual and is the point: it says out loud that the core
// is compiled INTO the module rather than linked beside it. Several consoles
// forbid loading a dynamic library at all, so a plugin that linked one would
// work on PC and nowhere that matters.
//
// THE MACROS BELOW ARE NOT DEFENSIVE PROGRAMMING. `AssertionMacros.h` defines
// `check(expr)`, and the runtime's validator has a method called `check` -- so
// every call to it inside the core became "too many arguments provided to
// function-like macro invocation", twenty errors deep, in a file the author had
// never touched. The engine's own `THIRD_PARTY_INCLUDES_START` exists for this
// and does not cover `check`, so it is undefined by hand and put back
// afterwards. Renaming the core's method to suit one engine would have been the
// wrong repair: the core is held to Python name for name, and the next engine
// will collide with something else.
#include "CoreMinimal.h"

THIRD_PARTY_INCLUDES_START
#pragma push_macro("check")
#pragma push_macro("checkf")
#pragma push_macro("verify")
#pragma push_macro("ensure")
#undef check
#undef checkf
#undef verify
#undef ensure

#include "usc.cpp"

#pragma pop_macro("ensure")
#pragma pop_macro("verify")
#pragma pop_macro("checkf")
#pragma pop_macro("check")
THIRD_PARTY_INCLUDES_END
