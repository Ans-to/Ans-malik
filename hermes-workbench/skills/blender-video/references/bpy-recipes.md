# bpy recipes — copy-paste snippets that work headless (Blender 4.x)

All snippets assume `import bpy, math, os` and a scene created after
`bpy.ops.wm.read_factory_settings(use_empty=True)`.

## Scene reset

```python
bpy.ops.wm.read_factory_settings(use_empty=True)   # empty, deterministic
scene = bpy.context.scene
```

## Camera that always looks at a point

`track_to` constraint, no manual Euler math (the reliable way):

```python
target = bpy.data.objects.new("AimTarget", None)
scene.collection.objects.link(target)
target.location = (0, 0, 0)

bpy.ops.object.camera_add(location=(4.2, -4.2, 2.4))
cam = bpy.context.object
con = cam.constraints.new(type="TRACK_TO")
con.target = target
con.track_axis = "TRACK_NEGATIVE_Z"
con.up_axis = "UP_Y"
cam.data.lens = 50          # 35 = wide, 85 = portrait compression
scene.camera = cam
```

## Turntable rig (camera orbits, object stays put)

```python
pivot = bpy.data.objects.new("Pivot", None)
scene.collection.objects.link(pivot)
cam.parent = pivot

pivot.rotation_euler = (0, 0, 0)
pivot.keyframe_insert("rotation_euler", frame=scene.frame_start)
pivot.rotation_euler = (0, 0, math.radians(120))
pivot.keyframe_insert("rotation_euler", frame=scene.frame_end)
# linear speed reads clean; eased reads "commercial"
for fc in pivot.animation_data.action.fcurves:
    for kp in fc.keyframe_points:
        kp.interpolation = "LINEAR"
```

## Lighting presets

```python
def key_light(energy=400, size=4, loc=(3, -3, 4)):
    bpy.ops.object.light_add(type="AREA", location=loc)
    light = bpy.context.object
    light.data.energy = energy
    light.data.size = size
    c = light.constraints.new(type="TRACK_TO")
    return light

# studio: white world + one big soft key + weak fill
scene.world = bpy.data.worlds.new("World")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.9, 0.9, 0.9, 1)
bg.inputs[1].default_value = 0.6
```

Use `light.data.energy` in **watts** for AREA/POINT; a 4 m area light at 400 W is a
soft daylight feel. Rim-light a dark scene with a small AREA at 800 W, low size (0.5).

## Materials

```python
def mat(name, base=(0.8, 0.2, 0.15, 1), rough=0.35, metal=0.0, emit=None, strength=4.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = emit
        bsdf.inputs["Emission Strength"].default_value = strength
    return m
```

`Emission Color` / `Emission Strength` are the 4.x names. On 3.x it is one
`"Emission"` socket — check `if "Emission Color" in bsdf.inputs`.

## Text objects (kinetic type)

```python
bpy.ops.object.text_add(location=(0, 0, 0))
txt = bpy.context.object
txt.data.body = "HELLO"
txt.data.align_x = "CENTER"
txt.data.extrude = 0.02
txt.data.size = 0.6
txt.rotation_euler = (math.radians(72), 0, 0)   # face the camera
```

## Keyframe helper (any property, any value)

```python
def kf(obj, path, frame, value):
    setattr(obj, path, value)
    obj.keyframe_insert(path, frame=frame)

kf(cube, "location", 1, (0, 0, 0))
kf(cube, "location", 48, (0, 0, 1.5))
```

## Animate a value with no object (driver-free)

```python
scene.frame_set(1)                       # drivers/constraints evaluate per frame
for f in range(scene.frame_start, scene.frame_end + 1):
    pass                                 # never loop frames for animation — keyframe instead
```

## Output: H.264 MP4

```python
out_dir = os.path.dirname(os.path.abspath(out_path))
os.makedirs(out_dir, exist_ok=True)
r = scene.render
r.image_settings.file_format = "FFMPEG"
r.ffmpeg.format = "MPEG4"
r.ffmpeg.codec = "H264"
r.ffmpeg.constant_rate_factor = "HIGH"
r.filepath = out_path                  # ends in .mp4, e.g. "render/out.mp4"
r.resolution_x, r.resolution_y = 1920, 1080   # both EVEN for H.264
```

## Output: transparent PNG sequence

```python
r.image_settings.file_format = "PNG"
r.image_settings.color_mode = "RGBA"
r.film_transparent = True
r.filepath = "render/frames/frame_"    # trailing name, Blender appends 0001.png
```

## Render just one frame (for QA)

```python
scene.frame_set(24)
r.filepath = "render/preview.png"
r.image_settings.file_format = "PNG"
bpy.ops.render.render(write_still=True)
```

## Colour management

```python
scene.view_settings.view_transform = "AgX"      # Blender 4.x default
# "Standard" for UI-accurate flat colour, "Filmic" for 3.x
```

## Headless notes

- `blender -b -P script.py -- <args>` — everything after `--` reaches `sys.argv`.
- Rendering with the **pip `bpy` module** instead of the Blender binary: run the
  script with a normal Python that has `bpy` installed. On Linux the wheel needs
  the X stack even for CPU rendering; if `import bpy` fails with
  `libXrender.so.1: cannot open shared object file`, either install
  `libxrender1 libxi6 libxfixes3 libxxf86vm1 libgl1 libxkbcommon0 libsm6 libice6`
  or point `LD_LIBRARY_PATH` at a directory holding stub `.so` files.
- `EEVEE` / `EEVEE Next` requires a GPU context; in CI it fails with
  `Unable to open a display`. Use `CYCLES` + `device='CPU'` for anything unattended.
- Set `scene.render.threads_mode = "AUTO"` (default) — do not pin thread counts.
