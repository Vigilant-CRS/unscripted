# The Square

A plaza, seven people, and two things you can do to somebody: be decent, or be
vile. Everything on screen is a readout of what the runtime holds — how warm
each of them is toward you, what they make of your conduct, and what they would
rather do when you speak to them.

**There is no reputation table in this project.** Every number is fetched from
the runtime over `GET /v2/state/character`, the endpoint a shipping build is
allowed to call.

## The beat worth waiting for

1. Be vile to Yara in the square. Otto is on the bench and sees it. Both faces
   cool, and Otto's cools even though nothing happened to him.
2. Walk to the bar. Nadia was not there, has never met you, and is unmoved.
3. Press `W`. Six hours pass. Nobody is scripted to tell anybody anything.
4. Ask Nadia again. She has cooled to about −0.20 and puts you off — because
   somebody who was there walked into the bar and mentioned it.

Asked before, she says *"Evening."* Asked after, *"I've got nothing for you."*
Same person, same question, and she still has not laid eyes on you.

Kindness travels the same way and just as far, which is why being decent in
front of the right person is worth something.

## Running it

    cd ../..
    python3 -m unscripted bundle --out demos/the-square/unscripted.pyz
    /path/to/godot --path demos/the-square --headless --import   # once
    /path/to/godot --path demos/the-square

Keys: arrows walk, `K` be kind, `X` be vile, `SPACE` ask, `W` let six hours
pass, `R` start the day again.

`--tour` plays the seven beats above unattended and prints one line each, so the
comparison does not depend on who was at the keyboard.

## What is switched on

`pursuit` and `standing`, passed from the scene rather than declared in
`worldpacks/market-square`, because that pack ships and other demos and tests
use it: a pack that switched mechanics on for everybody would be deciding for
them.

Without `standing` the scene still runs and every face stays neutral for ever,
which is the honest picture of what the runtime does without it.
