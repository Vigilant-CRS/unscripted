// Copyright Vigilant e.K.
//
// UUnscriptedSubsystem is the one connection a project makes to the Living
// Worlds Runtime. It owns the HTTP session, the current scene, world time, and
// the deferred-line queue; NPC actors talk to it rather than to the network.
//
// The division of labour: the runtime decides WHAT a character knows, says and
// feels and WHY; your project renders it. Nothing here simulates anything.
//
// Every field this parses is declared in ../../contract.json, which the runtime's
// own test suite checks against a live service. If the server changes shape, that
// test fails before it reaches you.
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "UnscriptedClient.h"
#include "UnscriptedSubsystem.generated.h"

USTRUCT(BlueprintType)
struct FUnscriptedScenePerson
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString AgentId;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString DisplayName;
};

USTRUCT(BlueprintType)
struct FUnscriptedScene
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString LocationId;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Label;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") int32 WorldTime = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") TArray<FUnscriptedScenePerson> People;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") TArray<FUnscriptedScenePerson> Exits;
};

/** One retelling, for a debug HUD: who told whom, and whether it changed on the way. */
USTRUCT(BlueprintType)
struct FUnscriptedRetelling
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString From;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString To;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Place;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") int32 Hops = 0;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") bool bDistorted = false;
    /** Plain-language description of what changed, e.g. "the when was forgotten". */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString WhatChanged;
};

/** One physical act the runtime has asked this project to carry out.
 *
 *  The character has NOT moved. He is still at `From` and stays there until you
 *  call ReportIntentResult -- which is the entire point: the runtime refuses to
 *  believe a character is somewhere the player was never shown him going.
 */
USTRUCT(BlueprintType)
struct FUnscriptedActionIntent
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString IntentId;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString ActorId;
    /** Closed catalogue. Today: MOVE_TO. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Type;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString PlaceId;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString FromPlaceId;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Activity;
    /** Why the runtime decided this, in plain language, for a debug HUD. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Reason;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") int32 IssuedAt = 0;
    /** World time after which the runtime gives up and treats it as a failure. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") int32 ExpiresAt = 0;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FUnscriptedOnNpcSpoke, const FUnscriptedAvatarPacket&, Packet);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FUnscriptedOnActionIntent, const FUnscriptedActionIntent&, Intent);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FUnscriptedOnSceneChanged, const FUnscriptedScene&, Scene);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FUnscriptedOnError, const FString&, Message);

UCLASS(BlueprintType)
class UNSCRIPTEDBRIDGE_API UUnscriptedSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    /** Point at a running service. `unscripted serve --auth-token ...` supplies the token. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void Connect(const FString& BaseUrl, const FString& AuthToken);

    /** Send a player line. The reply arrives on OnNpcSpoke if an NPC answered. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void SubmitPlayerLine(const FString& Text);

    /** Advance world time. Rejected by the server if negative: time is monotonic. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void AdvanceWorldTime(int32 Minutes);

    /** Map a gameplay event onto the world (a door forced, a body found). */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void SendGameplayEvent(const FString& EventType, const FString& ActorId,
                           const FString& LocationId, const FString& Summary);

    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void RefreshScene();

    /** Rumour state for a debug HUD: who knows what, and who told whom. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void RefreshKnowledge();

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    const FUnscriptedScene& GetScene() const { return Scene; }

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    const TArray<FUnscriptedRetelling>& GetRecentRetellings() const { return Retellings; }

    /** Ask what the runtime wants carried out. Poll after every turn and advance.
     *
     *  Each intent not seen before is broadcast on OnActionIntent. Answer every
     *  one of them: an intent nobody answers is closed as TIMED_OUT and treated
     *  as a failure, so a project that never reports gets a world in which
     *  nobody ever arrives anywhere.
     */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void PollIntents();

    /** Tell the runtime what happened. Status: SUCCEEDED, FAILED, INTERRUPTED,
     *  UNREACHABLE. Only SUCCEEDED changes the simulated world. */
    UFUNCTION(BlueprintCallable, Category = "Unscripted")
    void ReportIntentResult(const FString& IntentId, const FString& Status,
                            const FString& Detail);

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    const TArray<FUnscriptedActionIntent>& GetPendingIntents() const { return PendingIntents; }

    UFUNCTION(BlueprintPure, Category = "Unscripted")
    bool IsConnected() const { return bConnected; }

    /** Fired when an NPC speaks. Drive subtitle, voice and face from the packet. */
    UPROPERTY(BlueprintAssignable, Category = "Unscripted") FUnscriptedOnNpcSpoke OnNpcSpoke;
    UPROPERTY(BlueprintAssignable, Category = "Unscripted") FUnscriptedOnSceneChanged OnSceneChanged;
    /** Fired once per new intent. Walk the character, then report the result. */
    UPROPERTY(BlueprintAssignable, Category = "Unscripted") FUnscriptedOnActionIntent OnActionIntent;
    /** Any 4xx/5xx. The message is the server's `error` field; never silent. */
    UPROPERTY(BlueprintAssignable, Category = "Unscripted") FUnscriptedOnError OnError;

    /** Shared by NPC components so there is exactly one HTTP configuration. */
    UUnscriptedClient* GetClient() const { return Client; }

private:
    UPROPERTY() TObjectPtr<UUnscriptedClient> Client = nullptr;
    FUnscriptedScene Scene;
    TArray<FUnscriptedRetelling> Retellings;
    TArray<FUnscriptedActionIntent> PendingIntents;
    /** Ids already broadcast, so a poll during a walk does not fire twice. */
    TSet<FString> AnnouncedIntents;
    bool bConnected = false;
};
