class_name Unscripted
extends Node

## The engine side of the bridge, small enough to read in one sitting.
##
## Everything here is one of four HTTP calls against a running service:
##
##     GET  /capabilities          what this build can do, asked before anything
##     POST /v2/avatar/turn        a player line -> what a character says, plus
##                                 whether it was honest and what it committed to
##     GET  /v2/state/knowledge    who knows what, on whose word (debug only)
##     POST /v2/discredit          the player proves somebody lied
##
## It deliberately does NOT fall back to anything when the service is absent. A
## demo that quietly invents an answer when the runtime is not there is a demo
## that will one day be shown with the runtime not there, and nobody will notice
## until the questions start.

signal connected(capabilities: Dictionary)
signal failed(message: String)
signal spoke(packet: Dictionary)
signal knowledge(state: Dictionary)
signal revised(outcome: Dictionary)

const CONTRACT := "2.0.0"

var base_url := "http://127.0.0.1:8080"
var token := "dev"

var _queue: Array[Dictionary] = []
var _busy := false


func connect_to(url: String, auth_token: String) -> void:
	base_url = url
	token = auth_token
	_fetch("/capabilities", func(body: Dictionary) -> void:
		var versions: Array = body.get("contract_versions", [])
		if not versions.has(CONTRACT):
			failed.emit("This runtime speaks %s; this plugin needs %s."
				% [", ".join(PackedStringArray(versions)), CONTRACT])
			return
		connected.emit(body))


func say(text: String) -> void:
	_send("/v2/avatar/turn", {"text": text}, func(body: Dictionary) -> void:
		spoke.emit(body))


func advance(minutes: int) -> void:
	# Deliberately does NOT refresh on its own. One call, one signal: a helper
	# that also emits `knowledge` meant a caller doing both consumed two beats per
	# answer, and the demo silently played back five of its eight steps.
	_send("/advance", {"minutes": minutes}, func(_body: Dictionary) -> void:
		pass)


func discredit(agent_id: String) -> void:
	_send("/v2/discredit", {"source": agent_id, "factor": 0.35,
		"reason": "caught out"}, func(body: Dictionary) -> void:
		revised.emit(body))


func refresh_knowledge() -> void:
	_fetch("/v2/state/knowledge", func(body: Dictionary) -> void:
		knowledge.emit(body))


# --------------------------------------------------------------- plumbing ----
#
# One request at a time, in order. A demo that fires six overlapping requests and
# renders whichever returns first is a demo that behaves differently on a slow
# machine, which is exactly the machine it will be shown on.

func _fetch(path: String, on_done: Callable) -> void:
	_queue.append({"method": HTTPClient.METHOD_GET, "path": path,
		"body": "", "on_done": on_done})
	_pump()


func _send(path: String, body: Dictionary, on_done: Callable) -> void:
	_queue.append({"method": HTTPClient.METHOD_POST, "path": path,
		"body": JSON.stringify(body), "on_done": on_done})
	_pump()


func _pump() -> void:
	if _busy or _queue.is_empty():
		return
	_busy = true
	var job: Dictionary = _queue.pop_front()
	var request := HTTPRequest.new()
	add_child(request)
	request.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
			 payload: PackedByteArray) -> void:
			request.queue_free()
			_busy = false
			if result != HTTPRequest.RESULT_SUCCESS:
				failed.emit("No answer from %s. Is `unscripted serve` running?" % base_url)
				_pump()
				return
			var parsed: Variant = JSON.parse_string(
				payload.get_string_from_utf8())
			if typeof(parsed) != TYPE_DICTIONARY:
				failed.emit("%s returned something that is not JSON." % job.path)
				_pump()
				return
			if code >= 400:
				# The service answers a client mistake with a typed code rather
				# than a 500, so it is worth showing rather than swallowing.
				failed.emit("%s: %s" % [parsed.get("code", code),
					parsed.get("error", "")])
				_pump()
				return
			job.on_done.call(parsed as Dictionary)
			_pump())

	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Authorization: Bearer %s" % token])
	var error := request.request(base_url + job.path, headers, job.method, job.body)
	if error != OK:
		request.queue_free()
		_busy = false
		failed.emit("Could not reach %s (error %d)." % [base_url, error])
