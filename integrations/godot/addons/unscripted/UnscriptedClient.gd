extends Node
class_name UnscriptedClient

## Every endpoint a shipping game needs, in one place.
##
## The client in the demo project covers four endpoints, which is right for a
## demo and is not an integration: it cannot save, cannot send a gameplay event,
## and cannot answer an action intent. Those are the three things a real game
## does most. This is the complete one.
##
## Everything is asynchronous and queued -- one request at a time, in order, so a
## turn cannot overtake the event that caused it. Nothing here blocks a frame.
##
##     var host := UnscriptedHost.new()
##     var unscripted := UnscriptedClient.new()
##     add_child(host); add_child(unscripted)
##     host.ready_at.connect(unscripted.connect_to)
##     host.start("res://worldpacks/my-town", ["pursuit", "promises"])

## A character answered. `avatar` carries the line, whether it was honest, what
## it asserted and to whom, plus face and prosody.
signal spoke(avatar: Dictionary)
## One character as a shipped game may see them: mood, face, and their regard
## for the player -- trust, liking, familiarity, what they think of your conduct
## and, with the standing layer on, one warmth number to colour them by.
signal character_state(character: Dictionary)
## The world clock, in minutes, after a turn. Every game that shows a time of
## day needs this, and the turn response carried it all along -- the client read
## the answer out of the body and dropped the clock on the floor.
signal clock(world_time: int)
## The world advanced. `trace` is what happened, by reason code.
signal advanced(trace: Dictionary)
## A gameplay event was accepted, with who perceived it.
signal event_accepted(receipt: Dictionary)
## The runtime wants your engine to carry something out.
signal actions_pending(intents: Array)
## The save blob, ready to go into your own save file.
signal state_exported(blob: Dictionary)
## A load was inspected or performed; `report` says usable/dropped/unsaved.
signal state_report(report: Dictionary)
## Open and recently settled promises.
signal promises(report: Dictionary)
## Something went wrong, with a message worth showing a developer.
signal failed(reason: String)

var base_url := ""
var _token := ""
var _queue: Array = []
var _busy := false


func connect_to(url: String, auth_token: String) -> void:
	base_url = url.rstrip("/")
	_token = auth_token
	# Ask what this build can do before assuming any of it. "Off" and "not in
	# this build" look identical from outside, and finding out the hard way
	# means writing a HUD against a mechanic that is not running.
	_fetch("/capabilities", func(body: Dictionary) -> void:
		var versions: Array = body.get("contract_versions", [])
		if not versions.has("2.0.0"):
			failed.emit("This runtime does not speak contract 2.0.0; got %s"
				% str(versions)))


# -------------------------------------------------------------- dialogue --

## Minutes on the world clock as of the last turn. 0 before the first one.
var world_time := 0


func say(text: String) -> void:
	_post("/v2/avatar/turn", {"text": text}, func(body: Dictionary) -> void:
		if body.has("world_time"):
			world_time = int(body["world_time"])
			clock.emit(world_time)
		spoke.emit(body.get("avatar", {})))


# --------------------------------------------------------------- gameplay --

func fetch_character(agent_id: String) -> void:
	## READ ONE CHARACTER, IN A SHIPPING BUILD.
	##
	## Every endpoint this client had was something you did TO the world; there
	## was no way to ask what a character currently feels, which is what a
	## portrait, a greeting, a journal or a companion's face is made of. The
	## debug `/state/agent` carries beliefs, secrets and reason traces and is
	## rightly switched off in a shipped build, so this uses the narrow one:
	## who they are, their mood, their face, and their regard for the player.
	_fetch("/v2/state/character?id=" + agent_id.uri_encode(),
		func(body: Dictionary) -> void:
			character_state.emit(body))


func send_event(type: String, payload: Dictionary,
		location := "", actor := "") -> void:
	## THE ONE YOU WILL USE MOST. A door forced, a body found, a payment made:
	## send what characters could plausibly perceive or hear about, and let the
	## runtime decide who actually did.
	var body := {"type": type, "payload": payload}
	if location != "":
		body["location"] = location
	if actor != "":
		body["actor"] = actor
	_post("/event", body, func(receipt: Dictionary) -> void:
		event_accepted.emit(receipt))


func advance(minutes: int) -> void:
	_post("/advance", {"minutes": minutes}, func(body: Dictionary) -> void:
		advanced.emit(body.get("last_trace", {})))


func discredit(source_id: String, factor := 0.35, reason := "caught out") -> void:
	_post("/v2/discredit",
		{"source": source_id, "factor": factor, "reason": reason},
		func(_body: Dictionary) -> void: pass)


# ---------------------------------------------------------- what it asks --

func fetch_pending_actions() -> void:
	_fetch("/v2/actions/pending", func(body: Dictionary) -> void:
		actions_pending.emit(body.get("intents", [])))


func report_action(intent_id: String, status: String, detail := "") -> void:
	## SUCCEEDED, FAILED, INTERRUPTED or UNREACHABLE. Answer every intent: a
	## bridge that is enabled and never answered is a cast that never arrives
	## anywhere.
	_post("/v2/actions/%s/result" % intent_id,
		{"status": status, "detail": detail},
		func(_body: Dictionary) -> void: pass)


func settle_promise(promise_id: String, kept: bool, note := "") -> void:
	## Your game knows whether the player handed over the money. Say so, rather
	## than hoping an NPC was paying attention.
	_post("/v2/promises/%s/settle" % promise_id, {"kept": kept, "note": note},
		func(_body: Dictionary) -> void: pass)


func fetch_promises() -> void:
	_fetch("/v2/promises", func(body: Dictionary) -> void: promises.emit(body))


# ------------------------------------------------------------ save / load --

func export_state() -> void:
	## Put the result into YOUR save file, next to everything else you persist.
	## About 11 kB gzipped for eight characters.
	_fetch("/v2/state/export", func(body: Dictionary) -> void:
		state_exported.emit(body))


func inspect_state(blob: Dictionary) -> void:
	## What loading it WOULD do. Call this on a load screen before offering
	## "continue": `usable` is a field, not an exception.
	_post("/v2/state/inspect", {"state": blob}, func(body: Dictionary) -> void:
		state_report.emit(body))


func import_state(blob: Dictionary) -> void:
	_post("/v2/state/import", {"state": blob}, func(body: Dictionary) -> void:
		state_report.emit(body))


# ------------------------------------------------------------- transport --

func _fetch(path: String, on_done: Callable) -> void:
	## NOT `_get`. Object already has a virtual `_get(StringName) -> Variant`,
	## and overriding it with a different signature makes Godot refuse to parse
	## the whole script -- so the addon would have failed to load in every
	## project that used it. Found by putting it in a real scene, which is the
	## only way this class of mistake ever surfaces.
	_queue.append({"method": HTTPClient.METHOD_GET, "path": path,
		"body": "", "on_done": on_done})
	_pump()


func _post(path: String, body: Dictionary, on_done: Callable) -> void:
	_queue.append({"method": HTTPClient.METHOD_POST, "path": path,
		"body": JSON.stringify(body), "on_done": on_done})
	_pump()


func _pump() -> void:
	if _busy or _queue.is_empty():
		return
	if base_url == "":
		failed.emit("Not connected yet. Wait for UnscriptedHost.ready_at.")
		_queue.clear()
		return
	_busy = true
	var job: Dictionary = _queue.pop_front()
	var request := HTTPRequest.new()
	add_child(request)
	request.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
				bytes: PackedByteArray) -> void:
			request.queue_free()
			_busy = false
			if result != HTTPRequest.RESULT_SUCCESS:
				failed.emit("No answer from %s%s." % [base_url, job.path])
				# EVERY REQUEST ANSWERS EXACTLY ONCE, success or not. Without
				# this a failed say() emitted `failed` and never `spoke`, so any
				# game that awaited the reply -- the obvious way to write it --
				# waited for the rest of the session with nothing on screen and
				# no error. Found by writing exactly that game.
				job.on_done.call({})
				_pump()
				return
			var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
			var body: Dictionary = parsed if typeof(parsed) == TYPE_DICTIONARY else {}
			if code >= 400:
				# The service always answers with {error, code}, so a failure
				# says what it was rather than only how it failed.
				failed.emit("%s %d %s: %s" % [job.path, code,
					body.get("code", "error"), body.get("error", "")])
				job.on_done.call({})
			else:
				job.on_done.call(body)
			_pump())
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Authorization: Bearer %s" % _token,
	])
	var error := request.request(base_url + job.path, headers, job.method, job.body)
	if error != OK:
		request.queue_free()
		_busy = false
		failed.emit("Could not reach %s (error %d)." % [base_url, error])
