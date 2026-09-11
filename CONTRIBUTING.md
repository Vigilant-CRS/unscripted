# Contributing

## Before you open a pull request — the licence term that applies to you

Section 3(e) of [`LICENSE`](LICENSE) says that contributions submitted for
inclusion are licensed to Vigilant e.K. under the licence's terms, **with the
right to relicense them commercially.**

That matters here more than in most projects, because this is source-available
rather than open source: Vigilant sells commercial licences, and a contribution
that could not be included in one would have to be refused or removed later,
which is worse for everybody than saying so now.

So, plainly: **opening a pull request means you agree to that.** If you cannot
agree — because your employer owns your work, or for any other reason — open an
issue describing the change instead. A well-described bug is worth more than a
patch nobody can merge.

## What is welcome

**Bugs, with a reproduction.** The best form is a failing test in
`tests/test_scenarios.py`. Every test in that file is written to explain what
would be wrong if it failed, and a new one should read the same way.

**World packs.** Content you author is yours (§3d) — but a pack that exercises
something the reference packs do not is genuinely useful, and a pack contributed
here is contributed under the same terms as code.

**Measurements that contradict ours.** If a number in the documentation is wrong
on your machine, that is the most valuable thing you can send. Every claim in
this repository is supposed to be reproducible by a command; if one is not, it
should be corrected or removed.

## What will be refused, and why

**A layer that is on by default.** Every optional mechanic is off, and off is
byte-identical — a test asserts it. A studio that does not want a mechanic must
not pay for it.

**A dependency.** The SDK installs with no third-party packages. That is what
lets it ship as a single file, and it is worth more than any convenience a
library would buy.

**A claim without a measurement.** Docstrings here state what a thing does and
what it does not; the honest limits are as load-bearing as the features. A
change that adds a capability should say how it was verified, and a change that
removes a limitation should update the place where that limitation is written
down.

**Silence on failure.** Several bugs found in this codebase were not wrong
behaviour but invisible behaviour: an exception swallowed, a reason discarded, a
value silently ignored. A patch that adds a `try: ... except: pass` will be sent
back.

## Running the tests

```bash
python3 tests/test_scenarios.py     # the whole suite, no pytest needed
python3 -m unscripted golden-all           # multi-step playthroughs with assertions
python3 -m unscripted benchmark --turns 1500
python3 -m unscripted validate worldpacks/market-square
```

Everything must pass before a pull request. The suite is self-contained and
takes a couple of minutes.
