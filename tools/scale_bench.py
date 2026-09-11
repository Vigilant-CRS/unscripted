"""Scale bench: how does a tick cost grow with the size of the cast?

Not part of the package -- a measurement tool, kept because the numbers in
docs/CONCEPT.md have to be reproducible by whoever doubts them.

    python3 tools/scale_bench.py
"""

import copy, json, os, resource, sys, time
sys.path.insert(0, os.getcwd())
from unscripted.evidence import _runtime
from unscripted.agent import Agent
from unscripted.routine import Routine

def build(n, template_pack="worldpacks/relay-station"):
    rt = _runtime(template_pack)
    w = rt.world
    seeds = list(w.agents.values())
    places = list(w.places)
    base = seeds[0]
    for i in range(n - len(seeds)):
        src = seeds[i % len(seeds)]
        a = Agent(id=f"agent:extra_{i}", big_five=dict(src.big_five),
                  schwartz=dict(src.schwartz), needs=dict(src.needs),
                  identities=list(src.identities), roles=list(src.roles),
                  education=dict(src.education), relationships={},
                  goals=list(src.goals), location=places[i % len(places)],
                  public_name=f"Extra {i}", aliases=(f"extra{i}",),
                  routine=copy.deepcopy(src.routine),
                  networks=(f"shift:{i%3}",), epistemic=dict(src.epistemic))
        w.agents[a.id] = a
    return rt

def rss_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


import time
from unscripted.routine import Routine

def district(rt, n_places):
    """A cast with somewhere to live, and staggered days -- as a real world is."""
    w = rt.world
    base = list(w.places.items())[0][1]
    for i in range(n_places):
        w.places[f"place:room_{i}"] = dict(base, label=f"Room {i}", exits=[], aliases=[f"room{i}"])
    rooms = [k for k in w.places if k.startswith("place:room_")]
    for j, a in enumerate(w.agents.values()):
        home, work = rooms[j % len(rooms)], rooms[(j * 7 + 3) % len(rooms)]
        shift = (j % 6) * 4
        a.location = home
        a.routine = Routine.from_list([
            {"from": f"{shift:02d}:00", "place": work, "activity": "work"},
            {"from": f"{(shift + 8) % 24:02d}:00", "place": home, "activity": "rest"},
        ])
    return rt

print(f"{'Agenten':>8} {'Orte':>6} {'ms/Sim-Stunde':>15} {'ms/Agent/h':>11} {'max. Belegung':>14}")
for n, places in ((200, 60), (800, 200), (2000, 400), (5000, 800)):
    rt = build(n); rt.core.projection_scope = "focus"; district(rt, places)
    rt.advance_time(60)
    t0 = time.perf_counter()
    for _ in range(8): rt.advance_time(60)
    dt = (time.perf_counter() - t0) / 8 * 1000
    busiest = max(len(rt.world.occupants(p)) for p in rt.world.places)
    print(f"{n:>8} {places:>6} {dt:>15.1f} {dt/n:>11.3f} {busiest:>14}")
    rt.close()
