extends Node2D

## The same events, twice, inside a game engine -- and moving.
##
## The first version of this drew states: one snapshot per beat, held for four
## seconds. It was accurate and it was dead, because what is worth seeing here is
## not a state but a PROCESS. A claim leaves a mouth, crosses a room, arrives, and
## changes what somebody is willing to say next. Snapshots sample exactly that
## away.
##
## So it moves. People walk their routines between rooms. A claim passing from one
## to another is a pulse that travels the line between them and leaves a thread
## behind, and the threads accumulate into the provenance web the runtime has been
## keeping all along. Switch to FLAGS and every thread vanishes -- not as a
## flourish, but because that is the honest picture: a boolean has nowhere to keep
## them.
##
## TWO PHASES, DELIBERATELY. Everything is fetched first and played back second. A
## demo that renders while it waits on HTTP shows a different thing on a slow
## machine, and the slow machine is the one it will be shown on. It also makes the
## recording deterministic.
##
## Nothing is drawn from an asset. A schematic that is clearly designed reads as
## engineering; a scene dressed in free assets reads as a prototype, and this has
## to survive being forwarded to somebody's boss.

const UnscriptedClient := preload("res://Unscripted.gd")
const FlagModel := preload("res://Flags.gd")

## The claim being followed, and the two answers the world contains for it. The
## radio's version is wrong and everywhere; the witness's version is right and
## almost nowhere. Drawing them in different colours is the whole demonstration:
## you watch a false story sweep a block while the truth sits in one person.
const FACT := "killed_by"
const RADIO_VERSION := "group:eastside"
const TRUE_VERSION := "group:contractors"

const BG := Color("#0b0d11")
const PANEL := Color("#11141a")
const LINE := Color("#232833")
const FG := Color("#e9e7e2")
const DIM := Color("#868d99")
const HOT := Color("#e0a458")
const COOL := Color("#6fa8dc")
const BAD := Color("#d0619b")
const LIE := Color("#e05252")
## The two answers, kept visually apart. Amber is what the radio said; green is
## what the witness saw. A viewer works out which is which in about four seconds
## and never needs it explained again.
const RADIO_TINT := Color("#e0a458")
const TRUE_TINT := Color("#6cc08a")

const STAGE := Rect2(0, 96, 1240, 690)
const PANEL_RECT := Rect2(1240, 96, 680, 984)
const ROOM_SIZE := Vector2(330, 250)

const ROOMS := {
	"place:radio": Vector2(60, 150),
	"place:market": Vector2(440, 150),
	"place:precinct": Vector2(820, 150),
	"place:bar": Vector2(60, 440),
	"place:alley": Vector2(440, 440),
}
const LINKS := [
	["place:radio", "place:market"], ["place:market", "place:precinct"],
	["place:market", "place:bar"], ["place:market", "place:alley"],
]

## Cards before and after. The story needs somewhere to begin that is not a
## simulation already in progress, and it needs to end on what a studio would
## have to do next rather than on a dot going out.
## One card per spoken intro line, and the counts must match: tools/godot_demo.py
## measures each line and tells this scene how long to hold its card. A card
## without a line is silence; a line without a card talks over the next one.
const INTRO_CARDS := [
	{"kicker": "vigilant", "text": "UNSCRIPTED", "big": true},
	{"kicker": "what if", "text":
		"Characters lie to the player —\nand the runtime knows it was a lie."},
	{"kicker": "what if", "text":
		"Information takes time to travel,\narrives in different shapes, and never reaches everyone."},
	{"kicker": "what if", "text":
		"A district has a mood,\nand a player who behaves badly there gets less out of it."},
	{"kicker": "the usual answer", "text":
		"More dialogue. More scripted branches.\nA language model behind each character."},
	{"kicker": "why it does not hold", "text":
		"All written in advance. The same for every player.\nEvery character still knows everything at once."},
	{"kicker": "the actual problem", "text":
		"It was never how the characters talk.\nIt is that the world knows nothing and changes nothing."},
	{"kicker": "what is needed", "text":
		"A system that organises itself."},
]
const OUTRO_CARDS := [
	{"kicker": "nothing here was scripted", "text":
		"Seven characters. One killing. One radio station.\nThe rest fell out of who was standing where."},
	{"kicker": "mood", "text":
		"Be unpleasant to a trader: her mood drops 0.95,\nand she is sharper with everyone she speaks to next."},
	{"kicker": "mood spreads", "text":
		"A little of it moves to whoever she talks to.\n3 in 4 of those transfers are second-hand."},
	{"kicker": "forgetting", "text":
		"Being threatened stays reachable for about a week.\nSomething trivial is gone in three days."},
	{"kicker": "opinions change", "text":
		"Catch a source lying and every belief resting on it\nis recomputed across the whole block."},
	{"kicker": "consequences", "text":
		"Hurt one of a trade in front of the others and that\nbelonging becomes who they are. Break a promise; it costs."},
	{"kicker": "what this is for", "text":
		"None of it branched, scripted or hard coded.\nEvery player ends up somewhere different."},
	{"kicker": "what it is", "text":
		"A local service. HTTP and JSON on localhost.\nNo network calls, no third-party packages. One file."},
	{"kicker": "with or without a model", "text":
		"No language model at all, or a local one on any\nOpenAI-compatible endpoint. The runtime decides what may be said."},
	{"kicker": "what it costs", "text":
		"76 KB per character. 2,000 characters across 400 places:\n141 ms per simulated hour. Every layer switches off."},
	{"kicker": "vigilant e.k. · stuttgart", "text": "vigilant-crs.de", "big": true},
]

## Hours the block runs before the questions, and how long an hour is shown for.
const HOURS := 16
const HOUR_SECONDS := 1.15
## How long a claim takes to cross the room, and how long its arrival flashes.
const PULSE_SECONDS := 0.85
const FLASH_SECONDS := 0.7
## One question, answered twice.
const SIDE_SECONDS := 4.4

## The player's lines. Demo content, written for a world the way a level is.
const QUESTIONS := [
	{"text": "ask Otto about the killing",
	 "caption": "You ask the man on the bench who killed the councillor.",
	 "ask": "agent:otto"},
	{"text": "ask Yara about the killing",
	 "caption": "You ask the trader whose stall it happened in front of.",
	 "ask": "agent:yara"},
	{"text": "go precinct"},
	{"text": "ask Officer Dale about the killing",
	 "caption": "You ask the officer holding the case.", "ask": "agent:dale"},
	{"text": "ask Sela about the killing",
	 "caption": "You ask the councillor's own aide.", "ask": "agent:sela"},
	{"text": "go market", "caption": "You go back to the square."},
	{"text": "threaten Yara",
	 "caption": "You lean on the witness.", "ask": "agent:yara"},
	{"text": "ask Yara about the killing",
	 "caption": "You ask her the same question again.", "ask": "agent:yara"},
]

var unscripted
var flags := FlagModel.new()
var font: Font
var bold: Font

var _hours: Array = []
var _tells: Array = []
var _questions: Array = []
var _cast: Array = []
var _names := {}
var _phase := "loading"
var _status := "Connecting to unscripted serve..."
var _clock := 0.0
var _captured := 0
var _question_index := 0
var _last_packet := {}

## Timings handed in by the recorder, which knows how long each line takes to
## say. Without them the scene holds each beat for a constant, the narration is
## laid at constant offsets, and any line longer than the constant talks over the
## next one -- which is exactly what happened: six of sixteen lines overlapped,
## by as much as three and a half seconds.
var _running_override := -1.0
var _sides: Array = []
var _intro: Array = []          ## seconds per intro card
var _outro: Array = []          ## seconds per outro card

var _pulses: Array = []
var _threads: Array = []
var _flashes := {}


func _ready() -> void:
	font = SystemFont.new()
	font.font_names = PackedStringArray(["Inter", "DejaVu Sans", "Liberation Sans"])
	bold = SystemFont.new()
	bold.font_names = font.font_names
	bold.font_weight = 700

	var url := "http://127.0.0.1:8080"
	var token := "dev"
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--url="):
			url = argument.substr(6)
		elif argument.begins_with("--token="):
			token = argument.substr(8)
		elif argument.begins_with("--running="):
			_running_override = float(argument.substr(10))
		elif argument.begins_with("--sides="):
			for piece in argument.substr(8).split(","):
				if piece != "":
					_sides.append(float(piece))
		elif argument.begins_with("--intro="):
			for piece in argument.substr(8).split(","):
				if piece != "":
					_intro.append(float(piece))
		elif argument.begins_with("--outro="):
			for piece in argument.substr(8).split(","):
				if piece != "":
					_outro.append(float(piece))

	unscripted = UnscriptedClient.new()
	add_child(unscripted)
	unscripted.failed.connect(func(message: String) -> void:
		_status = message
		_phase = "failed"
		queue_redraw())
	unscripted.connected.connect(func(capabilities: Dictionary) -> void:
		_status = "Runtime %s. Running the block..." % capabilities.get(
			"runtime_version", "?")
		_capture_hour())
	unscripted.knowledge.connect(_on_knowledge)
	unscripted.spoke.connect(_on_spoke)
	unscripted.connect_to(url, token)


# --------------------------------------------------------------- capture ----
#
# An hour at a time, so playback has a position and a belief for every moment and
# never waits on the network.

func _capture_hour() -> void:
	if _captured >= HOURS:
		_capture_question()
		return
	_status = "Running hour %d of %d..." % [_captured + 1, HOURS]
	queue_redraw()
	unscripted.advance(60)
	unscripted.refresh_knowledge()


func _capture_question() -> void:
	if _question_index >= QUESTIONS.size():
		_begin_playback()
		return
	_status = "Asking question %d of %d..." % [_question_index + 1, QUESTIONS.size()]
	queue_redraw()
	unscripted.say(QUESTIONS[_question_index].text)
	unscripted.refresh_knowledge()


func _on_spoke(packet: Dictionary) -> void:
	_last_packet = packet


func _on_knowledge(state: Dictionary) -> void:
	if _phase != "loading":
		return
	_read_cast(state)
	var where := {}
	for room in state.get("occupancy", []):
		for person in room.get("people", []):
			if not str(person.get("id", "")).ends_with("player_1"):
				where[person.get("id", "")] = room.get("place", "")

	if _captured < HOURS:
		_hours.append({"where": where, "holders": _holders(state)})
		_captured += 1
		if _captured >= HOURS:
			# The transmission log is cumulative and stamped, so it is read once
			# at the end and bucketed rather than diffed hour by hour.
			_read_tells(state)
		_capture_hour()
		return

	_questions.append({
		"caption": QUESTIONS[_question_index].get("caption", ""),
		"ask": QUESTIONS[_question_index].get("ask", ""),
		"where": where,
		"holders": _holders(state),
		"packet": _last_packet.duplicate(true),
	})
	_last_packet = {}
	_question_index += 1
	_capture_question()


func _read_cast(state: Dictionary) -> void:
	if not _cast.is_empty():
		return
	for room in state.get("occupancy", []):
		for person in room.get("people", []):
			var id: String = person.get("id", "")
			if id.ends_with("player_1"):
				continue
			_names[id] = person.get("name", id)
			_cast.append({"id": id, "name": person.get("name", id)})
	_cast.sort_custom(func(a, b): return a.name < b.name)


func _read_tells(state: Dictionary) -> void:
	var earliest := -1
	for row in state.get("transmissions", []):
		if row.get("proposition", "") != FACT:
			continue
		var at: int = row.get("world_time", 0)
		earliest = at if earliest < 0 else mini(earliest, at)
	for row in state.get("transmissions", []):
		if row.get("proposition", "") != FACT:
			continue
		var hour := int(float(row.get("world_time", 0) - earliest) / 60.0)
		_tells.append({
			"from": row.get("from", ""), "to": row.get("to", ""),
			"hour": clampi(hour, 0, HOURS - 1),
			"distorted": bool(row.get("distorted", false)),
			"spawned": false,
		})


func _holders(state: Dictionary) -> Dictionary:
	## Per person, the version of the claim they hold most strongly. Somebody who
	## has heard both keeps the stronger one here and is marked as torn, because a
	## map cannot draw two answers in one dot and the panel says the rest.
	var out := {}
	for fact in state.get("facts", []):
		if fact.get("predicate", "") != FACT:
			continue
		var version := _version_of(fact.get("text", ""))
		if version == "":
			continue
		for holder in fact.get("holders", []):
			var id: String = holder.get("agent", "")
			var kept: Dictionary = out.get(id, {})
			var entry := {"holder": holder, "version": version,
				"prob": holder.get("prob", 0.0)}
			if kept.is_empty():
				out[id] = entry
			else:
				out[id] = {"holder": entry.prob > kept.prob if entry.holder else kept.holder,
					"version": version if entry.prob > kept.prob else kept.version,
					"prob": maxf(entry.prob, kept.prob),
					"holder2": kept, "torn": true}
				out[id]["holder"] = holder if entry.prob > kept.prob else kept.holder
	return out


func _version_of(text: String) -> String:
	if text.find(RADIO_VERSION) >= 0:
		return RADIO_VERSION
	if text.find(TRUE_VERSION) >= 0:
		return TRUE_VERSION
	return ""


# -------------------------------------------------------------- playback ----

func _begin_playback() -> void:
	var ids: Array = []
	for member in _cast:
		ids.append(member.id)
	flags.broadcast(FACT, ids)
	_phase = "playing"
	_clock = 0.0


func _intro_seconds() -> float:
	var total := 0.0
	for card in _intro:
		total += card
	return total


func _running_seconds() -> float:
	return _running_override if _running_override > 0.0 else HOURS * HOUR_SECONDS


func _process(delta: float) -> void:
	if _phase == "playing":
		var before := _clock
		_clock += delta
		_spawn_between(before, _clock)
		_advance_effects(delta)
		var outro := 0.0
		for card in _outro:
			outro += card
		if _clock > _intro_seconds() + _running_seconds() + _questions_span() + outro + 0.5:
			get_tree().quit()
	queue_redraw()


func _hour_now() -> float:
	## The hours are spread across however long the running section lasts, so the
	## block keeps moving at whatever pace the voice sets.
	var span := _running_seconds()
	var since := _clock - _intro_seconds()
	return clampf(since / span * float(HOURS), 0.0, float(HOURS) - 0.001)


func _card_now() -> Dictionary:
	## Which card, if any, is on screen. -1 means the simulation is showing.
	var at := _clock
	for index in _intro.size():
		if at < _intro[index]:
			return {"cards": INTRO_CARDS, "index": index}
		at -= _intro[index]
	var after := _clock - _intro_seconds() - _running_seconds() - _questions_span()
	if after >= 0.0:
		for index in _outro.size():
			if after < _outro[index]:
				return {"cards": OUTRO_CARDS, "index": index}
			after -= _outro[index]
		return {"cards": OUTRO_CARDS, "index": OUTRO_CARDS.size() - 1}
	return {"cards": [], "index": -1}


func _questions_span() -> float:
	var total := 0.0
	for side in _sides:
		total += side
	if total <= 0.0:
		total = _questions.size() * SIDE_SECONDS * 2.0
	return total


func _question_now() -> Dictionary:
	var elapsed := _clock - _intro_seconds() - _running_seconds()
	if elapsed < 0.0:
		return {"index": -1, "flags": false}
	if _sides.is_empty():
		var slot := int(elapsed / SIDE_SECONDS)
		return {"index": mini(slot / 2, _questions.size() - 1), "flags": slot % 2 == 0}
	# Each half-beat lasts as long as the line spoken over it.
	var running := 0.0
	for index in _sides.size():
		running += _sides[index]
		if elapsed < running:
			return {"index": mini(int(index / 2), _questions.size() - 1),
				"flags": index % 2 == 0}
	return {"index": _questions.size() - 1, "flags": false}


func _spawn_between(from_time: float, to_time: float) -> void:
	if from_time >= _running_seconds():
		return
	var last := int(to_time / HOUR_SECONDS)
	for tell in _tells:
		if tell.spawned or tell.hour > last:
			continue
		tell.spawned = true
		_pulses.append({"from": tell["from"], "to": tell["to"],
			"distorted": tell["distorted"], "age": 0.0, "landed": false})


func _advance_effects(delta: float) -> void:
	for pulse in _pulses:
		pulse.age += delta
		if pulse.age >= PULSE_SECONDS and not pulse.landed:
			pulse.landed = true
			_flashes[pulse["to"]] = FLASH_SECONDS
			_threads.append({"from": pulse["from"], "to": pulse["to"],
				"distorted": pulse["distorted"]})
	_pulses = _pulses.filter(func(p): return p.age < PULSE_SECONDS)
	for id in _flashes.keys():
		_flashes[id] -= delta
		if _flashes[id] <= 0.0:
			_flashes.erase(id)


# ------------------------------------------------------------------ draw ----

func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, Vector2(1920, 1080)), BG)
	if _phase != "playing":
		_draw_header(false, false)
		_text(Vector2(60, 420), _status, 30, FG if _phase != "failed" else LIE)
		if _phase == "failed":
			_text(Vector2(60, 470), "Start it with:  unscripted serve --world-pack worldpacks/cyberpunk-block --auth-token dev", 22, DIM)
		return

	# A card takes the whole screen. The story needs somewhere to begin that is
	# not a simulation already in progress, and somewhere to end that is not a dot
	# going out.
	var card := _card_now()
	if card.index >= 0:
		_draw_card(card.cards[card.index])
		return

	var question := _question_now()
	var running: bool = question.index < 0
	var showing_flags: bool = question.flags and not running
	_draw_header(showing_flags, running)
	_draw_district(question, showing_flags, running)
	_draw_panel(question, showing_flags, running)
	_draw_caption(question, showing_flags, running)


func _draw_card(card: Dictionary) -> void:
	var centre := Vector2(960, 540)
	var kicker: String = card.get("kicker", "")
	var big: bool = card.get("big", false)
	if kicker != "":
		var kicker_size := 20
		var width := _spaced_width(kicker.to_upper(), kicker_size, 6.0)
		_text(centre + Vector2(-width / 2.0, -110), kicker.to_upper(), kicker_size,
			HOT, 6.0)

	var size := 64 if big else 42
	var lines: PackedStringArray = String(card.get("text", "")).split("\n")
	var y := -20.0 if lines.size() < 2 else -60.0
	for line in lines:
		var width := bold.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		_text(centre + Vector2(-width / 2.0, y), line, size, FG, 0.0, true)
		y += size * 1.35

	# A rule under a title card, so the frame has a shape rather than floating.
	if big:
		draw_line(centre + Vector2(-160, y - 10), centre + Vector2(160, y - 10),
			Color(HOT, 0.5), 2.0)


func _spaced_width(text: String, size: int, spacing: float) -> float:
	var total := 0.0
	for index in text.length():
		total += bold.get_string_size(text[index], HORIZONTAL_ALIGNMENT_LEFT, -1,
			size).x + spacing
	return total


func _draw_header(showing_flags: bool, running: bool) -> void:
	draw_rect(Rect2(0, 0, 1920, 96), PANEL)
	draw_line(Vector2(0, 96), Vector2(1920, 96), LINE, 2.0)
	_text(Vector2(46, 40), "A COUNCILLOR IS SHOT IN THE SQUARE", 16, DIM, 4.0)
	_text(Vector2(46, 74), "Two answers, and who ends up with which", 27, FG)
	if _phase != "playing":
		return
	var label := "THE BLOCK IS RUNNING" if running else ("FLAGS" if showing_flags else "UNSCRIPTED")
	var tint: Color = COOL if running else (DIM if showing_flags else HOT)
	var width := bold.get_string_size(label, HORIZONTAL_ALIGNMENT_LEFT, -1, 30).x
	draw_rect(Rect2(1860 - width - 34, 26, width + 34, 46), tint, false, 2.0)
	_text(Vector2(1860 - width - 17, 58), label, 30, tint, 0.0, true)
	var sub := ""
	if running:
		sub = "hour %d of %d" % [int(_hour_now()) + 1, HOURS]
	else:
		sub = "one boolean per fact" if showing_flags else "the runtime decides"
	_text(Vector2(1860 - font.get_string_size(sub, HORIZONTAL_ALIGNMENT_LEFT, -1, 17).x, 88), sub, 17, DIM)


func _draw_district(question: Dictionary, showing_flags: bool, running: bool) -> void:
	for link in LINKS:
		draw_line(_room_centre(link[0]), _room_centre(link[1]), LINE, 3.0)
	for place in ROOMS:
		var origin: Vector2 = STAGE.position + ROOMS[place]
		draw_rect(Rect2(origin, ROOM_SIZE), PANEL)
		draw_rect(Rect2(origin, ROOM_SIZE), LINE, false, 2.0)
		_text(origin + Vector2(18, 34), _place_label(place).to_upper(), 15, DIM, 3.0)

	var placement := _placement(question, running)

	# Threads first, so people draw over them. In the flag column there are none:
	# not a flourish, the honest picture.
	if not showing_flags:
		for thread in _threads:
			var a: Vector2 = placement.get(thread["from"], Vector2.ZERO)
			var b: Vector2 = placement.get(thread["to"], Vector2.ZERO)
			if a == Vector2.ZERO or b == Vector2.ZERO:
				continue
			draw_line(a, b, Color(BAD if thread["distorted"] else HOT, 0.22), 2.0)

	for member in _cast:
		var at: Vector2 = placement.get(member.id, Vector2.ZERO)
		if at != Vector2.ZERO:
			_draw_person(member, at, question, showing_flags, running)

	if not showing_flags:
		for pulse in _pulses:
			var a: Vector2 = placement.get(pulse["from"], Vector2.ZERO)
			var b: Vector2 = placement.get(pulse["to"], Vector2.ZERO)
			if a == Vector2.ZERO or b == Vector2.ZERO:
				continue
			var progress := clampf(pulse.age / PULSE_SECONDS, 0.0, 1.0)
			var eased := progress * progress * (3.0 - 2.0 * progress)
			var tint: Color = BAD if pulse["distorted"] else HOT
			var head := a.lerp(b, eased)
			draw_line(a, head, Color(tint, 0.45), 3.0)
			draw_circle(head, 9.0 - 3.0 * eased, tint)
			draw_arc(head, 16.0 + 16.0 * eased, 0.0, TAU, 32,
				Color(tint, 0.55 * (1.0 - eased)), 2.0)


func _placement(question: Dictionary, running: bool) -> Dictionary:
	var out := {}
	if running:
		var hour := _hour_now()
		var index := mini(int(hour), _hours.size() - 1)
		var next_index := mini(index + 1, _hours.size() - 1)
		var blend := hour - float(int(hour))
		var eased := blend * blend * (3.0 - 2.0 * blend)
		var here: Dictionary = _hours[index].where
		var there: Dictionary = _hours[next_index].where
		for member in _cast:
			var a: String = here.get(member.id, "")
			if a == "":
				continue
			var b: String = there.get(member.id, a)
			out[member.id] = _seat(a, member.id, here).lerp(
				_seat(b, member.id, there), eased)
		return out

	var where: Dictionary = _questions[question.index].where if question.index >= 0 else {}
	for member in _cast:
		var place: String = where.get(member.id, "")
		if place != "":
			out[member.id] = _seat(place, member.id, where)
	return out


func _seat(place: String, agent_id: String, where: Dictionary) -> Vector2:
	if not ROOMS.has(place):
		return Vector2.ZERO
	var here: Array = []
	for member in _cast:
		if where.get(member.id, "") == place:
			here.append(member.id)
	var slot := maxi(here.find(agent_id), 0)
	return STAGE.position + ROOMS[place] + Vector2(72 + (slot % 3) * 96,
		100 + int(slot / 3) * 78)


func _draw_person(member: Dictionary, at: Vector2, question: Dictionary,
				  showing_flags: bool, running: bool) -> void:
	var probability := 0.0
	var knows := false
	var version := ""
	var torn := false
	if showing_flags:
		knows = flags.knows(member.id, FACT)
		probability = 1.0 if knows else 0.0
	else:
		var holders: Dictionary = _hours[mini(int(_hour_now()), _hours.size() - 1)].holders \
			if running else _questions[question.index].holders
		var entry: Dictionary = holders.get(member.id, {})
		knows = not entry.is_empty()
		probability = entry.get("prob", 0.0)
		version = entry.get("version", "")
		torn = entry.get("torn", false)

	var tint: Color = TRUE_TINT if version == TRUE_VERSION else RADIO_TINT
	var fill := Color("#232833")
	if knows:
		fill = Color(tint, 1.0).darkened(0.55).lerp(tint,
			clampf((probability - 0.42) / 0.46, 0.0, 1.0))

	# An arrival flashes, so a claim landing is something you SEE rather than
	# something you work out afterwards by comparing two frames.
	var flash: float = _flashes.get(member.id, 0.0)
	if flash > 0.0:
		var strength := flash / FLASH_SECONDS
		draw_arc(at, 30.0 + 24.0 * (1.0 - strength), 0.0, TAU, 48,
			Color(HOT, strength * 0.85), 3.0)

	draw_circle(at, 27.0, fill)
	if not knows:
		draw_arc(at, 27.0, 0.0, TAU, 48, Color("#39404e"), 2.0)
	elif not showing_flags:
		# A gauge: "believes it" and "is sure of it" are different states, and a
		# fill alone cannot tell them apart at a glance.
		draw_arc(at, 34.0, -PI / 2.0, -PI / 2.0 + TAU * probability, 48,
			Color(tint, 0.8), 3.0)
		if torn:
			# Somebody holding both answers at once is the state a single truth
			# value cannot represent, so it gets a mark of its own.
			draw_arc(at, 40.0, PI * 0.15, PI * 0.85, 32, Color(COOL, 0.9), 3.0)

	if _has_lied(member.id, question):
		draw_circle(at + Vector2(20, -20), 7.5,
			LIE if not showing_flags else Color("#3a3a3a"))

	if question.index >= 0 and _questions[question.index].get("ask", "") == member.id:
		draw_arc(at, 40.0, 0.0, TAU, 64, FG, 2.5)

	var width := font.get_string_size(member.name, HORIZONTAL_ALIGNMENT_LEFT, -1, 17).x
	_text(at + Vector2(-width / 2.0, 52), member.name, 17, FG if knows else DIM)


func _has_lied(agent_id: String, question: Dictionary) -> bool:
	for index in range(0, question.index + 1):
		if index >= _questions.size():
			break
		var packet: Dictionary = _questions[index].get("packet", {}).get("avatar", {})
		if packet.get("speaker_id", "") == agent_id and packet.get("honesty", "") == "lie":
			return true
	return false


func _draw_panel(question: Dictionary, showing_flags: bool, running: bool) -> void:
	draw_rect(PANEL_RECT, PANEL)
	draw_line(PANEL_RECT.position, PANEL_RECT.position + Vector2(0, PANEL_RECT.size.y), LINE, 2.0)
	var x := PANEL_RECT.position.x + 40
	var y := PANEL_RECT.position.y + 62

	if running:
		var holders: Dictionary = _hours[mini(int(_hour_now()), _hours.size() - 1)].holders
		var radio := 0
		var truth := 0
		for id in holders:
			if holders[id].get("version", "") == TRUE_VERSION:
				truth += 1
			else:
				radio += 1
		_text(Vector2(x, y), "WHAT THEY BELIEVE", 15, DIM, 3.0)
		y += 46
		draw_circle(Vector2(x + 11, y - 7), 9.0, RADIO_TINT)
		_text(Vector2(x + 30, y), "%d think it was the east-side kids" % radio, 22, FG)
		y += 34
		draw_circle(Vector2(x + 11, y - 7), 9.0, TRUE_TINT)
		_text(Vector2(x + 30, y), "%d think it was contract men" % truth, 22, FG)
		y += 30
		_text(Vector2(x + 30, y), "one of them was standing in it", 18, DIM)
		y += 56
		_text(Vector2(x, y), "WHO TOLD WHOM", 15, DIM, 3.0)
		y += 42
		if _threads.is_empty():
			_text(Vector2(x, y), "nothing has been passed on yet", 20, DIM)
		for index in range(maxi(0, _threads.size() - 9), _threads.size()):
			var thread: Dictionary = _threads[index]
			_text(Vector2(x, y), "%s  →  %s" % [_names.get(thread["from"], "?"),
				_names.get(thread["to"], "?")], 20,
				BAD if thread["distorted"] else FG)
			if thread["distorted"]:
				_text(Vector2(x + 320, y), "changed on the way", 17, BAD)
			y += 32
		return

	var asked: String = _questions[question.index].get("ask", "")
	if asked == "":
		_text(Vector2(x, y), "WHO KNOWS IT", 15, DIM, 3.0)
		y += 52
		var count := 0
		for member in _cast:
			var knows: bool = flags.knows(member.id, FACT) if showing_flags \
				else _questions[question.index].holders.has(member.id)
			if knows:
				count += 1
		_text(Vector2(x, y), "%d of %d" % [count, _cast.size()], 46, FG, 0.0, true)
		y += 56
		_text(Vector2(x, y), "the channel fired" if showing_flags
			else "only the people who were listening", 20, DIM)
		if showing_flags:
			y += 52
			_text(Vector2(x, y), "and no record of who told whom", 20, Color("#5c626e"))
		return

	_text(Vector2(x, y), "YOU ASKED", 15, DIM, 3.0)
	y += 42
	_text(Vector2(x, y), _names.get(asked, asked), 34, FG, 0.0, true)
	y += 58

	var rows: Array = []
	if showing_flags:
		var knows: bool = flags.knows(asked, FACT)
		rows = [
			["Do they know it?", "yes" if knows else "no", knows],
			["How sure are they?", "there is no third state", false],
			["Who told them?", "nowhere to put it", false],
			["Which version?", "nowhere to put it", false],
			["Was it a lie?", "nowhere to put it", false],
		]
	else:
		var holder: Dictionary = _questions[question.index].holders.get(asked, {})
		var packet: Dictionary = _questions[question.index].get("packet", {}).get("avatar", {})
		var known := not holder.is_empty()
		rows = [
			["Do they know it?", "yes" if known else "no, never heard it", known],
			["How sure are they?", ("%.2f" % holder.get("prob", 0.0)) if known else "—", known],
			["Who told them?", str(holder.get("origin", "—")) if known else "—", known],
			["Times told", str(holder.get("times_heard", 0)) if known else "—", known],
			["Independent sources", str(holder.get("independent_origins", 0)) if known else "—", known],
		]
		if packet.get("honesty", "") != "":
			rows.append(["Was the answer honest?", packet.get("honesty", ""),
				packet.get("honesty", "") == "honest"])

	for row in rows:
		_text(Vector2(x, y), row[0], 19, DIM)
		var value := str(row[1])
		var tint: Color = FG if row[2] else DIM
		if value == "nowhere to put it":
			tint = Color("#5c626e")
		if value == "lie":
			tint = LIE
		var width := bold.get_string_size(value, HORIZONTAL_ALIGNMENT_LEFT, -1, 21).x
		_text(Vector2(PANEL_RECT.end.x - 40 - width, y), value, 21, tint, 0.0, true)
		y += 30
		draw_line(Vector2(x, y - 8), Vector2(PANEL_RECT.end.x - 40, y - 8), LINE, 1.0)
		y += 18

	var spoken: Dictionary = _questions[question.index].get("packet", {}).get("avatar", {})
	if showing_flags:
		# The flag column must not show the runtime's sentence. A boolean has one
		# line per fact and gives it to everybody, in the same words, however they
		# asked and whatever they did last time -- and showing the generated line
		# here would quietly credit flags with something they did not do.
		y += 26
		_text(Vector2(x, y), "WHAT THEY SAY", 15, DIM, 3.0)
		y += 40
		_wrapped(Vector2(x, y), "the one line this fact has, to anyone, always",
			22, Color("#5c626e"), PANEL_RECT.size.x - 80)
	elif spoken.has("text"):
		y += 26
		_text(Vector2(x, y), "WHAT THEY SAID", 15, DIM, 3.0)
		y += 40
		_wrapped(Vector2(x, y), "“%s”" % spoken.get("text", ""), 22, FG, PANEL_RECT.size.x - 80)


func _draw_caption(question: Dictionary, showing_flags: bool, running: bool) -> void:
	var top := STAGE.end.y + 24
	draw_line(Vector2(0, top - 24), Vector2(PANEL_RECT.position.x, top - 24), LINE, 2.0)
	var caption := ""
	var note := ""
	if running:
		caption = "The block goes about its day. Nobody is scripting these conversations."
		note = "Each line is a claim passing from one person to another, and it stays as the route it took."
	else:
		caption = _questions[question.index].get("caption", "")
		note = "A boolean is set at a moment, for everyone who can read it." if showing_flags \
			else "Every belief keeps the route it took, so any of it can be asked about later."
	if caption != "":
		_wrapped(Vector2(60, top + 40), caption, 27, FG, PANEL_RECT.position.x - 120)
	_text(Vector2(60, top + 150), note, 20, DIM)


# --------------------------------------------------------------- helpers ----

func _room_centre(place: String) -> Vector2:
	return STAGE.position + ROOMS[place] + ROOM_SIZE / 2.0


func _place_label(place: String) -> String:
	return place.trim_prefix("place:").replace("_", " ")


func _text(at: Vector2, text: String, size: int, colour: Color,
		   spacing: float = 0.0, use_bold: bool = false) -> void:
	var face: Font = bold if use_bold else font
	if spacing <= 0.0:
		draw_string(face, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)
		return
	var x := at.x
	for index in text.length():
		var glyph := text[index]
		draw_string(face, Vector2(x, at.y), glyph, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)
		x += face.get_string_size(glyph, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x + spacing


func _wrapped(at: Vector2, text: String, size: int, colour: Color, width: float) -> void:
	var line := ""
	var y := at.y
	for word in text.split(" "):
		var candidate := word if line == "" else line + " " + word
		if font.get_string_size(candidate, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width:
			draw_string(font, Vector2(at.x, y), line, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)
			y += size * 1.35
			line = word
		else:
			line = candidate
	if line != "":
		draw_string(font, Vector2(at.x, y), line, HORIZONTAL_ALIGNMENT_LEFT, -1, size, colour)
