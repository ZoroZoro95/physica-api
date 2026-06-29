# Visual Template Tasks - 2026-06-24

Source verifier report:
`questions/visual_benchmarks/smoke_visual_benchmark/review_queue/visual_verdicts.json`

Benchmark:
30 cases total, 15 text and 15 image-derived. The verifier scored 16 pass, 11 warn, and 3 fail.

## Blocker

### projectile_collides_with_sliding_particle_on_incline

Cases:
- `15_visual_text_q15_projectile_collides_with_sliding_particle_on_incline`
- `21_visual_image_q06_projectile_collides_with_sliding_particle_on_incline`
- `24_visual_image_q09_projectile_collides_with_sliding_particle_on_incline`

Problem:
Setup and diagram-insight beats are identical. Normal-direction, collision-equation, and answer-sanity beats are near duplicates. The final beat does not show the equation or numeric speed.

Required work:
- Split setup, along-plane cancellation, normal-return equation, collision equation, and final speed into distinct templates.
- Show why along-plane motion cancels using paired P/Q `g sin alpha` arrows only on that beat.
- Show the normal-motion equation and `t = 4 s` substitution on the collision-equation beat.
- Show final `u` value on the answer beat instead of repeating the normal diagram.

## High

### inclined_plane_right_angle_impact_condition

Cases:
- `16_visual_image_q01_inclined_plane_right_angle_impact_condition`
- `25_visual_image_q10_inclined_plane_right_angle_impact_condition`

Problem:
Invariant, event-condition, and calculation beats are visually too similar. The final launch/incline angle condition is not written.

Required work:
- Add a final condition template showing the algebraic relation between launch angle and incline angle.
- Make event-condition beat emphasize `v_t = 0` at impact, while calculation beat emphasizes substituted angle relation.

### level_ground_position_at_time

Case:
- `07_visual_text_q07_level_ground_position_at_time`

Problem:
Final calculate beat repeats the position board without showing `x(t)`, `y(t)`, or numeric substitution.

Required work:
- Add a position-equation template with `x = u_x t` and `y = u_y t - 1/2gt^2`.
- Add a final numeric substitution variant for the requested time.

### height_launch_time_of_flight

Case:
- `10_visual_text_q10_height_launch_time_of_flight`

Problem:
Factor/solve beat does not show the actual vertical equation root or solved time.

Required work:
- Replace generic positive-root text with a vertical equation/root template.
- Show the final `T` value when available.

## Medium

### minimum_speed_to_hit_target

Case:
- `11_visual_text_q11_minimum_speed_to_hit_target`

Problem:
Setup and calculation panels are too similar. Limiting condition/formula is absent.

### inclined_plane_max_normal_distance_velocity_component

Cases:
- `18_visual_image_q03_inclined_plane_max_normal_distance_velocity_component`
- `27_visual_image_q12_inclined_plane_max_normal_distance_velocity_component`

Problem:
Final beat omits max-distance formula/value. Path is still too stylized for normal-distance derivation.

### velocity_change_interval

Case:
- `28_visual_image_q13_velocity_change_interval`

Problem:
First two beats are identical despite different intent. Final delta-v beat lacks numeric delta-v.

### two_projectile_interception_time_ratio

Case:
- `30_visual_image_q15_two_projectile_interception_time_ratio`

Problem:
Final ratio/calculation is not shown; board stops at compare vertical times.

## Low

### level_ground_multi_quantity

Cases:
- `02_visual_text_q02_level_ground_multi_quantity`
- `03_visual_text_q03_level_ground_multi_quantity`

Problem:
Final board is generic and some connection beats repeat launch-components.
