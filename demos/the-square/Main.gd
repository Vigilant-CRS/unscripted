extends Node2D

## The Square: what they think of you, and what they do about it.
##
## One plaza, seven people, two things you can do to somebody — be decent or be
## vile — and a readout of what the runtime makes of it. There is no reputation
## table in this project. Every number on screen is fetched from the runtime
## through the shipped addon, on the endpoint a shipping build is allowed to
## call.
##
##   arrows   walk
##   K        be kind to whoever you are standing with
##   X        be vile to them
##   SPACE    ask them something
##   W        let six hours pass, so that people can talk
##   R        start the day again
##
## THE BEAT WORTH WAITING FOR is the third one. Be vile in the square, where two
## people can see you, and watch their halos cool. Then walk to the bar, where
## Nadia was not present and has never met you — and find that she has cooled
## too, because somebody told her, and by less, because she only heard it.

const ROOMS := {
	"place:market":   {"label": "MARKET SQUARE", "rect": Rect2(430, 250, 700, 560)},
	"place:bar":      {"label": "THE FILAMENT",  "rect": Rect2(120, 250, 250, 250)},
	"place:alley":    {"label": "BACK ALLEY",    "rect": Rect2(120, 560, 250, 250)},
	"place:radio":    {"label": "CITY RADIO",    "rect": Rect2(1190, 250, 250, 250)},
	"place:precinct": {"label": "PRECINCT",      "rect": Rect2(1190, 560, 250, 250)},
}

## Names and a word about each, for the screen. Where they are comes from the
## runtime -- they have routines, and the day moves them.
const CAST := {
	"agent:yara":  {"name": "Yara",  "role": "trader"},
	"agent:otto":  {"name": "Otto",  "role": "on the bench"},
	"agent:nadia": {"name": "Nadia", "role": "the bar"},
	"agent:tomas": {"name": "Tomas", "role": "runner"},
	"agent:bran":  {"name": "Bran",  "role": "radio"},
	"agent:dale":  {"name": "Dale",  "role": "police"},
	"agent:sela":  {"name": "Sela",  "role": "police"},
}

const WALK_TO := {
	"place:market": "go to the market", "place:bar": "go to the bar",
	"place:alley": "go to the alley", "place:radio": "go to the radio",
	"place:precinct": "go to the precinct",
}

const INK := Color("08090e")
const PANEL := Color("11131c")
const EDGE := Color("222839")
const TEXT := Color("ece9e4")
const DIM := Color("79819a")
const AMBER := Color("e0a458")
const WARM := Color("5fbf8f")
const COLD := Color("d0596c")
const NEUTRAL := Color("4a5468")

var _player_place := "place:market"
var _clock := 0
var _ready_now := false
var _busy := false
var _walked_to := ""
var _last_line := ""
var _last_act := ""
var _speaker := ""
var _note := "walk to somebody · K be kind · X be vile · SPACE ask · W let six hours pass"

## agent id -> the runtime's own view of them, straight off
## `GET /v2/state/character`. Nothing in this file computes a mood or a warmth.
var _view: Dictionary = {}
## Smoothed for drawing only, so a halo eases rather than snapping. The value it
## eases toward is always the runtime's.
var _shown_warmth: Dictionary = {}

@onready var _host: UnscriptedHost = $Host
@onready var _client: UnscriptedClient = $Client


func _ready() -> void:
	_host.ready_at.connect(_on_ready)
	_host.failed.connect(func(why): push_warning("[unscripted] " + why))
	_client.failed.connect(func(why): _note = why; queue_redraw())
	_client.clock.connect(func(t: int): _clock = t)
	_client.character_state.connect(_on_character)
	_host.bundle_path = "res://unscripted.pyz"
	var pack := ProjectSettings.globalize_path("res://../../worldpacks/market-square")
	# The layers are passed here rather than declared in the pack, because
	# market-square is shipped and other demos and tests use it: a pack that
	# switched mechanics on for everybody would be deciding for them.
	_host.start(pack, ["pursuit", "standing"])
	for id in CAST:
		_shown_warmth[id] = 0.0
	queue_redraw()
	if OS.get_cmdline_args().has("--tour"):
		_tour()


func _on_ready(url: String, token: String) -> void:
	_client.connect_to(url, token)
	_ready_now = true
	_refresh()


func _on_character(character: Dictionary) -> void:
	var id := String(character.get("id", ""))
	if id != "":
		_view[id] = character
	queue_redraw()


func _refresh() -> void:
	## Ask the runtime what everybody currently makes of the player. Seven small
	## GETs; the client queues them, so they arrive in order and never overlap a
	## turn.
	for id in CAST:
		_client.fetch_character(id)


func _process(delta: float) -> void:
	var moved := false
	for id in CAST:
		var want := _warmth_of(id)
		var have: float = _shown_warmth.get(id, 0.0)
		if abs(want - have) > 0.001:
			_shown_warmth[id] = have + (want - have) * min(1.0, delta * 3.0)
			moved = true
	if moved:
		queue_redraw()


func _warmth_of(id: String) -> float:
	var regard: Dictionary = (_view.get(id, {}) as Dictionary).get("regard", {})
	return float(regard.get("warmth", 0.0))


func _here() -> Array:
	var out := []
	for id in CAST:
		if _place_of(id) == _player_place:
			out.append(id)
	return out


func _place_of(id: String) -> String:
	var seen: String = String((_view.get(id, {}) as Dictionary).get("location", ""))
	return seen if seen != "" else _home_of(id)


func _home_of(id: String) -> String:
	match id:
		"agent:yara", "agent:otto": return "place:market"
		"agent:nadia": return "place:bar"
		"agent:tomas": return "place:alley"
		"agent:bran": return "place:radio"
		_: return "place:precinct"


# ------------------------------------------------------------------- doing --

func _walk_to(place: String) -> void:
	if _walked_to == place:
		return
	# Everything opens onto the square, so a walk between two doors goes out and
	# in again. The runtime refuses a hop between them, politely and with a
	# reason, and it is right to.
	if place != "place:market" and _walked_to != "place:market":
		_client.say(WALK_TO["place:market"])
		await _client.spoke
	_client.say(WALK_TO.get(place, "look"))
	await _client.spoke
	_walked_to = place


func _act_on(verb: String, target := "") -> void:
	## `target` names WHO, because "whoever is first in the room" is not a
	## choice a player makes and is not one a scripted tour can rely on: the bar
	## holds two people at that hour, and the tour narrated one while the runtime
	## was told about the other.
	var who: Array = _here()
	if who.is_empty() or _busy or not _ready_now:
		return
	if target != "" and not who.has(target):
		return
	_busy = true
	_speaker = target if target != "" else String(who[0])
	var name := String(CAST[_speaker]["name"])
	await _walk_to(_player_place)
	_client.say("%s %s" % [verb, name.to_lower()])
	var avatar: Dictionary = await _client.spoke
	_last_line = String(avatar.get("text", ""))
	_last_act = String(avatar.get("act", ""))
	if verb == "ask":
		_note = "%s: %s" % [name, _act_label(_last_act)]
	else:
		_note = "you were %s to %s. Everybody who could see it now knows." % [
			"kind" if verb == "help" else "vile", name]
	# Ask the runtime again, for everybody: this is the moment the people who
	# only heard about it are supposed to differ from the people who watched.
	_refresh()
	_busy = false
	queue_redraw()


func _let_time_pass() -> void:
	## SIX HOURS. Without this nothing travels, because travelling is somebody
	## walking into a room and mentioning it -- and the demo would only ever
	## show the people who were standing there, which is a reputation counter.
	if _busy or not _ready_now:
		return
	_busy = true
	_note = "six hours pass. People go about their day, and they talk."
	queue_redraw()
	_client.say("wait 360 minutes")
	await _client.spoke
	_refresh()
	_busy = false
	queue_redraw()


func _act_label(act: String) -> String:
	match act:
		# "answered", not "told you what they know": the runtime's act is
		# `inform` even when what they inform you of is that they have nothing,
		# and a label claiming otherwise sits under a line that plainly says
		# the opposite.
		"inform": return "answered you"
		"evade": return "put you off"
		"greet": return "greeted you and no more"
		"deflect": return "changed the subject"
		"threaten": return "warned you off"
		_: return act


func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_K: _act_on("help")
		KEY_X: _act_on("threaten")
		KEY_SPACE: _act_on("ask")
		KEY_W: _let_time_pass()
		KEY_R: get_tree().reload_current_scene()
		KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN:
			_step(event.keycode)
		_: return
	queue_redraw()


func _step(key: int) -> void:
	## Out to the square and in again, which is the shape of the map.
	if _player_place != "place:market":
		_player_place = "place:market"
	else:
		match key:
			KEY_LEFT: _player_place = "place:bar"
			KEY_DOWN: _player_place = "place:alley"
			KEY_RIGHT: _player_place = "place:radio"
			KEY_UP: _player_place = "place:precinct"
	_note = "walk to somebody · K be kind · X be vile · SPACE ask · W let six hours pass"


# ----------------------------------------------------------------- drawing --

func _draw() -> void:
	var font := ThemeDB.fallback_font
	draw_rect(Rect2(Vector2.ZERO, Vector2(1920, 1080)), INK)

	draw_string(font, Vector2(120, 96), "THE SQUARE", HORIZONTAL_ALIGNMENT_LEFT,
				-1, 34, TEXT)
	draw_string(font, Vector2(120, 130),
				"what they think of you, and what they do about it",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 19, DIM)
	draw_string(font, Vector2(1480, 96),
				"%02d:%02d" % [(_clock / 60) % 24, _clock % 60],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 24, DIM)
	draw_string(font, Vector2(1480, 130),
				"K kind    X vile    SPACE ask    W wait    R reset",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 17, EDGE)

	for place in ROOMS:
		var room: Dictionary = ROOMS[place]
		var rect: Rect2 = room["rect"]
		draw_rect(rect, PANEL)
		draw_rect(rect, AMBER if place == _player_place else EDGE, false,
				  2.0 if place == _player_place else 1.0)
		draw_string(font, rect.position + Vector2(18, 32), room["label"],
					HORIZONTAL_ALIGNMENT_LEFT, -1, 16, DIM)

	for id in CAST:
		_draw_person(font, id)

	_draw_panel(font)

	draw_rect(Rect2(120, 880, 1680, 100), PANEL)
	draw_rect(Rect2(120, 880, 1680, 100), EDGE, false, 1.0)
	if _last_line != "":
		draw_string(font, Vector2(148, 924), '"%s"' % _last_line,
					HORIZONTAL_ALIGNMENT_LEFT, 1620, 22, TEXT)
	draw_string(font, Vector2(148, 958), _note, HORIZONTAL_ALIGNMENT_LEFT,
				1620, 17, AMBER if _last_line == "" else DIM)


func _warm_colour(w: float) -> Color:
	if w >= 0.0:
		return NEUTRAL.lerp(WARM, min(1.0, w * 2.2))
	return NEUTRAL.lerp(COLD, min(1.0, -w * 2.2))


func _draw_person(font: Font, id: String) -> void:
	var place := _place_of(id)
	if not ROOMS.has(place):
		return
	var rect: Rect2 = ROOMS[place]["rect"]
	# The slot is worked out from who is ACTUALLY in the room, not authored per
	# character: routines move people, and two characters who each had "slot 0"
	# ended up drawn on top of each other the moment the day carried them into
	# the same place.
	var present: Array = []
	for other in CAST:
		if _place_of(other) == place:
			present.append(other)
	present.sort()
	var slot: int = present.find(id)
	var span: float = rect.size.x / float(max(1, present.size()))
	var at := rect.position + Vector2(span * (slot + 0.5), rect.size.y * 0.42)

	var w: float = _shown_warmth.get(id, 0.0)
	var tint := _warm_colour(w)
	# Lean toward somebody they are warm to, away from somebody they are not.
	# Small: this is posture, not a stage direction.
	at.x += clamp(w, -1.0, 1.0) * 10.0

	# A halo whose weight is how strongly they feel, either way. Neutral draws
	# nothing at all, so an untouched world is quiet.
	if abs(w) > 0.02:
		var ring: float = 3.0 + 9.0 * min(1.0, abs(w) * 1.8)
		var glow := tint
		glow.a = 0.30 + 0.5 * min(1.0, abs(w) * 1.8)
		draw_arc(at, 54.0, 0.0, TAU, 64, glow, ring, true)

	if id == _speaker and place == _player_place:
		draw_arc(at, 44.0, 0.0, TAU, 48, AMBER, 1.5, true)
	draw_circle(at + Vector2(0, 60), 26.0, Color(0, 0, 0, 0.28))   # a soft shadow
	draw_circle(at, 34.0, tint)
	# Eyes, and a mouth that curves with how they feel about you. Two arcs and
	# three circles is all a face needs to read at this size.
	draw_circle(at + Vector2(-11, -7), 4.0, INK)
	draw_circle(at + Vector2(11, -7), 4.0, INK)
	var curve: float = clamp(w, -1.0, 1.0)
	var mouth := at + Vector2(0, 10 - curve * 6.0)
	draw_arc(mouth, 13.0, PI * (0.15 if curve >= 0.0 else 1.15),
			 PI * (0.85 if curve >= 0.0 else 1.85), 20, INK, 2.5, true)

	draw_string(font, at + Vector2(-70, 78), String(CAST[id]["name"]),
				HORIZONTAL_ALIGNMENT_CENTER, 140, 20, TEXT)
	draw_string(font, at + Vector2(-70, 100), String(CAST[id]["role"]),
				HORIZONTAL_ALIGNMENT_CENTER, 140, 14, DIM)
	if abs(w) > 0.02:
		draw_string(font, at + Vector2(-70, 124), _feeling(w),
					HORIZONTAL_ALIGNMENT_CENTER, 140, 15, tint)


func _feeling(w: float) -> String:
	if w > 0.35: return "glad to see you"
	if w > 0.12: return "warm"
	if w > 0.02: return "thawing"
	if w < -0.35: return "wants nothing to do with you"
	if w < -0.12: return "cold"
	return "wary"


func _draw_panel(font: Font) -> void:
	var rect := Rect2(1480, 250, 320, 560)
	draw_rect(rect, PANEL)
	draw_rect(rect, EDGE, false, 1.0)
	var who: Array = _here()
	# Whoever you last spoke to, if they are still in the room. Showing the
	# first name in the cast table instead meant the panel described somebody
	# other than the person who had just answered you.
	var id: String = ""
	if _speaker != "" and who.has(_speaker):
		id = _speaker
	elif not who.is_empty():
		id = String(who[0])
	if id == "":
		draw_string(font, rect.position + Vector2(20, 44), "NOBODY HERE",
					HORIZONTAL_ALIGNMENT_LEFT, -1, 15, EDGE)
		return
	var regard: Dictionary = (_view.get(id, {}) as Dictionary).get("regard", {})
	var y := rect.position.y + 44.0
	draw_string(font, Vector2(rect.position.x + 20, y), "STANDING WITH",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 13, DIM)
	y += 34
	draw_string(font, Vector2(rect.position.x + 20, y), String(CAST[id]["name"]),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 30, TEXT)
	y += 46
	# Straight off the runtime. The labels are ours; every number is theirs.
	for row in [
		["how warm", "%+.2f" % float(regard.get("warmth", 0.0))],
		["your conduct", "%+.2f" % float((regard.get("reputation", {}) as Dictionary).get("decent", 0.0))],
		["they like you", "%+.2f" % float(regard.get("liking", 0.0))],
		["they trust you", "%.2f" % float(regard.get("trust", 0.0))],
		["they know you", "%.2f" % float(regard.get("familiarity", 0.0))],
	]:
		draw_string(font, Vector2(rect.position.x + 20, y), String(row[0]),
					HORIZONTAL_ALIGNMENT_LEFT, -1, 16, DIM)
		draw_string(font, Vector2(rect.position.x + 190, y), String(row[1]),
					HORIZONTAL_ALIGNMENT_LEFT, 110, 16, TEXT)
		y += 30
	y += 18
	draw_string(font, Vector2(rect.position.x + 20, y), "NONE OF THIS IS AUTHORED",
				HORIZONTAL_ALIGNMENT_LEFT, -1, 12, EDGE)
	y += 22
	for text in ["There is no reputation table in",
				 "this project. Every number above",
				 "is read from the runtime."]:
		draw_string(font, Vector2(rect.position.x + 20, y), text,
					HORIZONTAL_ALIGNMENT_LEFT, 290, 13, EDGE)
		y += 18


# --------------------------------------------------------------- the tour --

## place, verb, who it is done to, and what to say about it.
const ROUTE := [
	["place:market", "", "", "Nobody has met you. Every face is quiet."],
	["place:market", "help", "agent:yara",
	 "You do Yara a kindness. Otto is on the bench, watching."],
	["place:bar", "ask", "agent:nadia",
	 "Nadia is in the bar. She did not see it, and has never met you."],
	["place:market", "threaten", "agent:yara",
	 "Now be vile to her, in front of the same man."],
	["place:market", "ask", "agent:yara", "Ask her something, straight away."],
	["place:market", "wait", "",
	 "Six hours pass. Nobody is scripted to tell anybody anything."],
	["place:bar", "ask", "agent:nadia",
	 "Nadia again. She still has not seen you."],
]
const BEAT := 4.0


func _tour() -> void:
	await get_tree().create_timer(2.0).timeout
	while not _ready_now:
		await get_tree().create_timer(0.3).timeout
	await get_tree().create_timer(1.5).timeout
	for step in ROUTE:
		_player_place = String(step[0])
		_note = String(step[3])
		queue_redraw()
		await get_tree().create_timer(1.2).timeout
		if String(step[1]) == "wait":
			await _let_time_pass()
		elif String(step[1]) != "":
			await _act_on(String(step[1]), String(step[2]))
		else:
			await _walk_to(_player_place)
			_refresh()
		await get_tree().create_timer(0.6).timeout
		var line := []
		for id in CAST:
			line.append("%s=%+.2f" % [String(CAST[id]["name"]), _warmth_of(id)])
		print("[tour] %-9s %-9s %-6s %s | %s" % [
			step[0].substr(6), step[1], String(step[2]).substr(6),
			" ".join(line), _last_line.substr(0, 34)])
		await get_tree().create_timer(BEAT).timeout
	print("[tour] done")
	get_tree().quit()
