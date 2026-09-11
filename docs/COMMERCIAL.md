# The licence and the price, assessed

**This is an engineering and commercial assessment, not legal or tax advice.**
Nothing here has been reviewed by a Fachanwalt für IT-Recht or a Steuerberater,
and two of the findings below (§ 4, § 5) are the kind that need one before money
changes hands. Read it as "what a buyer's legal department will say, and what
comparable products actually charge", not as a settled position.

Assessed against `LICENSE` v1.2 and the price table in `README.md`, September
2026, at runtime 1.21.0: 201 tests, five external reviews closed, **no shipped
title, one maintainer**.

---

## 1. The licence model is right, and that is not the usual answer

Source-available, per-Product, lifetime, no royalty, no seat counting, with a
free tier gated on *both* a per-title lifetime revenue threshold and a company
size. Four things about that are correct on purpose:

* **Source-available is not optional for this product.** Console certification
  requires handing source to a platform holder under NDA; a studio integrating a
  simulation layer will step into it in a debugger on day two; and the entire
  pitch here is *auditable* determinism — a claim nobody can check in a binary.
  A closed-binary licence would contradict the marketing.
* **Per-title flat beats a royalty.** Studios can approve a number. They cannot
  approve a percentage without finance, legal and a reporting obligation, and a
  royalty on an unproven component is where a middleware deal dies.
* **Lifetime, no renewal** removes the single worst friction in middleware
  procurement: the licence expiring mid-production.
* **The Derivative-Work reach** closes the obvious "rewrite it in C# and walk
  away" hole. A translation or port is an Umarbeitung under § 69c Nr. 2 UrhG and
  the reach over one is solid.

### Where the model is weaker than it reads

**The published specification is a hole in the Derivative-Work reach.**
`docs/SPECIFICATION.md` is 123 pages that exist so somebody can rebuild the
system without reading the code — which is exactly what a clean-room
reimplementation is. Ideas, principles and interfaces are not protected
(§ 69a Abs. 2 UrhG). A team that reads only the spec and writes their own code
owes nothing, and the licence cannot change that.

That is a real tension and it is worth being deliberate about rather than
surprised by. The spec is the strongest credibility asset the project has; it is
also the moat, published. The honest resolution: **the moat is not the algorithm,
it is the conformance suite, the bit-exact port, five reviews' worth of closed
defects, and the person who knows why each bound is shaped the way it is.** A
clean-room team gets the model and inherits none of that — and, on the evidence
of this repository, would ship the *first* version of the source ceiling and not
the fourth. Price and pitch accordingly; do not pretend the licence forbids it.

**A bespoke licence costs the customer legal time.** Every non-standard licence
adds a week to a studio's review. Two cheap mitigations: keep the terms, but
describe them as a *Fair Source* licence so a reviewer recognises the shape; and
have the commercial agreement drafted and ready to send, so the answer to "can we
see the paper?" is an attachment rather than a delay.

### Three defects in the file itself

1. ~~**Section 3 is lettered a, b, c, f, d, e.**~~ **Fixed** in this pass: the
   items keep the reading order the author chose and the letters now run a to f.
   Worth recording because it is the kind of defect a buyer's lawyer finds in the
   first ten minutes and reads as a signal about everything else in the file.
2. **The AS-IS disclaimer will not hold for the paid tier.** For the *free*
   licence it is roughly fine — a gratuitous grant is judged near §§ 521, 524 BGB
   and liability narrows to intent and gross negligence. For a **paid perpetual
   licence** a blanket exclusion of all warranty and all liability in standard
   terms is unwirksam under § 307 BGB, even B2B, and the "nothing excludes what
   cannot be excluded" saver does not cure it: what survives is liability for
   *typische, vorhersehbare Schäden bei Verletzung wesentlicher Vertragspflichten*
   (Kardinalpflichten), which the clause does not address at all. The commercial
   agreement needs a real, stated cap instead of a disclaimer that a court would
   strike — the usual shape is 100% of the licence fee, or 1× annual fee for a
   subscription, with the statutory carve-outs named.
3. **A perpetual licence for a one-off fee is bought, not rented.** German courts
   treat it as Rechtskauf under § 453 BGB, which brings a two-year Gewährleistung
   the file never mentions. That belongs in the commercial agreement, shortened as
   far as B2B terms allow, not left to default.

### Four things missing that a buyer will ask for

* **Platform-holder disclosure.** Explicit permission to give source to Sony,
  Microsoft or Nintendo under their NDA for certification. This is asked for in
  every console deal and its absence stalls one.
* **Escrow.** Named, with terms and a price. A one-person e.K. selling a runtime
  that ships inside a game *will* be asked about the bus factor, and "we have an
  escrow agreement with X for €N a year" is a two-sentence answer to a question
  that otherwise ends the conversation.
* **A real CLA.** § 3(f) relicenses contributions by assertion. For anything past
  a typo that is not enough to keep the commercial relicensing right clean; a
  DCO plus a signed CLA for substantial contributions is the minimum.
* **Export, sanctions and third-party notices.** Boilerplate, but its absence is
  a red flag to a procurement reviewer rather than a neutral silence.

---

## 2. The prices, against what comparable middleware charges

Published per-title list prices for game middleware, for orientation:

| Product | What a title pays |
| --- | --- |
| FMOD | free under ~$600k budget; ~$2,000 indie; ~$7,500 basic; ~$15,000+ premium |
| Wwise | tiered per title, roughly $1,500 to $25,000+ |
| Bink 2 | ~$8,500 per platform per title |
| Coherent Gameface | ~$25,000+ per title |
| Umbra / Simplygon / Enlighten class | €25,000–€100,000+, enterprise |
| Havok (historically) | $50,000–$150,000+ |
| Inworld / Convai | usage-priced: cost scales with players, forever |

The current ladder — free / €3,500 / €12,000 / from €45,000 — sits inside that
band and its shape is right. Four specific notes:

**€3,500 is well-judged.** It is under the line where a small studio needs a
purchase order and three signatures. Keep it exactly there.

**€12,000 for a €1M–10M company is low, and should stay low for now.** That band
holds 20-to-80-person studios making €3–8M games; €12,000 is 0.15–0.4% of
budget, against $15,000 for FMOD Premium — and audio is a commodity every game
needs, while this is a differentiator no game needs. On a like-for-like basis
€18,000–€25,000 is defensible. **It is not defensible yet**, because the price is
currently carrying the risk of being first. Raise it when a title has shipped,
not before.

**€30,000 a year studio-wide is underpriced against €12,000 per title.** It
breaks even at 2.5 titles a year, so a studio shipping three is buying a 20%
discount on an unlimited commitment — including sequels, which the per-title
scheme correctly charges again for. Either €45,000–€60,000, or cap it at three
titles a year.

**"From €45,000" reads as too small for the buyer it is aimed at.** For a studio
with a €30M budget, a €45,000 line item is *harder* to justify than €150,000,
because €45,000 reads as a hobby vendor and invites the "why don't we just build
it" conversation. Publish "from €45,000" — a published number beats "on request"
and the README is right about why — but expect the negotiated shape to be
€75,000–€150,000 per title, split into a licence fee and a paid integration.

### Three revenue lines that are missing

* **Maintenance and support, 18–22% of licence per year**, first year included.
  This is the industry norm and it is where middleware vendors actually make
  sustainable money. Everything currently sold is perpetual with no renewal, so
  revenue is one-shot and lumpy by construction.
* **Integration and co-development at a day rate.** €1,000–€1,600/day is the
  German band for specialised engine and simulation work; €1,200 is a fair
  anchor. **For a solo vendor this is very likely to be the majority of early
  revenue.** A studio that has just approved €12,000 for a licence will approve
  ten days of the author's time without a second meeting.
* **Porting to an in-house engine, fixed price**, €25,000–€80,000. Several of the
  studios most likely to want this run their own engine.

### The pricing argument that was not in the README

*Added to it in the same pass as this assessment; kept here because it is the
reasoning behind where the top tier is priced.*

Against Inworld and Convai, this runtime has **no per-interaction cost, no cloud
dependency, no latency budget and no rate limit** — it is deterministic and runs
on the player's machine. At a million players a usage-priced competitor plausibly
costs six figures *a year, forever*; €150,000 once is cheap by comparison, and
the comparison is the strongest pricing argument available.

The six-figure number is an order-of-magnitude estimate from published
per-interaction rates, not a measurement, and the README says so in a footnote.
It does not need to be precise: the *shape* of the cost is the argument — one
side scales with success and never ends, the other does not — and that holds at
any plausible rate. Do not let it harden into a quoted figure in a deck. It also has an EU AI Act
answer: this is not an AI system in the GPAI sense, so the obligations follow
whatever model a studio bolts on through `semantic_release="provider"` and not
this. Both arguments justify the top of the range, and both are now made — under
*"The number that matters is the one that does not repeat"* in `README.md`, next
to the price table rather than three documents away from it.

---

## 3. What this will realistically earn, which is the part that matters

The uncomfortable assessment, stated plainly because the alternative is planning
against a number nobody will hit:

**There is no budget line for this yet.** Studios have an audio budget, a physics
budget, a UI budget. Nobody has an "NPC epistemics" budget. Every early sale is
therefore a category-creation sale: six to eighteen months, champion-led inside
the studio, and frequently lost to "we'll build it ourselves next project" rather
than to a competitor.

**The free threshold is generous and correct, and it means the indie long tail
pays nothing.** That is the right trade for adoption in a category that does not
exist. Do not model revenue from it.

**Realistic first twelve months from a public repository with no sales function:
zero to three paid licences, €0–€40,000**, plus €20,000–€60,000 of integration
work if one lands. The median outcome is closer to €0–€15,000 than to €50,000,
and the single largest determinant is not the price list but whether one
lighthouse studio can be found and served.

The credible paths to real money, in order of likelihood:

1. **Consulting and co-development on one lighthouse project.** Fastest, and it
   produces the reference title everything else is blocked on.
2. **Outside games entirely.** Training simulation, serious games, agent-based
   modelling of how information moves through a population, social-science and
   defence-adjacent work. This runtime's actual subject — provenance, belief
   under correlated evidence, rumour saturation — is arguably worth more there
   than in entertainment, and those buyers have budgets, procurement processes
   and a taste for auditable determinism.
3. **A tech acquisition or acqui-hire** by an engine vendor or an AI-NPC company.
4. **Volume middleware licensing.** Real, and the slowest of the four.

**The reference-title discount is the best idea in the current pricing** and
should be pushed harder than 60%. The first shipped title is worth more than any
licence fee on this page; consider free-plus-integration for one, in exchange for
a named credit, a public case study and the right to quote measured results.

---

## 4. German specifics worth knowing before invoicing

Not tax advice; check with a Steuerberater. All of it is routine, and all of it
is cheaper to set up before the first invoice than after.

* **VAT.** 19% for German customers. EU B2B with a valid VAT ID goes out under
  reverse charge (§ 13b UStG) with the customer's ID on the invoice. Non-EU B2B
  is outside the scope of German VAT.
* **Withholding tax on royalties is the one that bites.** A US or Japanese studio
  will deduct withholding tax from a licence payment unless treaty relief is
  claimed *in advance*. Under the German–US and German–Japan double-taxation
  treaties the rate on royalties is 0%, but only against the right paperwork
  (W-8BEN-E for the US, the Japanese application forms plus a German residence
  certificate). Nobody refunds it afterwards without a fight. Have the forms
  ready before the first non-EU deal, not during it.
* **Structure large deals as an Individualvereinbarung, not AGB.** A liability
  cap negotiated individually survives § 307 BGB scrutiny that the same cap in
  standard terms would not.
* **e.K. means personal liability.** For a product that ships inside other
  people's games, the question of whether a GmbH or UG is worth its cost is worth
  asking a Steuerberater once, early — before the first six-figure contract, not
  after.

---

## 5. What to change, in order

1. ~~Fix the section lettering in `LICENSE`.~~ Done.
2. Draft the commercial agreement: liability cap, support term, escrow,
   platform-holder disclosure, Gewährleistung. This is the one item that needs a
   lawyer and it blocks the first real deal.
3. Add support and maintenance (20%/year, first year included), a day rate, and a
   porting price to the published table.
4. ~~Put the two arguments from § 2 into the README.~~ Done: no per-player cost,
   no processor agreement, and no EU AI Act obligation attaching to this
   component.
5. Get the non-EU withholding forms in place.
6. Leave the per-title numbers where they are until a title has shipped. Then
   raise the middle tier and the site licence.

