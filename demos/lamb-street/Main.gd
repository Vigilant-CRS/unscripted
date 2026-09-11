extends Node2D

## Lamb Street: one scene, one cast, one question, and a switch.
##
## The comparison this demo exists to make is only worth something if the two
## sides are genuinely the same scene. So there is one project, one camera, one
## set of characters and one input -- and a toggle that changes ONLY where the
## answers come from. Two builds would always invite the objection that we made
## the other one worse on purpose.
##
##   SPACE   ask the person you are standing next to
##   T       switch between SCRIPTED and UNSCRIPTED
##   R       reset the night and start again
##   1-5     choose what to ask about
##   arrows  walk

const ROOMS := {
	"place:bar":       {"label": "THE NINEPIN",   "rect": Rect2(120, 210, 440, 250)},
	"place:kiosk":     {"label": "BYRNE'S STAND", "rect": Rect2(600, 210, 380, 250)},
	"place:shop":      {"label": "OKONKWO'S",     "rect": Rect2(1020, 210, 380, 250)},
	"place:taxi_rank": {"label": "THE RANK",      "rect": Rect2(120, 620, 440, 230)},
	"place:club_door": {"label": "THE LYRIC",     "rect": Rect2(600, 620, 380, 230)},
	"place:precinct":  {"label": "THE PRECINCT",  "rect": Rect2(1020, 620, 380, 230)},
	# Where it happened, and nobody is in it. The label used to carry the time
	# as well and ran off the edge of a 1920-wide frame into the key bindings,
	# which is the sort of thing you only see once it is on video.
	"place:hotel_back":{"label": "BEHIND THE MARCHMONT", "rect": Rect2(1440, 210, 360, 640)},
	"place:street":    {"label": "LAMB STREET",   "rect": Rect2(120, 490, 1680, 100)},
}

## What to say to the runtime to walk there. The scene moves the player on
## screen; the runtime has to be told, or every question is asked from the middle
## of the street and nobody is in earshot. That was the whole bug: six empty
## answers, no error anywhere, because asking somebody who is not there is a
## perfectly reasonable thing to get nothing back from.
const WALK_TO := {
	"place:bar": "go to the bar",
	"place:kiosk": "go to the kiosk",
	"place:shop": "go to the shop",
	"place:taxi_rank": "go to the rank",
	"place:club_door": "go to the club",
	"place:precinct": "go to the precinct",
	"place:street": "go to the street",
	"place:hotel_back": "go to the hotel",
}

const CAST := {
	"halloran": {"place": "place:bar",       "name": "Halloran", "role": "barman"},
	"byrne":    {"place": "place:kiosk",     "name": "Byrne",    "role": "papers"},
	"okonkwo":  {"place": "place:shop",      "name": "Okonkwo",  "role": "grocer"},
	"vance":    {"place": "place:taxi_rank", "name": "Vance",    "role": "driver"},
	"reyes":    {"place": "place:club_door", "name": "Reyes",    "role": "the door"},
	"doyle":    {"place": "place:precinct",  "name": "Doyle",    "role": "police"},
}

const TOPICS := ["what happened", "the shot", "the runner", "the car", "the bulletin"]

const INK := Color("0b0d11")
const PANEL := Color("11151d")
const EDGE := Color("222a38")
const TEXT := Color("e9e7e2")
const DIM := Color("8b93a3")
const AMBER := Color("e0a458")
const GREEN := Color("5fbf8f")
const RED := Color("d0596c")

var _mode := "SCRIPTED"
var _scripted := ScriptedDialogue.new()
var _player_place := "place:street"
var _topic := 0
var _answer := {}
var _speaker := ""
var _clock := 1267            # 21:07, the night of it
## Which act is on screen. Purely presentational, and the same in both modes so
## that nobody can say the two halves were shown a different night.
var _act := "THE NIGHT OF"
var _living_ready := false
var _busy := false
## Where the runtime thinks the player is, so a walk is sent once per room
## rather than before every question.
var _walked_to := ""

@onready var _host: UnscriptedHost = $Host
@onready var _client: UnscriptedClient = $Client


## The route the demo walks, twice. Same people, same questions, same order --
## which is the only way the two halves can be compared at all.
##
## THE COMPARISON IS THE SECOND ACT. In the first, both sides look fine, and
## they are meant to: a written table is a perfectly good way to answer six
## questions once. Then the night ends, the police give a statement to City
## Radio, and the same people are asked the same thing again. The table cannot
## read a clock, so it says what it said before -- and that is not a straw man,
## it is the shape of the tool.
##
## `at` is where the world clock should stand when the act opens; the runtime is
## walked forward to it, because asking questions costs minutes and the number
## would otherwise drift.
const ACTS := [
	{"title": "THE NIGHT OF", "at": 1267, "steps": [
		["halloran", 1],   # the shot      -- a time without a person
		["vance",    2],   # the runner    -- a person without a name
		["okonkwo",  3],   # the car       -- a car without a reason
		["reyes",    2],   # the runner    -- she watched him go, and says not
		["byrne",    4],   # the bulletin  -- there has not been one yet
		["doyle",    0],   # what happened -- has the case, has no facts
	]},
	{"title": "THE MORNING AFTER", "at": 1980, "steps": [
		["byrne",    4],   # the bulletin  -- he sells papers and he listens
		["halloran", 4],   # the bulletin  -- so does the barman
		["okonkwo",  4],   # the bulletin  -- and the grocer, in three rooms
	]},
	{"title": "BACK TO THE DOOR", "at": 1980, "steps": [
		["reyes",    0],   # what happened -- and now she has to say it outright
	]},
]
const BEAT := 3.4


func _ready() -> void:
	_host.ready_at.connect(_on_service_ready)
	_host.failed.connect(func(why): push_warning("[unscripted] " + why))
	_client.failed.connect(func(why): push_warning("[client] " + why))
	_client.advanced.connect(func(_t): queue_redraw())
	# The clock on the wall comes from the runtime, not from a counter here, so
	# what the scene shows and what the characters are answering out of cannot
	# drift apart.
	_client.clock.connect(func(t: int): _clock = t; queue_redraw())
	# Our own bundle, shipped beside the scene. This is the deployment story the
	# documentation describes, used on ourselves: one file, no install, no pip.
	_host.bundle_path = "res://unscripted.pyz"
	var pack := ProjectSettings.globalize_path("res://../../worldpacks/nine-oh-seven")
	# No layer list here on purpose. The world pack names the four it is built
	# on, in its own world.json, and the runtime reads them from there. Keeping a
	# second copy in the game meant the pack and the scene could disagree about
	# what the world was, and nothing would have said which one was right.
	_host.start(pack)
	queue_redraw()
	if OS.get_cmdline_args().has("--tour"):
		_tour()


func _tour() -> void:
	## Drive the comparison unattended, so it can be recorded and so that a
	## failure is a failure of the demo rather than of whoever was at the keyboard.
	##
	## SCRIPTED FIRST, deliberately. A viewer who sees the runtime first has
	## nothing to be surprised by; a viewer who sees six characters answer out of
	## a table and THEN sees the same six answer out of what they actually know
	## has the whole argument in ninety seconds.
	await get_tree().create_timer(2.0).timeout
	while not _living_ready:
		await get_tree().create_timer(0.3).timeout

	for mode in ["SCRIPTED", "UNSCRIPTED"]:
		_mode = mode
		_reset_run()
		queue_redraw()
		await get_tree().create_timer(BEAT * 0.7).timeout
		for act in ACTS:
			_act = act["title"]
			# An act change clears the panel. Leaving it up carried the last
			# answer of the night into the morning, under the new heading and
			# the new clock -- which looked exactly like the runtime having said
			# it at nine in the morning.
			_answer = {}
			_speaker = ""
			await _open_act(int(act["at"]))
			queue_redraw()
			await get_tree().create_timer(BEAT * 0.8).timeout
			for step in act["steps"]:
				_player_place = CAST[step[0]]["place"]
				_topic = step[1]
				_answer = {}
				queue_redraw()
				await get_tree().create_timer(0.9).timeout
				await _ask()
				queue_redraw()
				print("[tour] %-13s %-18s %02d:%02d %-9s %-13s %-7s %s" % [
					mode, _act, _clock / 60 % 24, _clock % 60, step[0],
					TOPICS[_topic], str(_answer.get("honesty", "—")),
					str(_answer.get("text", "")).substr(0, 44)])
				await get_tree().create_timer(BEAT).timeout
	print("[tour] done")
	get_tree().quit()


func _open_act(at: int) -> void:
	## Walk the world clock forward to where the act begins.
	##
	## The scripted side has no clock to move, and that is the point rather than
	## an omission: the scene knows what time it is either way, and only one of
	## the two answerers can be told.
	if _mode != "UNSCRIPTED":
		_clock = at
		return
	var delta := at - _clock
	if delta > 0:
		_client.say("wait %d minutes" % delta)
		await _client.spoke


func _on_service_ready(url: String, token: String) -> void:
	_client.connect_to(url, token)
	_living_ready = true
	queue_redraw()


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_T:
			# THE WHOLE POINT. Same scene, same person, same question.
			_mode = "UNSCRIPTED" if _mode == "SCRIPTED" else "SCRIPTED"
			_answer = {}
		KEY_R:
			_reset()
		KEY_SPACE:
			_ask()
		KEY_1, KEY_2, KEY_3, KEY_4, KEY_5:
			_topic = event.keycode - KEY_1
			_answer = {}
		KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN:
			_walk(event.keycode)
	queue_redraw()


func _walk(key: int) -> void:
	## Rooms in reading order, so walking is predictable on camera.
	var order := ["place:bar", "place:kiosk", "place:shop", "place:street",
				  "place:taxi_rank", "place:club_door", "place:precinct"]
	var at := order.find(_player_place)
	if at < 0:
		at = 3
	if key == KEY_LEFT or key == KEY_UP:
		at = max(0, at - 1)
	else:
		at = min(order.size() - 1, at + 1)
	_player_place = order[at]
	_answer = {}


func _here() -> String:
	for who in CAST:
		if CAST[who]["place"] == _player_place:
			return who
	return ""


func _walk_to(place: String) -> void:
	## Lamb Street is the only thing every door opens onto, so you go out to the
	## street and then in again -- which is what walking down a street is.
	##
	## The runtime refuses a hop between two doors, politely and with a reason,
	## and the first version of this demo threw that reason away and showed an
	## empty answer panel. It is worth saying plainly: the runtime was right and
	## the game was wrong, and the game had no way of noticing.
	if _walked_to == place:
		return
	if place != "place:street" and _walked_to != "place:street":
		_client.say(WALK_TO["place:street"])
		await _client.spoke
	_client.say(WALK_TO.get(place, "look"))
	await _client.spoke
	_walked_to = place


func _ask() -> void:
	## Walk there, wait, ask, wait, show. Every step awaited in one place.
	##
	## The first two attempts split this across a signal handler and tried to
	## work out which reply was which by filtering empties and then by a busy
	## flag. Both worked for the first character and went out of step for the
	## rest, because "which reply is this" is a question you should never have to
	## ask. Awaiting each call where it is made removes the question.
	var who := _here()
	if who == "" or _busy:
		return
	_speaker = who
	var topic: String = TOPICS[_topic]

	if _mode == "SCRIPTED":
		_answer = _scripted.answer(who, topic)
		queue_redraw()
		return

	if not _living_ready:
		_answer = {"text": "(the runtime is still starting)"}
		queue_redraw()
		return

	_busy = true
	_answer = {"text": "…"}
	queue_redraw()

	await _walk_to(_player_place)

	_client.say("ask %s about %s" % [who, topic])
	var avatar: Dictionary = await _client.spoke

	var asserted: Array = avatar.get("asserted", [])
	var first: Dictionary = asserted[0] if asserted.size() > 0 else {}
	var heard: Array = first.get("heard_by", [])
	_answer = {
		"text": avatar.get("text", ""),
		"honesty": avatar.get("honesty", "—"),
		# The row a dialogue tree has nowhere to put: how sure, on what, and how
		# many people were in earshot when it was said.
		"confidence": first.get("certainty", "—"),
		"source": first.get("proposition", "—"),
		"hops": str(heard.size()) if not heard.is_empty() else "—",
	}
	_busy = false
	queue_redraw()


func _reset_run() -> void:
	## Put the presentation back to the start of the night without reloading the
	## scene, so the tour can play the same three acts twice in one window.
	##
	## Deliberately does NOT reset the runtime: the scripted pass never touches
	## it, so the living pass still opens on an untouched world. A viewer who
	## toggles by hand mid-case carries the world with them, which is the truth
	## about what the runtime is.
	_scripted.reset()
	_answer = {}
	_speaker = ""
	_walked_to = ""
	_clock = 1267
	_act = String(ACTS[0]["title"])


func _reset() -> void:
	_scripted.reset()
	_answer = {}
	_walked_to = ""
	_clock = 1267
	get_tree().reload_current_scene()


func _advance_hours(hours: int) -> void:
	_clock += hours * 60
	if _living_ready:
		_client.advance(hours * 60)


func _draw() -> void:
	var font := ThemeDB.fallback_font
	draw_rect(Rect2(Vector2.ZERO, Vector2(1920, 1080)), INK)

	# --- the switch, at the top, always visible -----------------------------
	var on_unscripted := _mode == "UNSCRIPTED"
	draw_string(font, Vector2(120, 92), "NPC MODE", HORIZONTAL_ALIGNMENT_LEFT,
				-1, 20, DIM)
	draw_string(font, Vector2(120, 132),
				"SCRIPTED" if not on_unscripted else "SCRIPTED",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 34,
				TEXT if not on_unscripted else EDGE)
	draw_string(font, Vector2(340, 132), "UNSCRIPTED",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 34, AMBER if on_unscripted else EDGE)
	# The clock and the act, side by side and identical in both modes. Only one
	# of the two answerers can read them.
	draw_string(font, Vector2(1140, 92),
				"%02d:%02d" % [(_clock / 60) % 24, _clock % 60],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 26, TEXT)
	draw_string(font, Vector2(1140, 128), _act,
				HORIZONTAL_ALIGNMENT_LEFT, -1, 18, AMBER)
	draw_string(font, Vector2(1480, 92),
				"T switch   R reset   SPACE ask   1-5 topic",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 18, EDGE)

	# --- the street ---------------------------------------------------------
	for place in ROOMS:
		var room: Dictionary = ROOMS[place]
		var rect: Rect2 = room["rect"]
		draw_rect(rect, PANEL)
		draw_rect(rect, EDGE, false, 2.0)
		draw_string(font, rect.position + Vector2(18, 34), room["label"],
					HORIZONTAL_ALIGNMENT_LEFT, -1, 17, DIM)
		if place == _player_place:
			draw_rect(rect.grow(6), AMBER, false, 2.0)

	for who in CAST:
		var person: Dictionary = CAST[who]
		var rect: Rect2 = ROOMS[person["place"]]["rect"]
		var at := rect.position + rect.size * 0.5
		var lit: bool = who == _speaker and not _answer.is_empty()
		draw_circle(at, 26, GREEN if lit else Color("3a4354"))
		draw_string(font, at + Vector2(-60, 56), person["name"],
					HORIZONTAL_ALIGNMENT_LEFT, 200, 20, TEXT)
		draw_string(font, at + Vector2(-60, 78), person["role"],
					HORIZONTAL_ALIGNMENT_LEFT, 200, 15, DIM)

	if _here() != "":
		var rect: Rect2 = ROOMS[_player_place]["rect"]
		draw_string(font, rect.position + Vector2(18, rect.size.y - 16),
					"you are here — SPACE to ask", HORIZONTAL_ALIGNMENT_LEFT,
					-1, 15, AMBER)

	# --- the question -------------------------------------------------------
	var y := 900.0
	var x := 120.0
	for i in TOPICS.size():
		var chosen := i == _topic
		draw_string(font, Vector2(x, y), "%d %s" % [i + 1, TOPICS[i]],
					HORIZONTAL_ALIGNMENT_LEFT, -1, 19,
					AMBER if chosen else EDGE)
		x += 220

	# --- the answer, and what is known about it -----------------------------
	draw_rect(Rect2(120, 930, 1680, 120), PANEL)
	draw_rect(Rect2(120, 930, 1680, 120), EDGE, false, 2.0)
	if _answer.is_empty():
		draw_string(font, Vector2(148, 985),
					"walk to somebody and press SPACE",
					HORIZONTAL_ALIGNMENT_LEFT, -1, 20, EDGE)
		return

	var honesty: String = str(_answer.get("honesty", "—"))
	var colour := TEXT
	if honesty == "lie":
		colour = RED
	draw_string(font, Vector2(148, 975), "\"%s\"" % _answer.get("text", ""),
				HORIZONTAL_ALIGNMENT_LEFT, 1620, 24, colour)

	# The row a dialogue tree cannot fill in. On the scripted side these are
	# dashes, and that is the argument rather than an omission.
	var facts := "honesty: %s     confidence: %s     heard by: %s" % [
		honesty, str(_answer.get("confidence", "—")), str(_answer.get("hops", "—"))]
	draw_string(font, Vector2(148, 1022), facts, HORIZONTAL_ALIGNMENT_LEFT,
				-1, 18, RED if honesty == "lie" else DIM)
