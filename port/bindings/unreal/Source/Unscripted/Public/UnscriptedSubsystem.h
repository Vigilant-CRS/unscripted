// The Unreal-facing layer.
//
// NOT COMPILED ON THE MACHINE THIS WAS WRITTEN ON. Unreal is not installed
// here, so everything below has been written against the engine's documented
// API and never built. That is stated rather than implied, and it is why this
// file is as thin as it is: every line that touches the runtime lives in
// `UscNative.h`, which IS compiled and exercised on every run of the test suite.
//
// What is unverified here is exactly this: the reflection macros, the
// FString/UTF-8 conversions, and the subsystem lifetime. If something does not
// build, it is in this file or in `Unscripted.Build.cs`.
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"

#include "UscNative.h"

#include "UnscriptedSubsystem.generated.h"

/// What a call did. Mirrors `usc_unreal::Outcome` for Blueprint.
UENUM(BlueprintType)
enum class EUnscriptedOutcome : uint8
{
    Ok            UMETA(DisplayName = "Ok"),
    BadArgument   UMETA(DisplayName = "Bad Argument"),
    BadPack       UMETA(DisplayName = "Bad Pack"),
    BadState      UMETA(DisplayName = "Bad State"),
    BadSave       UMETA(DisplayName = "Bad Save"),
    Refused       UMETA(DisplayName = "Refused"),
};

/**
 * One world per game instance.
 *
 * Every structured answer comes back as a JSON string. Unreal's `Json` module
 * parses it on the game's side, which is where a studio wants the types anyway
 * -- a USTRUCT per field would be a second schema to keep in step with the one
 * the runtime already documents.
 */
UCLASS(BlueprintType)
class UNSCRIPTED_API UUnscriptedSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    /** The ABI the linked runtime speaks. */
    UFUNCTION(BlueprintPure, Category = "Unscripted")
    static int32 AbiVersion();

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    static FString RuntimeVersion();

    /**
     * Open a world pack.
     *
     * @param PackPath        A filesystem path, not a `/Game/` path -- the
     *                        runtime reads JSON itself and knows nothing about
     *                        Unreal's virtual filesystem. On a cooked build,
     *                        stage the pack and pass the staged path.
     * @param CharacterFiles  Basenames inside the pack's `characters/`
     *                        directory. Required: on a cooked build they may be
     *                        inside a pak file, and the game is the only thing
     *                        that knows what is in it.
     */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome Open(const FString& PackPath,
                              const TArray<FString>& CharacterFiles,
                              const FString& ConfigJson);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void Close();

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    bool IsOpen() const;

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    int64 WorldTime() const;

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome AdvanceTime(int64 Minutes);

    /** One turn of player text. The answer is in `LastAnswer`. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome SubmitPlayerText(const FString& Text);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome Respond(const FString& AgentId, const FString& Topic);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome AgentState(const FString& AgentId);

    /** ARKit blendshapes, gaze, prosody and posture -- what MetaHuman consumes. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome FacePacket(const FString& AgentId, const FString& GazeTarget);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome KnowledgeState(int64 Limit);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome WorldState();

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome SceneState();

    /** The whole mutable world, for the game's own save. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome ExportState();

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome InspectState(const FString& BlobJson);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome ImportState(const FString& BlobJson);

    /** What this game still owes the runtime an answer for. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome PendingActions();

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    EUnscriptedOutcome ResolveAction(const FString& IntentId, const FString& Status,
                                       const FString& Detail);

    /** The last answer, as JSON. Owned by this object. */
    UFUNCTION(BlueprintPure, Category = "Unscripted")
    FString LastAnswer() const;

    /** Why the last call failed, or empty. */
    UFUNCTION(BlueprintPure, Category = "Unscripted")
    FString LastError() const;

    // UGameInstanceSubsystem
    virtual void Deinitialize() override;

private:
    usc_unreal::Native Runtime;
};
