"""Point-particle meetings during overlapping free flights; no collision response."""
from itertools import combinations
import math

from .engine import state
from .models import Encounter, Scene, Simulation


def find_encounters(scene: Scene, tracks: list[Simulation]) -> list[Encounter]:
    by_id = {track.particle_id: track for track in tracks}
    events = []
    for a, b in combinations(sorted(scene.particles, key=lambda p: p.id), 2):
        ta, tb = by_id[a.id], by_id[b.id]
        if ta.status == 'waiting' or tb.status == 'waiting':
            continue
        start = max(a.launch_time, b.launch_time)
        end = min(ta.samples[-1].t, tb.samples[-1].t)
        if start > end:
            continue
        sa = state(a, scene.gravity, start-a.launch_time)
        sb = state(b, scene.gravity, start-b.launch_time)
        delta = [sa.position.x-sb.position.x, sa.position.y-sb.position.y]
        speed = [sa.velocity.x-sb.velocity.x, sa.velocity.y-sb.velocity.y]
        # Equal acceleration cancels. Solve on the better-conditioned axis,
        # then verify both coordinates using freshly evaluated physical states.
        axis = max(range(2), key=lambda i: abs(speed[i]))
        coincident = speed[axis] == 0
        elapsed = 0.0 if coincident else -delta[axis]/speed[axis]
        time = start + elapsed
        tolerance = 64*math.ulp(max(abs(time), end, 1.0))
        if time < start-tolerance or time > end+tolerance:
            continue
        time = min(end, max(start, time))
        pa = state(a, scene.gravity, time-a.launch_time).position
        pb = state(b, scene.gravity, time-b.launch_time).position
        scale = max(abs(pa.x), abs(pa.y), abs(pb.x), abs(pb.y), 1.0)
        # Numerical equality, not a visual sphere-radius collision threshold.
        if math.hypot(pa.x-pb.x, pa.y-pb.y) > max(1e-9, 64*math.ulp(scale)):
            continue
        events.append(Encounter(particle_ids=(a.id, b.id),
            kind='coincident' if coincident and end > start else 'meeting',
            time=time, end_time=end if coincident else time, position=pa))
    return sorted(events, key=lambda event: (event.time, event.particle_ids))
