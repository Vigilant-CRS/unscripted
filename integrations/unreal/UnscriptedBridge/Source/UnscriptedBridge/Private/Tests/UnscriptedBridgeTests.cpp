// Copyright Vigilant e.K.
//
// Does the plugin BEHAVE, as opposed to merely compile?
//
// Compiling proved the C++ is well formed against a real engine. It says
// nothing about whether a request reaches the runtime, whether the answer is
// the shape the contract promises, or whether the client survives the runtime
// refusing it. These run inside Unreal, against a live Unscripted service,
// and answer that.
//
// The service's address arrives in UNSCRIPTED_URL and UNSCRIPTED_TOKEN. tools/unreal_smoke.py
// starts a real service on a free port, puts them in the environment and runs
// these; without them the tests say so and skip, because a test that silently
// passes when it could not reach anything is worse than no test.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "HttpModule.h"
#include "HttpManager.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Misc/Paths.h"
#include "HAL/PlatformProcess.h"
#include "UnscriptedClient.h"

namespace LWTestSupport
{
    /// Where the service is, or empty if nobody told us.
    static FString BaseUrl() { return FPlatformMisc::GetEnvironmentVariable(TEXT("UNSCRIPTED_URL")); }
    static FString Token()   { return FPlatformMisc::GetEnvironmentVariable(TEXT("UNSCRIPTED_TOKEN")); }

    /// One request, waited on by ticking the HTTP manager.
    ///
    /// An automation test is allowed to block; a game is not, which is why the
    /// plugin itself is asynchronous and only this helper is not. Ticking
    /// rather than sleeping is what lets the response actually arrive.
    static bool Call(const FString& Verb, const FString& Path, const FString& Body,
                     int32& OutStatus, TSharedPtr<FJsonObject>& OutJson,
                     double TimeoutSeconds = 20.0)
    {
        const TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request =
            FHttpModule::Get().CreateRequest();
        Request->SetURL(BaseUrl() + Path);
        Request->SetVerb(Verb);
        Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
        Request->SetHeader(TEXT("Authorization"), TEXT("Bearer ") + Token());
        if (!Body.IsEmpty()) { Request->SetContentAsString(Body); }

        bool bDone = false;
        FString Payload;
        Request->OnProcessRequestComplete().BindLambda(
            [&bDone, &OutStatus, &Payload](FHttpRequestPtr, FHttpResponsePtr Response, bool bConnected)
        {
            OutStatus = (bConnected && Response.IsValid()) ? Response->GetResponseCode() : 0;
            if (bConnected && Response.IsValid()) { Payload = Response->GetContentAsString(); }
            bDone = true;
        });
        Request->ProcessRequest();

        const double Deadline = FPlatformTime::Seconds() + TimeoutSeconds;
        while (!bDone && FPlatformTime::Seconds() < Deadline)
        {
            FHttpModule::Get().GetHttpManager().Tick(0.05f);
            FPlatformProcess::Sleep(0.01f);
        }
        if (!bDone) { return false; }
        if (!Payload.IsEmpty())
        {
            const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Payload);
            FJsonSerializer::Deserialize(Reader, OutJson);
        }
        return true;
    }

    /// True when there is a service to talk to. Reported, never assumed.
    static bool Reachable(FAutomationTestBase& Test)
    {
        if (BaseUrl().IsEmpty())
        {
            Test.AddWarning(TEXT("UNSCRIPTED_URL is not set; run these through "
                                 "tools/unreal_smoke.py, which starts a service "
                                 "and points them at it."));
            return false;
        }
        return true;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUnscriptedServiceAnswers,
    "Unscripted.Service.AnswersAndNegotiatesTheContract",
    EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::ProductFilter)

bool FUnscriptedServiceAnswers::RunTest(const FString&)
{
    using namespace LWTestSupport;
    if (!Reachable(*this)) { return true; }

    int32 Status = 0;
    TSharedPtr<FJsonObject> Json;
    TestTrue(TEXT("the service answered /health"),
             Call(TEXT("GET"), TEXT("/health"), TEXT(""), Status, Json));
    TestEqual(TEXT("/health returned 200"), Status, 200);
    TestTrue(TEXT("/health said ok"), Json.IsValid() && Json->GetBoolField(TEXT("ok")));

    // THE CHECK docs/CONNECTING.md TELLS EVERY INTEGRATOR TO MAKE, made here so
    // the plugin's own advice is exercised rather than only written down.
    TestTrue(TEXT("/capabilities answered"),
             Call(TEXT("GET"), TEXT("/capabilities"), TEXT(""), Status, Json));
    const TArray<TSharedPtr<FJsonValue>>* Versions = nullptr;
    if (TestTrue(TEXT("/capabilities lists contract_versions"),
                 Json.IsValid() && Json->TryGetArrayField(TEXT("contract_versions"), Versions)))
    {
        bool bSpeaksTwo = false;
        for (const TSharedPtr<FJsonValue>& Value : *Versions)
        {
            if (Value.IsValid() && Value->AsString() == TEXT("2.0.0")) { bSpeaksTwo = true; }
        }
        TestTrue(TEXT("the runtime speaks contract 2.0.0"), bSpeaksTwo);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUnscriptedAvatarTurn,
    "Unscripted.Dialogue.ATurnComesBackParseable",
    EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::ProductFilter)

bool FUnscriptedAvatarTurn::RunTest(const FString&)
{
    using namespace LWTestSupport;
    if (!Reachable(*this)) { return true; }

    int32 Status = 0;
    TSharedPtr<FJsonObject> Json;
    TestTrue(TEXT("a turn was answered"),
             Call(TEXT("POST"), TEXT("/v2/avatar/turn"),
                  TEXT("{\"text\":\"ask Yara about the shooting\"}"), Status, Json));
    TestEqual(TEXT("a turn returns 200"), Status, 200);

    // The plugin's OWN parser, on the runtime's real answer. This is the join
    // that compiling cannot check: a field renamed on either side passes the
    // compiler and fails here.
    const TSharedPtr<FJsonObject>* Avatar = nullptr;
    if (Json.IsValid() && Json->TryGetObjectField(TEXT("avatar"), Avatar) && Avatar)
    {
        FUnscriptedAvatarPacket Packet;
        TestTrue(TEXT("ParseAvatarPacket accepts what the runtime sent"),
                 UUnscriptedClient::ParseAvatarPacket(*Avatar, Packet));
        TestTrue(TEXT("the character said something"), !Packet.Text.IsEmpty());
        TestTrue(TEXT("honesty is one of the four the contract names"),
                 Packet.Honesty == TEXT("honest") || Packet.Honesty == TEXT("lie")
                 || Packet.Honesty == TEXT("exaggeration")
                 || Packet.Honesty == TEXT("understatement"));
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUnscriptedRefusalIsHandled,
    "Unscripted.Service.ARefusalIsNotACrash",
    EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::ProductFilter)

bool FUnscriptedRefusalIsHandled::RunTest(const FString&)
{
    using namespace LWTestSupport;
    if (!Reachable(*this)) { return true; }

    // A client that only works when the server agrees is not finished. The
    // service answers every failure with {error, code}, and a plugin that
    // treats a 4xx as a parse failure loses the reason.
    int32 Status = 0;
    TSharedPtr<FJsonObject> Json;
    TestTrue(TEXT("a malformed body was answered at all"),
             Call(TEXT("POST"), TEXT("/turn"), TEXT("{\"txt\":\"look\"}"), Status, Json));
    TestEqual(TEXT("a misspelled field is refused, not silently accepted"), Status, 400);
    TestTrue(TEXT("the refusal names its code"),
             Json.IsValid() && !Json->GetStringField(TEXT("code")).IsEmpty());

    TestTrue(TEXT("an unknown endpoint answered"),
             Call(TEXT("GET"), TEXT("/v2/nothing/here"), TEXT(""), Status, Json));
    TestEqual(TEXT("an unknown endpoint is a 404"), Status, 404);
    return true;
}

#endif  // WITH_DEV_AUTOMATION_TESTS
