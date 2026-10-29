"""Resolve declarative measurements from scene geometry and engine contacts."""
import math

from .models import (AngleMeasurement, DistanceMeasurement, FixedAnchor, Ground,
                     ObjectAnchor, Particle, ResolvedMeasurement, Staircase, Vector)


def default_measurements(scene, particle_id):
    result = []
    for index, surface in enumerate(scene.surfaces):
        if not isinstance(surface, Staircase):
            continue
        def anchor(feature):
            return ObjectAnchor(kind='object', target=surface.id, feature=feature)
        result.extend([
            DistanceMeasurement(kind='distance', id=f'default_{index}_rise', label='Step height',
                start=anchor('step_upper'), end=anchor('step_start'), axis='vertical',
                side=1 if surface.direction == 'right' else -1),
            DistanceMeasurement(kind='distance', id=f'default_{index}_run', label='Step width',
                start=anchor('step_start'), end=anchor('step_end'), axis='horizontal', side=1),
        ])
    if result:
        result.append(DistanceMeasurement(kind='distance', id='flight_drop', label='Drop',
            start=ObjectAnchor(kind='object', target=particle_id, feature='launch'),
            end=ObjectAnchor(kind='object', target=particle_id, feature='contact'), axis='vertical', side=-1))
    return result


def resolve_anchor(anchor, scene, simulation, simulations=None):
    if isinstance(anchor, FixedAnchor):
        return Vector(x=anchor.point.x, y=anchor.point.y)
    obj = next(item for item in [*scene.surfaces, *scene.particles] if item.id == anchor.target)
    feature = anchor.feature
    if isinstance(obj, Particle):
        if feature == 'launch':
            return Vector(x=obj.position.x, y=obj.position.y)
        source = simulations.get(obj.id) if simulations is not None else simulation
        if source is None or source.particle_id != obj.id or source.contact is None:
            raise ValueError('No contact available for this particle in this simulation')
        return source.contact.position
    if isinstance(obj, Ground):
        return Vector(x=obj.x_max if feature.endswith('end') else obj.x_min, y=obj.y)
    x, y = obj.origin.x, obj.origin.y
    if feature == 'origin':
        return Vector(x=x, y=y)
    if isinstance(obj, Staircase):
        sign, n = (1 if obj.direction == 'right' else -1), anchor.step
        return Vector(x=x + sign * (n if feature == 'step_end' else n-1) * obj.run,
                      y=y - (n-1 if feature == 'step_upper' else n) * obj.rise)
    end = feature.endswith('end')
    return Vector(x=x + (obj.width if end else 0),
                  y=y + (obj.height if feature.startswith('top_') and end == obj.rising else 0))


def resolve_measurements(scene, simulation, simulations=None):
    specs = scene.measurements if scene.measurements is not None else default_measurements(scene, simulation.particle_id)
    result = []
    for spec in specs:
        base = dict(id=spec.id, label=spec.label, kind=spec.kind,
                    unit='deg' if isinstance(spec, AngleMeasurement) else 'm',
                    axis=getattr(spec, 'axis', 'direct'), side=getattr(spec, 'side', 1))
        try:
            a, b = resolve_anchor(spec.start, scene, simulation, simulations), resolve_anchor(spec.end, scene, simulation, simulations)
            if isinstance(spec, AngleMeasurement):
                v = resolve_anchor(spec.vertex, scene, simulation, simulations)
                ax, ay, bx, by = a.x-v.x, a.y-v.y, b.x-v.x, b.y-v.y
                if min(math.hypot(ax, ay), math.hypot(bx, by)) < 1e-9:
                    raise ValueError('An angle requires two nonzero rays')
                value = math.degrees(math.atan2(abs(ax*by-ay*bx), ax*bx+ay*by))
                points = [a, v, b]
            else:
                dx, dy = b.x-a.x, b.y-a.y
                value = abs(dx) if spec.axis == 'horizontal' else abs(dy) if spec.axis == 'vertical' else math.hypot(dx, dy)
                points = [a, b]
            result.append(ResolvedMeasurement(**base, status='ready', points=points, value=value))
        except ValueError as exc:
            result.append(ResolvedMeasurement(**base, status='unavailable', reason=str(exc)))
    return result
