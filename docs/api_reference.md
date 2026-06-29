# Manim 3D Scene Reference
To create a 3D scene, inherit from `ThreeDScene`.
Key methods:
- `set_camera_orientation(phi=75*DEGREES, theta=-45*DEGREES)`
- `begin_ambient_camera_rotation(rate=0.1)`
- `move_camera(phi=..., theta=..., run_time=...)`

Example:
```python
class ThreeDExample(ThreeDScene):
    def construct(self):
        axes = ThreeDAxes()
        sphere = Sphere(radius=2)
        self.add(axes, sphere)
        self.set_camera_orientation(phi=75*DEGREES, theta=-45*DEGREES)
        self.begin_ambient_camera_rotation(rate=0.1)
        self.wait(2)
```

# Three.js Primitives Reference
- `BoxGeometry(width, height, depth)`
- `SphereGeometry(radius, widthSegments, heightSegments)`
- `PlaneGeometry(width, height)`
- `MeshStandardMaterial({color: 0x00ff00})`

Coordinate System:
- Y is UP.
- X is Right.
- Z is Forward (towards camera).
