// Copyright Vigilant e.K.
//
// Drop this on any character that should be driven by the runtime. It polls that
// one agent's face between lines and applies the ARKit-52 weights to a MetaHuman.
//
// Polling rather than pushing is deliberate: a face is a continuous property of a
// character's mood, not an event. An NPC standing in a corner gets steadily
// angrier while the player is elsewhere, and the face should show that when the
// player walks back in.
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "UnscriptedClient.h"
#include "UnscriptedNpcComponent.generated.h"

UCLASS(ClassGroup = (Unscripted), meta = (BlueprintSpawnableComponent))
class UNSCRIPTEDBRIDGE_API UUnscriptedNpcComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UUnscriptedNpcComponent();

    /** The agent id in the world pack, e.g. "agent:voss". */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Unscripted")
    FString AgentId;

    /** Seconds between face polls. A face is mood, which moves slowly; 0.5 is ample
        and 10 NPCs at 0.5s is 20 requests/second against a local service. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Unscripted",
              meta = (ClampMin = "0.1"))
    float FacePollSeconds = 0.5f;

    /** Stop polling when the character is not rendered. Off-screen NPCs still
        think -- the runtime keeps simulating them -- they just do not need a face. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Unscripted")
    bool bOnlyPollWhenVisible = true;

    UPROPERTY(BlueprintReadOnly, Category = "Unscripted")
    FUnscriptedFacePacket CurrentFace;

    /** Override to route weights into your own rig if you are not on Live Link. */
    UFUNCTION(BlueprintImplementableEvent, Category = "Unscripted")
    void OnFaceUpdated(const FUnscriptedFacePacket& Face);

    virtual void BeginPlay() override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType,
                               FActorComponentTickFunction* ThisTickFunction) override;

private:
    float TimeSincePoll = 0.f;
    bool bRequestInFlight = false;
};
