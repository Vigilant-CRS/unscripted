// Copyright Vigilant e.K.
#include "UnscriptedSubsystem.h"
#include "Dom/JsonObject.h"

void UUnscriptedSubsystem::Connect(const FString& BaseUrl, const FString& AuthToken)
{
    if (!Client)
    {
        Client = NewObject<UUnscriptedClient>(this);
    }
    Client->Configure(BaseUrl, AuthToken);

    Client->GetJson(TEXT("/health"),
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        if (Status != 200 || !Body.IsValid())
        {
            bConnected = false;
            // Say what actually went wrong. "Could not connect" sends an integrator
            // to the wrong place; a 401 means a missing token, not a missing server.
            const FString Detail = Body.IsValid()
                ? Body->GetStringField(TEXT("error"))
                : FString::Printf(TEXT("no response (HTTP %d)"), Status);
            OnError.Broadcast(FString::Printf(
                TEXT("Unscripted: connection failed - %s"), *Detail));
            return;
        }
        bConnected = true;
        RefreshScene();
    }));
}

void UUnscriptedSubsystem::RefreshScene()
{
    if (!Client) { return; }
    Client->GetJson(TEXT("/state/scene"),
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        if (Status != 200 || !Body.IsValid()) { return; }

        FUnscriptedScene Next;
        Next.LocationId = Body->GetStringField(TEXT("location"));
        Next.Label      = Body->GetStringField(TEXT("label"));
        Next.WorldTime  = Body->GetIntegerField(TEXT("world_time"));

        const TArray<TSharedPtr<FJsonValue>>* People = nullptr;
        if (Body->TryGetArrayField(TEXT("npcs"), People))
        {
            for (const TSharedPtr<FJsonValue>& Entry : *People)
            {
                const TSharedPtr<FJsonObject> Person = Entry->AsObject();
                if (!Person.IsValid()) { continue; }
                FUnscriptedScenePerson Who;
                Who.AgentId     = Person->GetStringField(TEXT("id"));
                Who.DisplayName = Person->GetStringField(TEXT("name"));
                Next.People.Add(Who);
            }
        }

        const TArray<TSharedPtr<FJsonValue>>* Exits = nullptr;
        if (Body->TryGetArrayField(TEXT("exits"), Exits))
        {
            for (const TSharedPtr<FJsonValue>& Entry : *Exits)
            {
                const TSharedPtr<FJsonObject> Exit = Entry->AsObject();
                if (!Exit.IsValid()) { continue; }
                FUnscriptedScenePerson Way;
                Way.AgentId     = Exit->GetStringField(TEXT("id"));
                Way.DisplayName = Exit->GetStringField(TEXT("label"));
                Next.Exits.Add(Way);
            }
        }

        Scene = MoveTemp(Next);
        OnSceneChanged.Broadcast(Scene);
    }));
}

void UUnscriptedSubsystem::SubmitPlayerLine(const FString& Text)
{
    if (!Client) { return; }

    const TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("text"), Text);

    Client->PostJson(TEXT("/avatar/turn"), Request,
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        if (Status != 200 || !Body.IsValid())
        {
            OnError.Broadcast(Body.IsValid()
                ? Body->GetStringField(TEXT("error"))
                : FString::Printf(TEXT("turn failed (HTTP %d)"), Status));
            return;
        }

        // `avatar` is absent when the turn produced no spoken line -- a move, a
        // look, a command the parser rejected. Checking is not optional.
        const TSharedPtr<FJsonObject>* Avatar = nullptr;
        if (Body->TryGetObjectField(TEXT("avatar"), Avatar) && Avatar && Avatar->IsValid())
        {
            FUnscriptedAvatarPacket Packet;
            if (UUnscriptedClient::ParseAvatarPacket(*Avatar, Packet))
            {
                OnNpcSpoke.Broadcast(Packet);
            }
        }
        RefreshScene();
    }));
}

void UUnscriptedSubsystem::AdvanceWorldTime(int32 Minutes)
{
    if (!Client) { return; }
    if (Minutes < 0)
    {
        // World time is monotonic. The server rejects this too; failing here saves
        // a round trip and points at the caller rather than at the network.
        OnError.Broadcast(TEXT("Unscripted: world time cannot go backwards."));
        return;
    }
    const TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetNumberField(TEXT("minutes"), Minutes);
    Client->PostJson(TEXT("/advance"), Request,
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject>, int32 Status)
    {
        if (Status == 200) { RefreshScene(); }
    }));
}

void UUnscriptedSubsystem::SendGameplayEvent(const FString& EventType, const FString& ActorId,
                                               const FString& LocationId, const FString& Summary)
{
    if (!Client) { return; }
    const TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("type"), EventType);
    if (!ActorId.IsEmpty())    { Request->SetStringField(TEXT("actor"), ActorId); }
    if (!LocationId.IsEmpty()) { Request->SetStringField(TEXT("location"), LocationId); }

    const TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
    Payload->SetStringField(TEXT("summary"), Summary);
    Request->SetObjectField(TEXT("payload"), Payload);

    Client->PostJson(TEXT("/event"), Request,
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        if (Status != 200)
        {
            OnError.Broadcast(Body.IsValid() ? Body->GetStringField(TEXT("error"))
                                             : TEXT("event rejected"));
        }
    }));
}

void UUnscriptedSubsystem::RefreshKnowledge()
{
    if (!Client) { return; }
    Client->GetJson(TEXT("/state/knowledge"),
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        if (Status != 200 || !Body.IsValid()) { return; }
        Retellings.Reset();
        const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
        if (!Body->TryGetArrayField(TEXT("transmissions"), Rows)) { return; }
        for (const TSharedPtr<FJsonValue>& Entry : *Rows)
        {
            const TSharedPtr<FJsonObject> Row = Entry->AsObject();
            if (!Row.IsValid()) { continue; }
            FUnscriptedRetelling Told;
            Told.From        = Row->GetStringField(TEXT("from_name"));
            Told.To          = Row->GetStringField(TEXT("to_name"));
            Told.Place       = Row->GetStringField(TEXT("place_label"));
            Told.Hops        = Row->GetIntegerField(TEXT("hops"));
            Told.bDistorted  = Row->GetBoolField(TEXT("distorted"));
            Row->TryGetStringField(TEXT("distortion_note"), Told.WhatChanged);
            Retellings.Add(Told);
        }
    }));
}

void UUnscriptedSubsystem::PollIntents()
{
    if (!Client) { return; }
    Client->GetJson(TEXT("/v2/actions/pending"),
        FUnscriptedJsonReceived::CreateLambda([this](TSharedPtr<FJsonObject> Body, int32 Status)
    {
        if (Status != 200 || !Body.IsValid())
        {
            // A 404 here means the runtime is older than this plugin, not that
            // there is nothing to do. Saying which one it is saves an afternoon.
            if (Status == 404)
            {
                OnError.Broadcast(TEXT("Unscripted: this runtime does not serve "
                                       "/v2/actions/pending. Check GET /capabilities "
                                       "-> action_bridge before polling."));
            }
            return;
        }

        PendingIntents.Reset();
        const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
        if (!Body->TryGetArrayField(TEXT("intents"), Rows)) { return; }

        TSet<FString> StillOpen;
        for (const TSharedPtr<FJsonValue>& Entry : *Rows)
        {
            const TSharedPtr<FJsonObject> Row = Entry->AsObject();
            if (!Row.IsValid()) { continue; }

            FUnscriptedActionIntent Intent;
            Intent.IntentId = Row->GetStringField(TEXT("intent_id"));
            Intent.ActorId  = Row->GetStringField(TEXT("actor"));
            Intent.Type     = Row->GetStringField(TEXT("type"));
            Intent.Reason   = Row->GetStringField(TEXT("reason"));
            Intent.IssuedAt  = Row->GetIntegerField(TEXT("issued_at"));
            Intent.ExpiresAt = Row->GetIntegerField(TEXT("expires_at"));

            const TSharedPtr<FJsonObject>* Params = nullptr;
            if (Row->TryGetObjectField(TEXT("params"), Params) && Params && Params->IsValid())
            {
                (*Params)->TryGetStringField(TEXT("place"), Intent.PlaceId);
                (*Params)->TryGetStringField(TEXT("from"), Intent.FromPlaceId);
                (*Params)->TryGetStringField(TEXT("activity"), Intent.Activity);
            }

            PendingIntents.Add(Intent);
            StillOpen.Add(Intent.IntentId);

            // Broadcast each intent once. A poll every tick during a thirty-second
            // walk would otherwise restart that walk thirty times a second.
            if (!AnnouncedIntents.Contains(Intent.IntentId))
            {
                AnnouncedIntents.Add(Intent.IntentId);
                OnActionIntent.Broadcast(Intent);
            }
        }

        // Forget ids the runtime has closed -- including ones it timed out while
        // we were still walking, which must be allowed to be issued again.
        AnnouncedIntents = AnnouncedIntents.Intersect(StillOpen);
    }));
}

void UUnscriptedSubsystem::ReportIntentResult(const FString& IntentId,
                                                const FString& Status,
                                                const FString& Detail)
{
    if (!Client || IntentId.IsEmpty()) { return; }

    const TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
    Request->SetStringField(TEXT("status"), Status);
    Request->SetStringField(TEXT("detail"), Detail);

    const FString Path = FString::Printf(TEXT("/v2/actions/%s/result"), *IntentId);
    Client->PostJson(Path, Request,
        FUnscriptedJsonReceived::CreateLambda([this, IntentId](TSharedPtr<FJsonObject> Body, int32 Code)
    {
        if (Code == 200)
        {
            AnnouncedIntents.Remove(IntentId);
            // The world only changed if the runtime accepted the result, so the
            // scene is only worth refetching now.
            RefreshScene();
            return;
        }
        // 404 means it was already resolved or timed out while we were walking;
        // 400 means the status was not one of the four. Both are integration
        // bugs worth surfacing rather than retrying.
        OnError.Broadcast(Body.IsValid()
            ? FString::Printf(TEXT("Unscripted: intent %s -> %s"), *IntentId,
                              *Body->GetStringField(TEXT("error")))
            : FString::Printf(TEXT("Unscripted: intent %s rejected (HTTP %d)"),
                              *IntentId, Code));
    }));
}
