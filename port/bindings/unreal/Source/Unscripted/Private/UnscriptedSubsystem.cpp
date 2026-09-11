// The Unreal-facing layer. See the header: NOT COMPILED HERE.
//
// Nothing in this file decides anything. It converts FString to UTF-8 and back,
// and hands the result to `usc_unreal::Native`, which is compiled and tested.
#include "UnscriptedSubsystem.h"

namespace {

/// `FString` -> UTF-8 `std::string`.
///
/// `TCHAR_TO_UTF8` yields a temporary whose lifetime ends at the semicolon, so
/// it is copied into the string here rather than held. That is the mistake this
/// helper exists to make impossible.
std::string Utf8(const FString& Text)
{
    return std::string(TCHAR_TO_UTF8(*Text));
}

FString FromUtf8(const std::string& Text)
{
    return FString(UTF8_TO_TCHAR(Text.c_str()));
}

EUnscriptedOutcome Translate(usc_unreal::Outcome Outcome)
{
    switch (Outcome)
    {
    case usc_unreal::Outcome::Ok:          return EUnscriptedOutcome::Ok;
    case usc_unreal::Outcome::BadArgument: return EUnscriptedOutcome::BadArgument;
    case usc_unreal::Outcome::BadPack:     return EUnscriptedOutcome::BadPack;
    case usc_unreal::Outcome::BadState:    return EUnscriptedOutcome::BadState;
    case usc_unreal::Outcome::BadSave:     return EUnscriptedOutcome::BadSave;
    default:                               return EUnscriptedOutcome::Refused;
    }
}

}  // namespace

int32 UUnscriptedSubsystem::AbiVersion()
{
    return usc_unreal::Native::abi_version();
}

FString UUnscriptedSubsystem::RuntimeVersion()
{
    return FromUtf8(usc_unreal::Native::runtime_version());
}

EUnscriptedOutcome UUnscriptedSubsystem::Open(const FString& PackPath,
                                                  const TArray<FString>& CharacterFiles,
                                                  const FString& ConfigJson)
{
    std::vector<std::string> Files;
    Files.reserve(CharacterFiles.Num());
    for (const FString& Name : CharacterFiles)
    {
        Files.push_back(Utf8(Name));
    }
    return Translate(Runtime.open(Utf8(PackPath), Files, Utf8(ConfigJson)));
}

void UUnscriptedSubsystem::Close() { Runtime.close(); }

bool UUnscriptedSubsystem::IsOpen() const { return Runtime.is_open(); }

int64 UUnscriptedSubsystem::WorldTime() const { return Runtime.world_time(); }

EUnscriptedOutcome UUnscriptedSubsystem::AdvanceTime(int64 Minutes)
{
    return Translate(Runtime.advance_time(Minutes));
}

EUnscriptedOutcome UUnscriptedSubsystem::SubmitPlayerText(const FString& Text)
{
    return Translate(Runtime.submit_player_text(Utf8(Text)));
}

EUnscriptedOutcome UUnscriptedSubsystem::Respond(const FString& AgentId,
                                                     const FString& Topic)
{
    return Translate(Runtime.respond(Utf8(AgentId), Utf8(Topic)));
}

EUnscriptedOutcome UUnscriptedSubsystem::AgentState(const FString& AgentId)
{
    return Translate(Runtime.agent_state(Utf8(AgentId)));
}

EUnscriptedOutcome UUnscriptedSubsystem::FacePacket(const FString& AgentId,
                                                        const FString& GazeTarget)
{
    return Translate(Runtime.face_packet(Utf8(AgentId), Utf8(GazeTarget)));
}

EUnscriptedOutcome UUnscriptedSubsystem::KnowledgeState(int64 Limit)
{
    return Translate(Runtime.knowledge_state(Limit));
}

EUnscriptedOutcome UUnscriptedSubsystem::WorldState()
{
    return Translate(Runtime.world_state());
}

EUnscriptedOutcome UUnscriptedSubsystem::SceneState()
{
    return Translate(Runtime.scene_state());
}

EUnscriptedOutcome UUnscriptedSubsystem::ExportState()
{
    return Translate(Runtime.export_state());
}

EUnscriptedOutcome UUnscriptedSubsystem::InspectState(const FString& BlobJson)
{
    return Translate(Runtime.inspect_state(Utf8(BlobJson)));
}

EUnscriptedOutcome UUnscriptedSubsystem::ImportState(const FString& BlobJson)
{
    return Translate(Runtime.import_state(Utf8(BlobJson)));
}

EUnscriptedOutcome UUnscriptedSubsystem::PendingActions()
{
    return Translate(Runtime.pending_actions());
}

EUnscriptedOutcome UUnscriptedSubsystem::ResolveAction(const FString& IntentId,
                                                           const FString& Status,
                                                           const FString& Detail)
{
    return Translate(Runtime.resolve_action(Utf8(IntentId), Utf8(Status), Utf8(Detail)));
}

FString UUnscriptedSubsystem::LastAnswer() const
{
    return FromUtf8(Runtime.answer());
}

FString UUnscriptedSubsystem::LastError() const
{
    return FromUtf8(Runtime.error());
}

void UUnscriptedSubsystem::Deinitialize()
{
    // The world is closed BEFORE the base class runs, because the base may drop
    // the last reference to this object and the runtime handle would then leak
    // for the lifetime of the process.
    Runtime.close();
    Super::Deinitialize();
}
