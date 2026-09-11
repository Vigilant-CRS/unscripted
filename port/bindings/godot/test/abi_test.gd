# Drive the runtime from GDSCRIPT, through the GDExtension, against the real
# library. This is the part no amount of C++ testing covers: whether Godot can
# see the class, construct it, call its methods and read what comes back.
#
#     godot --headless --path port/bindings/godot/test --script abi_test.gd
extends SceneTree

var failures := 0

func check(ok: bool, what: String) -> void:
	if not ok:
		print("  FAIL ", what)
		failures += 1

func _initialize() -> void:
	var repo: String = ProjectSettings.globalize_path("res://../../..")

	check(ClassDB.class_exists("Unscripted"), "Godot can see the class")
	if not ClassDB.class_exists("Unscripted"):
		quit(1)
		return

	var world = ClassDB.instantiate("Unscripted")
	print("abi ", world.abi_version(), ", runtime ", world.runtime_version())
	check(world.abi_version() == 1, "the library speaks ABI 1")

	# A pack that is not there is refused with a reason, not a crash.
	var refused: String = world.open(repo + "/nope", "a.json", "")
	check(refused != "", "a missing pack is refused")

	var pack: String = repo + "/worldpacks/cyberpunk-block"
	var files: PackedStringArray = PackedStringArray()
	for name in DirAccess.get_files_at(pack + "/characters"):
		if name.ends_with(".json"):
			files.append(name)
	files.sort()
	var opened: String = world.open(
		pack, "\n".join(files),
		'{"player_id": "agent:player_1", "pursuit": true, "standing": true}')
	check(opened == "", "the pack opens: " + opened)
	if opened != "":
		quit(1)
		return

	var look: Variant = JSON.parse_string(world.submit_player_text("look"))
	check(look != null, "a turn comes back as JSON")
	check(look["parsed"]["intent"] == "observe", "look parses as observe")
	check(look["message"].contains("NPCs"), "and describes the room")

	var asked: Variant = JSON.parse_string(world.submit_player_text("ask Vee about Milan"))
	check(asked["parsed"]["intent"] == "ask", "ask parses as ask")
	check(asked["npc"] != null, "and somebody answers")
	check(String(asked["npc"]["text"]).length() > 0, "with words in it")

	var before: int = world.world_time()
	check(world.advance_time("120") == "", "time advances")
	check(world.world_time() == before + 120, "by what it was given")
	check(world.advance_time("-1").contains("monotonic"), "and only forwards")

	var mind: Variant = JSON.parse_string(world.agent_state("agent:npc_red_jacket"))
	check(mind.has("beliefs"), "a mind has beliefs")
	check(mind["face"].has("blendshapes"), "and a face on it")
	check(JSON.parse_string(world.agent_state("agent:nobody")).has("error"),
		  "an unknown character is refused, in JSON")

	var face: Variant = JSON.parse_string(world.face_packet("agent:npc_red_jacket", ""))
	check(face.has("prosody"), "a face packet has prosody")
	check(face["gaze"].has("aversion"), "and gaze aversion")

	check(JSON.parse_string(world.knowledge_state("40")).has("facts"), "who knows what")
	check(JSON.parse_string(world.world_state()).has("factions"), "the world")
	check(JSON.parse_string(world.scene_state()).has("exits"), "the scene")
	check(String(world.inspect_agent("agent:npc_red_jacket")).contains("beliefs of"),
		  "a dump a person can read")

	# The string-lifetime rule: two answers held at once. If the binding handed
	# back the runtime's own buffer, the second call would have eaten the first.
	var scene: String = world.scene_state()
	var state: String = world.world_state()
	check(scene != state and scene.contains("exits"),
		  "an answer survives the next call")

	var saved: String = world.export_state()
	check(JSON.parse_string(world.inspect_state(saved))["usable"], "our own save is usable")
	world.advance_time("600")
	var moved: int = world.world_time()
	world.import_state(saved)
	check(world.world_time() < moved, "and putting it back rewinds the clock")
	check(not JSON.parse_string(
		world.inspect_state('{"format": "someone-elses-game"}'))["usable"],
		"a foreign blob is not usable")

	check(JSON.parse_string(world.pending_actions()) != null, "pending actions is JSON")

	if failures == 0:
		print("every Godot-binding check passed")
	else:
		print(failures, " check(s) failed")
	quit(1 if failures > 0 else 0)
