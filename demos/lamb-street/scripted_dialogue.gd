extends RefCounted
class_name ScriptedDialogue

## The conventional side of the comparison, written to be GOOD.
##
## THIS IS NOT A STRAW MAN, and the whole demo is worthless if it is. What is
## below is how a competent developer writes NPC dialogue for a murder scene in
## 2026: a table of characters, a table of topics, per-character lines with some
## variation, a flag for whether the player has heard a thing yet, and a fallback
## for questions a character has nothing for. It is the shape Dialogic, Yarn
## Spinner and Ink all produce, because it is the shape the problem has when
## dialogue is authored.
##
## It is also, deliberately, better than most shipped games manage: the lines are
## specific to the character, the liar has a cover story, and there is a barks
## table so nobody repeats one sentence forever.
##
## WHAT IT CANNOT DO -- and no amount of authoring effort fixes any of these,
## which is the actual argument:
##
##   * Every player gets the same answers in the same order. There is no state
##     in here that the world could change.
##   * The characters do not know each other exist. Halloran cannot learn what
##     Vance saw, because there is nowhere for that to be written down.
##   * Time does nothing. Ask at nine in the evening or nine the next morning:
##     the table does not have a clock in it.
##   * The liar lies because the author typed a lie. Nothing knows it is a lie,
##     so nothing can catch her out later.
##   * Adding a seventh character means writing the whole table again for them.
##
## THE BULLETIN LINES ARE THE HONEST TEST. A good author does write a line for
## "the bulletin" -- it is in here, for all six. But it has to be written before
## anybody knows WHEN the player will ask, and there is exactly one line per
## character. Ask Byrne at nine in the evening and he tells you what the radio
## has been saying all morning, twelve hours before it says it. The line is not
## badly written. It is written at the wrong time, and a table has no other
## kind of time to be written at.

## Lines per character, per topic. The second and third entries are variations,
## used on re-asks so that nobody sounds like a vending machine.
const LINES := {
	"halloran": {
		"the shot": [
			"One crack, out the back, just after nine. I was pouring.",
			"Same as I told you. One bang, round the back, gone nine.",
			"I've said what I heard. I'm not going to hear it twice.",
		],
		"what happened": [
			"A man got shot behind the Marchmont. That's all I know.",
			"Somebody died out the back. I don't know more than that.",
		],
		"the runner": ["Couldn't tell you. I was inside."],
		"the car": ["I don't watch the street. I watch the taps."],
		"the bulletin": ["Radio's been on about it. A man they haven't found."],
	},
	"vance": {
		"the runner": [
			"Somebody came out the back at a run and went left. No face.",
			"Coat and a hat, going left, fast. That's the lot.",
			"I've told you what I saw. It doesn't get better with asking.",
		],
		"what happened": [
			"Somebody got shot, and somebody ran. I only saw the running part.",
		],
		"the shot": ["Didn't hear it. Engine was going."],
		"the car": ["Cars are my business. I wasn't looking at that one."],
		"the bulletin": ["I don't have the radio on in the cab."],
	},
	"okonkwo": {
		"the car": [
			"There was a car sat outside with the engine going. Quarter of an hour.",
			"The same car. Engine running. I only thought about it after.",
			"I've given you the car. There isn't any more of it.",
		],
		"what happened": [
			"They say a man was shot. I was cashing up. I heard nothing.",
		],
		"the shot": ["I heard nothing. The radio was on."],
		"the runner": ["I didn't see anybody run."],
		"the bulletin": ["Radio said they're looking for a man. That's all."],
	},
	"reyes": {
		# THE LIE, typed by hand -- which is exactly the point. Nothing in this
		# file knows this is false, so nothing can ever catch her out.
		"what happened": [
			"Nobody came past this door. Ask the street, not me.",
			"I've told you. Not past me.",
			"You're wasting your evening.",
		],
		"the shot": ["Music's loud in there. I hear nothing after eight."],
		"the runner": ["Nobody ran past me."],
		"the car": ["I watch the door, not the kerb."],
		"the bulletin": ["I don't listen to the news. I work nights."],
	},
	"byrne": {
		"what happened": [
			"Papers'll have it in the morning. I've got nothing tonight.",
			"Still nothing. Come back when I've got a paper to sell you.",
		],
		"the shot": ["Not a thing."],
		"the runner": ["Not a thing."],
		"the car": ["Not a thing."],
		"the bulletin": ["Radio's been on about it all morning. A man they want."],
	},
	"doyle": {
		"what happened": [
			"There is an open investigation. I have nothing further to add.",
			"Still open. Still nothing to add.",
		],
		"the shot": ["I have nothing further to add."],
		"the runner": ["I have nothing further to add."],
		"the car": ["I have nothing further to add."],
		"the bulletin": ["The statement speaks for itself."],
	},
}

## What somebody says when asked about a topic nobody wrote a line for.
const FALLBACK := "I wouldn't know anything about that."

var _asked: Dictionary = {}


func answer(character: String, topic: String) -> Dictionary:
	var key := character + "/" + topic
	var count: int = _asked.get(key, 0)
	_asked[key] = count + 1

	var by_topic: Dictionary = LINES.get(character, {})
	var lines: Array = by_topic.get(topic, [])
	if lines.is_empty():
		return {"text": FALLBACK, "honesty": "—", "source": "—", "confidence": "—"}
	# Walk the variations, then hold on the last one. A tree cannot invent a
	# sixth thing to say, so the honest behaviour is to stop repeating new ones.
	var index: int = min(count, lines.size() - 1)
	return {
		"text": lines[index],
		# The panel on the runtime side shows honesty, provenance and
		# confidence. This side has none of those to show, and showing blanks is
		# more honest than inventing plausible values.
		"honesty": "—", "source": "—", "confidence": "—", "hops": "—",
	}


func reset() -> void:
	_asked.clear()
