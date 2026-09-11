// Drive the runtime through the Unity binding, from C#, against the real
// library. Everything here is what a game does on a turn.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Unscripted;

internal static class Program
{
    private static int _failures;

    private static void Check(bool ok, string what)
    {
        if (!ok) { Console.WriteLine($"  FAIL {what}"); _failures++; }
    }

    private static JsonElement Parse(string json) =>
        JsonDocument.Parse(json).RootElement.Clone();

    public static int Main(string[] args)
    {
        string root = args.Length > 0 ? args[0] : ".";
        string pack = Path.Combine(root, "worldpacks", "cyberpunk-block");
        var characters = new List<string>();
        foreach (var file in Directory.GetFiles(Path.Combine(pack, "characters"), "*.json"))
            characters.Add(Path.GetFileName(file));
        characters.Sort(StringComparer.Ordinal);

        Console.WriteLine($"abi {World.AbiVersion}, runtime {World.RuntimeVersion}");
        Check(World.AbiVersion == World.ExpectedAbiVersion,
              "the library and this binding speak the same ABI");

        // Refusals first. A binding that turns a refusal into a crash is worse
        // than one that does not compile.
        try
        {
            using var missing = new World(Path.Combine(root, "nope"), characters.ToArray());
            Check(false, "a missing pack should have been refused");
        }
        catch (UnscriptedException error)
        {
            Check(error.Status == UscStatus.BadPack, "a missing pack is refused by code");
            Check(error.Message.Length > 0, "and says why");
        }

        using var world = new World(
            pack, characters.ToArray(),
            "{\"player_id\": \"agent:player_1\", \"pursuit\": true, \"standing\": true}");

        var look = Parse(world.SubmitPlayerText("look"));
        Check(look.GetProperty("parsed").GetProperty("intent").GetString() == "observe",
              "look parses as observe");
        Check(look.GetProperty("message").GetString().Contains("NPCs"),
              "and describes the room");

        var asked = Parse(world.SubmitPlayerText("ask Vee about Milan"));
        Check(asked.GetProperty("parsed").GetProperty("intent").GetString() == "ask",
              "ask parses as ask");
        Check(asked.GetProperty("npc").ValueKind != JsonValueKind.Null,
              "and somebody answers");
        Check(asked.GetProperty("npc").GetProperty("text").GetString().Length > 0,
              "with words in it");

        long before = world.WorldTime;
        world.AdvanceTime(120);
        Check(world.WorldTime == before + 120, "time advances by what it was given");
        try
        {
            world.AdvanceTime(-1);
            Check(false, "time should not run backwards");
        }
        catch (UnscriptedException error)
        {
            Check(error.Message.Contains("monotonic"), "and says so in those words");
        }

        var mind = Parse(world.AgentState("agent:npc_red_jacket"));
        Check(mind.GetProperty("beliefs").GetArrayLength() >= 0, "a mind has beliefs");
        Check(mind.GetProperty("face").TryGetProperty("blendshapes", out _),
              "and a face on it");

        var face = Parse(world.FacePacket("agent:npc_red_jacket"));
        Check(face.TryGetProperty("prosody", out _), "a face packet has prosody");
        Check(face.GetProperty("gaze").TryGetProperty("aversion", out _),
              "and gaze aversion");

        Check(Parse(world.KnowledgeState()).TryGetProperty("facts", out _),
              "who knows what");
        Check(Parse(world.WorldState()).TryGetProperty("factions", out _), "the world");
        Check(Parse(world.SceneState()).TryGetProperty("exits", out _), "the scene");
        Check(world.InspectAgent("agent:npc_red_jacket").Contains("beliefs of"),
              "a dump a person can read");

        // THE STRING-LIFETIME RULE, tested rather than trusted. Two answers are
        // held at once; if the wrapper handed back a pointer instead of a copy,
        // the first would have been overwritten by the second.
        string first = world.SceneState();
        string second = world.WorldState();
        Check(first != second && first.Contains("exits"),
              "an answer survives the next call");

        string saved = world.ExportState();
        var report = Parse(world.InspectState(saved));
        Check(report.GetProperty("usable").GetBoolean(), "our own save is usable");
        world.AdvanceTime(600);
        long moved = world.WorldTime;
        world.ImportState(saved);
        Check(world.WorldTime < moved, "and putting it back rewinds the clock");

        var foreign = Parse(world.InspectState("{\"format\": \"someone-elses-game\"}"));
        Check(!foreign.GetProperty("usable").GetBoolean(), "a foreign blob is not usable");
        try
        {
            world.ImportState("{\"format\": \"someone-elses-game\"}");
            Check(false, "and should be refused on import");
        }
        catch (UnscriptedException error)
        {
            Check(error.Status == UscStatus.BadSave, "with a save-specific code");
        }

        Check(Parse(world.PendingActions()).ValueKind == JsonValueKind.Array,
              "pending actions is a list");
        try
        {
            world.ResolveAction("intent:nobody", "SUCCEEDED");
            Check(false, "an unknown intent should be refused");
        }
        catch (UnscriptedException error)
        {
            Check(error.Status == UscStatus.BadState, "as a state error");
        }

        Check(Parse(world.Discredit("agent:npc_red_jacket")).ValueKind
                  == JsonValueKind.Array,
              "a source can be discredited");

        try
        {
            world.AgentState("agent:nobody");
            Check(false, "an unknown character should be refused");
        }
        catch (UnscriptedException error)
        {
            Check(error.Status == UscStatus.BadState, "as a state error too");
        }

        // Disposing twice, and using it afterwards, are both things a game does
        // by accident on a scene change.
        var throwaway = new World(pack, characters.ToArray());
        throwaway.Dispose();
        throwaway.Dispose();
        try
        {
            throwaway.SceneState();
            Check(false, "a disposed world should refuse");
        }
        catch (ObjectDisposedException) { }

        Console.WriteLine(_failures == 0
            ? "every Unity-binding check passed"
            : $"{_failures} check(s) failed");
        return _failures == 0 ? 0 : 1;
    }
}
