# Projectile DPP Gap Report

Generated from `questions/manifest/projectile_dpp_manifest.json`.

## Summary

- Total top-level questions: 27
- MCQ: 22
- Diagram MCQ: 5
- Current executable evaluator:
  - Passed: 27
  - Failed: 0
  - Unsupported: 0
- Needs symbolic solver: 0 blocking evaluator coverage
- Needs diagram geometry: 0 blocking evaluator coverage

## Passing Cases

- `projectilenorm Q01` — `parametric_initial_speed`
- `projectilenorm Q02` — `velocity_change_interval`
- `projectilenorm Q03` — `parametric_curve_classification`
- `projectilenorm Q04` — `velocity_angle_event_speed`
- `projectilenorm Q05` — `horizontal_throw_velocity_angle_time`
- `projectilenorm Q06` — `velocity_perpendicular_to_initial_event`
- `projectilenorm Q07` — `same_range_doubled_angle_time_ratio`
- `projectilenorm Q08` — `target_angle_from_short_overshoot`
- `projectilenorm Q09` — `fielder_catch_before_ground`
- `projectilenorm Q10` — `average_velocity_to_peak`
- `projectilenorm Q11` — `projectile_with_horizontal_acceleration`
- `projectilenorm Q12` — `air_drag_conceptual_timing`
- `projectilenorm Q13` — `max_range_from_height_fixed_speed`
- `projectileinc Q01` — `inclined_plane_impact_time`
- `projectileinc Q02` — `inclined_plane_same_point_time_ratio`
- `projectileinc Q03` — `inclined_plane_right_angle_impact_condition`
- `projectileinc Q04` — `target_reachability_fixed_speed`
- `projectileinc Q05` — `staircase_collision`
- `projectileinc Q06` — `minimum_speed_to_hit_target`
- `projectileinc Q07` — `inclined_plane_max_normal_distance_velocity_component`
- `projectileinc Q08` — `perpendicular_launch_range_on_incline`
- `projectileinc Q09` — `max_range_on_incline`
- `projectileinc Q10` — `horizontal_launch_onto_incline_distance`
- `projectileinc Q11` — `two_inclines_perpendicular_launch_impact`
- `projectileinc Q12` — `projectile_collides_with_sliding_particle_on_incline`
- `projectileinc Q13` — `motion_on_smooth_incline_perpendicular_to_slope`
- `projectileinc Q14` — `three_dimensional_projectile_line_intersection`

## Extraction Corrections

- `projectilenorm Q04` option `d` is `10/root(3) m/s` in the source PDF, but text extraction returns `10 sqrt3 m/s`. The extractor applies a targeted correction for this option.

## Image Replay Coverage

Saved image debug reports under `questions/debug_reports/` replay cleanly through the patched solver. The replay covers air drag, staircase collision, perpendicular range on incline, two-incline impact speed, inclined-plane right-angle condition, smooth-incline speed after time, and projectile/sliding-particle collision.

## Remaining Work

The current evaluator covers every question in the manifest, but that is not the same as production readiness. Next work is image robustness: keep collecting uploaded-image debug reports, replay them through the solver, and fix extraction/parser mismatches until the image path is stable across multiple crops and handwriting/scan qualities.

## Non-Negotiable Acceptance Rule

No question becomes `passed` because an LLM explanation sounds plausible. A question only passes when the deterministic evaluator computes the expected option/value from the manifest.
