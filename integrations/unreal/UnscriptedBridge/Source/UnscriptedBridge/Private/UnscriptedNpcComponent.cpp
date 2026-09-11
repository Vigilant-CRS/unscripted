// Copyright Vigilant e.K.
#include "UnscriptedNpcComponent.h"
#include "UnscriptedSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"

UUnscriptedNpcComponent::UUnscriptedNpcComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = true;
}

void UUnscriptedNpcComponent::BeginPlay()
{
    Super::BeginPlay();
    if (AgentId.IsEmpty())
    {
        UE_LOG(LogTemp, Warning,
               TEXT("UnscriptedNpcComponent on %s has no AgentId; it will do nothing."),
               *GetOwner()->GetName());
        SetComponentTickEnabled(false);
    }
}

void UUnscriptedNpcComponent::TickComponent(float DeltaTime, ELevelTick TickType,
                                              FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);

    // One request at a time per character. Without this, a slow reply on a busy
    // frame queues another and the queue never drains.
    if (bRequestInFlight) { return; }

    TimeSincePoll += DeltaTime;
    if (TimeSincePoll < FacePollSeconds) { return; }
    TimeSincePoll = 0.f;

    if (bOnlyPollWhenVisible && GetOwner() && !GetOwner()->WasRecentlyRendered(1.f))
    {
        return;   // the runtime keeps simulating them; they just need no face
    }

    UWorld* World = GetWorld();
    UUnscriptedSubsystem* Runtime = World ? World->GetSubsystem<UUnscriptedSubsystem>() : nullptr;
    if (!Runtime || !Runtime->IsConnected() || !Runtime->GetClient()) { return; }

    bRequestInFlight = true;
    Runtime->GetClient()->GetFace(AgentId,
        FUnscriptedFaceReceived::CreateLambda([this](const FUnscriptedFacePacket& Face, bool bOk)
    {
        bRequestInFlight = false;
        if (!bOk) { return; }
        CurrentFace = Face;
        OnFaceUpdated(Face);
    }));
}
