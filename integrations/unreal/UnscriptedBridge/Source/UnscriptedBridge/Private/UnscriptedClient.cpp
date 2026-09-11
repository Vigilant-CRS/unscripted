// Copyright Vigilant e.K.
#include "UnscriptedClient.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
// UrlEncode lives here. Without it FGenericPlatformHttp does not resolve, the
// enclosing expression becomes ill-formed, and clang then reports three further
// errors about lambda captures that have nothing wrong with them -- which is
// what a first compile is for.
#include "GenericPlatform/GenericPlatformHttp.h"

void UUnscriptedClient::Configure(const FString& InBaseUrl, const FString& InAuthToken)
{
    BaseUrl = InBaseUrl;
    BaseUrl.RemoveFromEnd(TEXT("/"));
    AuthToken = InAuthToken;
}

void UUnscriptedClient::GetJson(const FString& Path, FUnscriptedJsonReceived OnDone)
{
    Send(TEXT("GET"), Path, FString(), MoveTemp(OnDone));
}

void UUnscriptedClient::PostJson(const FString& Path,
                                   const TSharedRef<FJsonObject>& Body,
                                   FUnscriptedJsonReceived OnDone)
{
    FString Serialised;
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Serialised);
    FJsonSerializer::Serialize(Body, Writer);
    Send(TEXT("POST"), Path, Serialised, MoveTemp(OnDone));
}

void UUnscriptedClient::Send(const FString& Verb, const FString& Path,
                               const FString& Body, FUnscriptedJsonReceived OnDone)
{
    const TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request =
        FHttpModule::Get().CreateRequest();
    Request->SetURL(BaseUrl + Path);
    Request->SetVerb(Verb);
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
    if (!AuthToken.IsEmpty())
    {
        Request->SetHeader(TEXT("Authorization"), TEXT("Bearer ") + AuthToken);
    }
    if (!Body.IsEmpty())
    {
        Request->SetContentAsString(Body);
    }

    Request->OnProcessRequestComplete().BindLambda(
        [OnDone](FHttpRequestPtr, FHttpResponsePtr Response, bool bSucceeded)
    {
        TSharedPtr<FJsonObject> Parsed;
        int32 Status = 0;
        if (bSucceeded && Response.IsValid())
        {
            Status = Response->GetResponseCode();
            const TSharedRef<TJsonReader<>> Reader =
                TJsonReaderFactory<>::Create(Response->GetContentAsString());
            FJsonSerializer::Deserialize(Reader, Parsed);
        }
        OnDone.ExecuteIfBound(Parsed, Status);
    });
    Request->ProcessRequest();
}

void UUnscriptedClient::GetFace(const FString& AgentId, FUnscriptedFaceReceived OnDone)
{
    GetJson(FString::Printf(TEXT("/avatar/face?agent_id=%s"), *FGenericPlatformHttp::UrlEncode(AgentId)),
        FUnscriptedJsonReceived::CreateLambda([OnDone](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        FUnscriptedFacePacket Face;
        const bool bOk = (Status == 200) && UUnscriptedClient::ParseFacePacket(Body, Face);
        OnDone.ExecuteIfBound(Face, bOk);
    }));
}

bool UUnscriptedClient::ParseFacePacket(const TSharedPtr<FJsonObject>& Root, FUnscriptedFacePacket& Out)
{
    if (!Root.IsValid()) { return false; }

    // Only non-zero weights are sent. An empty map is a calm face, not an error.
    const TSharedPtr<FJsonObject>* Weights = nullptr;
    if (Root->TryGetObjectField(TEXT("blendshapes"), Weights) && Weights && Weights->IsValid())
    {
        for (const auto& Pair : (*Weights)->Values)
        {
            double Weight = 0.0;
            if (Pair.Value.IsValid() && Pair.Value->TryGetNumber(Weight))
            {
                // FJsonObject::Values is keyed by FStringType, which in UE 5.8
                // is no longer FString. The conversion has to be written out;
                // before 5.8 this compiled because the types were the same one.
                Out.Blendshapes.Add(FString(Pair.Key), static_cast<float>(Weight));
            }
        }
    }

    const TSharedPtr<FJsonObject>* Emotion = nullptr;
    if (Root->TryGetObjectField(TEXT("emotion"), Emotion) && Emotion && Emotion->IsValid())
    {
        (*Emotion)->TryGetStringField(TEXT("dominant"), Out.DominantEmotion);
        Out.Intensity = (*Emotion)->GetNumberField(TEXT("intensity"));
        Out.Valence   = (*Emotion)->GetNumberField(TEXT("valence"));
        Out.Arousal   = (*Emotion)->GetNumberField(TEXT("arousal"));
        Out.Dominance = (*Emotion)->GetNumberField(TEXT("dominance"));
    }

    const TSharedPtr<FJsonObject>* Gaze = nullptr;
    if (Root->TryGetObjectField(TEXT("gaze"), Gaze) && Gaze && Gaze->IsValid())
    {
        (*Gaze)->TryGetStringField(TEXT("target"), Out.GazeTarget);
        Out.GazeAversion    = (*Gaze)->GetNumberField(TEXT("aversion"));
        Out.bMakeEyeContact = (*Gaze)->GetBoolField(TEXT("make_contact"));
    }

    const TSharedPtr<FJsonObject>* Prosody = nullptr;
    if (Root->TryGetObjectField(TEXT("prosody"), Prosody) && Prosody && Prosody->IsValid())
    {
        Out.SpeechRate = (*Prosody)->GetNumberField(TEXT("speech_rate"));
        Out.PitchShift = (*Prosody)->GetNumberField(TEXT("pitch_shift"));
        Out.Loudness   = (*Prosody)->GetNumberField(TEXT("loudness"));
    }

    Root->TryGetStringField(TEXT("posture"), Out.Posture);
    return true;
}

bool UUnscriptedClient::ParseAvatarPacket(const TSharedPtr<FJsonObject>& Root,
                                            FUnscriptedAvatarPacket& Out)
{
    if (!Root.IsValid()) { return false; }
    Root->TryGetStringField(TEXT("speaker_id"), Out.SpeakerId);
    Root->TryGetStringField(TEXT("text"), Out.Text);
    Root->TryGetStringField(TEXT("act"), Out.Act);
    Root->TryGetStringField(TEXT("verdict"), Out.Verdict);
    Root->TryGetStringField(TEXT("honesty"), Out.Honesty);

    // What the character actually committed to. Absent from this parser until
    // an automation test asked for it, which is the difference between code
    // that compiles and code that does what the contract says.
    const TArray<TSharedPtr<FJsonValue>>* Claims = nullptr;
    if (Root->TryGetArrayField(TEXT("asserted"), Claims) && Claims)
    {
        for (const TSharedPtr<FJsonValue>& Value : *Claims)
        {
            const TSharedPtr<FJsonObject>* Claim = nullptr;
            if (!Value.IsValid() || !Value->TryGetObject(Claim) || !Claim) { continue; }
            FUnscriptedAssertion Assertion;
            (*Claim)->TryGetStringField(TEXT("proposition"), Assertion.Proposition);
            (*Claim)->TryGetStringField(TEXT("text"), Assertion.Text);
            (*Claim)->TryGetStringField(TEXT("certainty"), Assertion.Certainty);
            (*Claim)->TryGetStringField(TEXT("honesty"), Assertion.Honesty);
            const TArray<TSharedPtr<FJsonValue>>* Heard = nullptr;
            if ((*Claim)->TryGetArrayField(TEXT("heard_by"), Heard) && Heard)
            {
                for (const TSharedPtr<FJsonValue>& Listener : *Heard)
                {
                    if (Listener.IsValid()) { Assertion.HeardBy.Add(Listener->AsString()); }
                }
            }
            Out.Asserted.Add(Assertion);
        }
    }

    // The avatar block carries the same face shape as GET /avatar/face.
    ParseFacePacket(Root, Out.Face);
    return !Out.Text.IsEmpty();
}
