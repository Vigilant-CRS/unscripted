extends Node
class_name UnscriptedHost

## Starts the runtime as a child process and tells you when it is reachable.
##
## Both shipped clients used to assume somebody had already run `unscripted serve` --
## the demo's error message literally asks whether you did. That is fine for a
## demo and it is the entire integration problem for a shipping game, so it is
## solved here once rather than badly in every project.
##
## What this handles, which is all of it:
##
##   the port      `--port 0` lets the OS choose. A fixed port breaks the moment
##                 a player has something else on it, or runs two copies.
##   finding out   the service writes {url, port, token, pid} atomically when it
##                 is listening; this polls for that file.
##   the token     generated per launch, so nothing else on the machine can talk
##                 to a service started for this game.
##   orphans       `--parent-pid` makes the service exit when this process does,
##                 including when it crashes. Games crash.
##   shutting down SIGTERM first, and only then something harsher.
##
## Usage:
##
##     var host := UnscriptedHost.new()
##     add_child(host)
##     host.ready_at.connect(func(url, token): client.configure(url, token))
##     host.start("res://worldpacks/my-town", ["pursuit", "notes"])

## Emitted once the service answers. Connect BEFORE calling start().
signal ready_at(url: String, token: String)
## Emitted if it never came up, with a reason worth showing a developer.
signal failed(reason: String)

## Where the interpreter is.
@export var python := "python3"
## Path to a bundle from `unscripted bundle`, or empty to use an installed `unscripted`.
##
## THE UNITY HOST HAD THIS AND THIS ONE DID NOT, which only surfaced when the
## demo tried to start a runtime from a game directory and got
##
##     /usr/bin/python3: No module named unscripted
##
## `-m unscripted` needs the package importable from wherever the child process starts,
## which is the game's directory and not the checkout. A bundle has no such
## requirement -- it is one file and it carries itself.
@export var bundle_path := ""
## How long to wait for the service before giving up, in seconds.
@export var startup_timeout := 30.0

var _pid := -1
var _announce_path := ""
var _elapsed := 0.0
var _running := false
var _url := ""
var _token := ""
## Which archive was actually launched, so a timeout can say something useful
## rather than repeating the command that was never run.
var _launched_bundle := ""


func start(world_pack: String, layers: PackedStringArray = []) -> void:
	if _running:
		push_warning("UnscriptedHost.start called twice; ignoring the second")
		return
	# user:// rather than res://: res:// is inside the exported package and is
	# not a real writable directory in a shipped build.
	_announce_path = ProjectSettings.globalize_path(
		"user://unscripted_%d.json" % OS.get_process_id())
	if FileAccess.file_exists(_announce_path):
		DirAccess.remove_absolute(_announce_path)
	_token = _make_token()

	var args := PackedStringArray()
	var bundle := bundle_path if not bundle_path.is_empty() else _find_bundle()
	_launched_bundle = bundle
	if bundle.is_empty():
		args.append_array(["-m", "unscripted"])
	else:
		args.append(ProjectSettings.globalize_path(bundle))
	args.append_array([
		"serve",
		"--world-pack", ProjectSettings.globalize_path(world_pack),
		"--port", "0",
		"--announce", _announce_path,
		"--auth-token", _token,
		"--parent-pid", str(OS.get_process_id()),
	])
	if layers.size() > 0:
		args.append("--layers")
		args.append(", ".join(layers).replace(" ", ""))

	_pid = OS.create_process(python, args)
	if _pid <= 0:
		failed.emit("Could not launch '%s'. Is Python installed and on PATH?" % python)
		return
	_running = true
	_elapsed = 0.0
	set_process(true)


func _find_bundle() -> String:
	## Look for the runtime beside the project before falling back to `-m unscripted`.
	##
	## The five lines the README calls "the whole integration" did not work in
	## anybody's own project: without `bundle_path` the host runs
	## `python3 -m unscripted`, a developer's game has no `unscripted` module installed, and
	## what they got was Python's own "No module named unscripted" with no hint of what
	## to do. Found by following those five lines in an empty project, which is
	## the only way this class of thing is ever found.
	for candidate in ["res://unscripted.pyz", "res://addons/unscripted/unscripted.pyz",
					  "res://../unscripted.pyz"]:
		if FileAccess.file_exists(candidate):
			return candidate
	return ""


func _explain_missing_runtime() -> String:
	return ("The runtime did not start. There is no unscripted.pyz beside the project "
			+ "and `python3 -m unscripted` is not importable here.\n"
			+ "  Build one:  unscripted bundle --out unscripted.pyz\n"
			+ "  Put it at:  res://unscripted.pyz  (or set UnscriptedHost.bundle_path)")


func _process(delta: float) -> void:
	if not _running or _url != "":
		return
	_elapsed += delta
	# Poll the file rather than the port: the service writes it only once it is
	# actually listening, so seeing it means the next request will be answered.
	# Polling a port instead would connect during the bind and fail on the first
	# real call, which is a much more confusing failure.
	if FileAccess.file_exists(_announce_path):
		var handle := FileAccess.open(_announce_path, FileAccess.READ)
		if handle == null:
			return
		var parsed: Variant = JSON.parse_string(handle.get_as_text())
		handle.close()
		if typeof(parsed) != TYPE_DICTIONARY:
			return          # written but not yet complete; try again next frame
		_url = str(parsed.get("url", ""))
		set_process(false)
		ready_at.emit(_url, str(parsed.get("token", "")))
		return
	if _elapsed > startup_timeout:
		_running = false
		set_process(false)
		if _launched_bundle.is_empty():
			# The overwhelmingly likely cause, and the one whose real error
			# ("No module named unscripted") reaches nobody, because it goes to the
			# child process's stderr rather than to the game.
			failed.emit(_explain_missing_runtime())
		else:
			failed.emit(
				"The runtime did not start within %.0f s. Run this by hand to see why:\n"
				% startup_timeout
				+ "  %s %s serve --world-pack <your pack>"
				% [python, ProjectSettings.globalize_path(_launched_bundle)])


func stop() -> void:
	if _pid > 0:
		# The service handles SIGTERM and shuts down cleanly, removing its own
		# announce file. Only if it does not is anything harsher warranted, and
		# --parent-pid is the backstop for the case where we never get here.
		OS.kill(_pid)
		_pid = -1
	_running = false
	_url = ""


func _exit_tree() -> void:
	stop()


func _make_token() -> String:
	# Not a secret worth defending against a determined attacker on the same
	# machine; it stops OTHER local software from talking to a service that was
	# started for this game, which is the actual risk on a player's PC.
	var bytes := PackedByteArray()
	for _i in range(24):
		bytes.append(randi() % 256)
	return Marshalls.raw_to_base64(bytes).replace("/", "_").replace("+", "-")
