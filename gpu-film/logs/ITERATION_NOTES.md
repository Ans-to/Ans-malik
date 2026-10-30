# Iteration log — what changed and why

## Scene pass history (pre-render design iterations, counted toward the 3 minimum)

### s1 title
1. World-space type through the 3D camera → text scaled with the lens, blew out of frame. **Fix:** dedicated flat graphics layer (`tcam`, fov = 2·atan(0.5)) so 1.0 unit = half frame height.
2. Type positions hand-placed in world units → no relationship to the frame at other resolutions. **Fix:** `at(x, y)` / `sz(frac)` layout helpers in frame fractions; identical layout at 9:16 and 16:9.
3. Headline sat inside the lit product. **Fix:** moved to the upper-left quadrant with the product in the lower-right third; rule draws on the second beat.

### s2 silicon
1. Die grid + HBM stacks read as a grey slab. **Fix:** brightened metals, added gold contacts and per-block albedo variation, key up to 4.4.
2. Camera at 38° fov too close, geometry cropped by frame. **Fix:** orbit via measured `orbit` curve, radius driven by `dolly_in`.

### s3 yield
1. Dies appeared instantly. **Fix:** `appear` ramp over 2.6 s, defective dies in amber to read as loss.
2. Yield stat static. **Fix:** counter from 100.0% → 82.0% with colour flip past 90%.

### s4 hbm
1. Stack layers were a single block. **Fix:** 8 layers per stack, alternating materials, staggered lift driven by index.
2. Body copy collided with the product. **Fix:** type stack moved up, product pushed to the lower-right.

### s5 euv
1. Machine too small and low. **Fix:** 3.4-unit chassis, taller electrodes, plasma column 0.55 u, camera radius 4.4→3.4.
2. Glass chamber blew out with a white halo. **Fix:** glass re-tuned as a low-fresnel dielectric (`rim` 2.2 → 0.35).

### s6 supply
1. Bars sat flat. **Fix:** 8 towers with a `grow` ramp, cyan emissive for the leading bar; supply line lags demand.
2. Labels overlapped the bars. **Fix:** labels anchored in the graphics layer, not in 3D.

### s7 bom
1. Cost bar filled the frame as a wall. **Fix:** scale 1.45, camera pulled to z 4.2→3.7, tilted framing.
2. Segment labels unreadable. **Fix:** label row moved to a fixed baseline at -0.62 with per-segment x derived from the same geometry scale.

### s8 answer
1. Hero die lit from behind → silhouette. **Fix:** key rotated to front-left, exposure up, camera pulled to radius 3.4.
2. Die too small in frame. **Fix:** die scale 1.35 → 1.9.

## Transitions
- First pass: light sweep and defocus were strong enough to white out the frame. **Fix:** sweep gain 1.4 → 0.42, defocus radius 9 → 4, whip smear 42 → 16, wipe glow 0.9 → 0.55.
