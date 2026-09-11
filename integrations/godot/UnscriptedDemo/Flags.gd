class_name Flags
extends RefCounted

## The way NPC knowledge is normally represented, in fifteen lines.
##
## This is not a straw man and not a competitor: it is a set of booleans, which
## is what most shipped games use, and it is fast, saveable and understood by
## everyone on the team. The Python side of this repository has the same model in
## `unscripted/flat.py` with the reasoning written out at length.
##
## What it cannot hold is the entire finding: there is nowhere to put who said
## it, how sure you are, which version you heard, or whether the person who told
## you turned out to be lying.

var known := {}   ## agent id -> Dictionary of fact -> true

func learn(agent_id: String, fact: String) -> bool:
	if not known.has(agent_id):
		known[agent_id] = {}
	if known[agent_id].has(fact):
		return false          # a boolean cannot be set twice
	known[agent_id][fact] = true
	return true

func broadcast(fact: String, agent_ids: Array) -> void:
	# A global fact has no field for who was listening.
	for agent_id in agent_ids:
		learn(agent_id, fact)

func knows(agent_id: String, fact: String) -> bool:
	return known.has(agent_id) and known[agent_id].has(fact)

func who_told(_agent_id: String, _fact: String) -> String:
	return ""     ## nowhere to put it

func how_sure(agent_id: String, fact: String) -> String:
	return "knows it" if knows(agent_id, fact) else "does not"

func which_version(_agent_id: String, _fact: String) -> String:
	return ""     ## there is one fact; a version that changed on the way is the
	              ## same boolean, or a second fact nobody authored


func was_a_lie(_agent_id: String, _fact: String) -> String:
	return ""     ## an honest report and a lie set the identical flag

func discredit(_speaker: String) -> int:
	return 0      ## no edge from a flag back to who caused it
