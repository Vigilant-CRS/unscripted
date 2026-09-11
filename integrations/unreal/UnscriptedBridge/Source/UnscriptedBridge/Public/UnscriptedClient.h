// Copyright Vigilant e.K.
//
// Transport for the Unscripted HTTP service. This is the only place
// that knows about URLs, headers and JSON; UUnscriptedSubsystem is the
// Blueprint-facing surface and NPC components share this one client so there is
// exactly one place authentication is configured.
//
// Every field parsed here is declared in ../../contract.json, which the runtime's
// test suite checks against a live service on every push.
#pragma once

#include "CoreMinimal.h"
#include "UObject/NoExportTypes.h"
#include "UnscriptedClient.generated.h"

/** A character's face and voice at one instant. Mirrors GET /avatar/face. */
USTRUCT(BlueprintType)
struct FUnscriptedFacePacket
{
    GENERATED_BODY()

    /** ARKit-52 weights in [0,1]. Only non-zero keys are sent, so a calm face is
        an EMPTY map rather than 52 zeroes -- treat a missing key as 0.0. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted")
    TMap<FString, float> Blendshapes;

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString DominantEmotion;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float Intensity = 0.f;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float Valence = 0.f;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float Arousal = 0.f;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float Dominance = 0.f;

    /** How strongly they avoid eye contact, [0,1]. Shame and low dominance raise it. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float GazeAversion = 0.f;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString GazeTarget;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") bool bMakeEyeContact = true;

    /** Hints for a TTS provider; the runtime does not synthesise audio. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float SpeechRate = 1.f;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float PitchShift = 0.f;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") float Loudness = 0.5f;

    /** "aggressive" | "retreat" | "approach" | "neutral", from Frijda tendencies. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Posture;
};

/** One NPC line plus the face to say it with. Mirrors the `avatar` block of
    POST /avatar/turn. The text has already passed the runtime's validator: it
    cannot contain a protected fact and cannot assert anything the character was
    not licensed to assert. */
/** One thing a character committed to, with who heard it.
 *
 *  The runtime distinguishes what was SAID from what was ASSERTED: a sentence
 *  may carry three claims or none, and only the assertions are what it stands
 *  behind. `Honesty` here is per claim -- a character can be truthful about one
 *  thing and lying about another in the same breath. */
USTRUCT(BlueprintType)
struct FUnscriptedAssertion
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Proposition;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Text;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Certainty;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Honesty;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") TArray<FString> HeardBy;
};

USTRUCT(BlueprintType)
struct FUnscriptedAvatarPacket
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString SpeakerId;
    /** Validated, secret-safe line to voice and subtitle. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Text;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Act;
    /** Always "ACCEPT" on release; a rejected line never reaches you. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Verdict;
    /** "honest", "lie", "exaggeration" or "understatement".
     *
     *  WHETHER THE CHARACTER LIED, which is the whole point of the runtime and
     *  which this struct dropped on the floor until an automation test went
     *  looking for it. The contract has promised it and the service has sent it
     *  the entire time; a game built on the Unreal plugin simply could not see
     *  it. Compiling could never have caught that. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FString Honesty;
    /** What was actually asserted, and to whom -- one entry per claim.
     *
     *  A line is not the same as a commitment: a character may say three things
     *  in a sentence, or none. This is the list the runtime stands behind, and
     *  it is what a quest system should key off rather than the prose. */
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") TArray<FUnscriptedAssertion> Asserted;
    UPROPERTY(BlueprintReadOnly, Category = "Unscripted") FUnscriptedFacePacket Face;
};

DECLARE_DELEGATE_TwoParams(FUnscriptedJsonReceived, TSharedPtr<class FJsonObject> /*Body*/, int32 /*Status*/);
DECLARE_DELEGATE_TwoParams(FUnscriptedFaceReceived, const FUnscriptedFacePacket& /*Face*/, bool /*bOk*/);

UCLASS()
class UNSCRIPTEDBRIDGE_API UUnscriptedClient : public UObject
{
    GENERATED_BODY()

public:
    /** BaseUrl like "http://127.0.0.1:8765". AuthToken may be empty on loopback. */
    void Configure(const FString& InBaseUrl, const FString& InAuthToken);

    void GetJson(const FString& Path, FUnscriptedJsonReceived OnDone);
    void PostJson(const FString& Path, const TSharedRef<class FJsonObject>& Body,
                  FUnscriptedJsonReceived OnDone);

    /** Convenience for the hot path: one agent's face, already parsed. */
    void GetFace(const FString& AgentId, FUnscriptedFaceReceived OnDone);

    static bool ParseFacePacket(const TSharedPtr<class FJsonObject>& Root, FUnscriptedFacePacket& Out);
    static bool ParseAvatarPacket(const TSharedPtr<class FJsonObject>& Root, FUnscriptedAvatarPacket& Out);

private:
    void Send(const FString& Verb, const FString& Path, const FString& Body,
              FUnscriptedJsonReceived OnDone);

    FString BaseUrl;
    FString AuthToken;
};
