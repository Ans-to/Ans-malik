"""
SILICON — a 15 second title film, built and rendered entirely from Blender Python.

    blender --background --factory-startup --python blender-film/scene.py -- --preset preview

Nothing here is placed by eye. Typography is measured after creation and scaled to a fraction of the
visible frame at its own depth, so a lens or resolution change cannot push type out of frame. Every
move is baked by sampling a cubic-bezier motion token from film_config.EASING frame by frame, so the
timing is identical at 540p and 1080p and no f-curve interpolation can drift between them.

Shots (see film_config.SHOTS):
    A  1-90    dust motes drifting through a shaft of light     "It begins as sand."
    B  91-195  a silicon die, wireframe resolving to solid
    C  196-300 kinetic type + a mechanical odometer             "Twenty-six billion switches."
    D  301-378 macro slabs, focus rack                          "Each one smaller than a virus."
    E  379-450 lockup                                           "SILICON"
"""

import argparse
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import film_config as FC


# --------------------------------------------------------------------------- easing
def _bez(t, a, b):
    """One axis of a cubic bezier with P0=0, P1=a, P2=b, P3=1."""
    return 3 * (1 - t) ** 2 * t * a + 3 * (1 - t) * t * t * b + t ** 3


def ease_bezier(x, cp):
    """Progress y for time x through a cubic-bezier timing function. Bisection cannot diverge."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    x1, y1, x2, y2 = cp
    lo, hi, t = 0.0, 1.0, x
    for _ in range(20):
        if _bez(t, x1, x2) < x:
            lo = t
        else:
            hi = t
        t = 0.5 * (lo + hi)
    return _bez(t, y1, y2)


def ease(frame, f0, f1, curve="standard"):
    if f1 <= f0:
        return 1.0
    return ease_bezier(min(1.0, max(0.0, (frame - f0) / float(f1 - f0))), FC.EASING[curve])


def sample(f0, f1, step=2):
    fs = list(range(int(f0), int(f1) + 1, step))
    if fs[-1] != int(f1):
        fs.append(int(f1))
    return fs


def lerp(a, b, t):
    return a + (b - a) * t


# --------------------------------------------------------------------------- animation baking
def bake_vec(owner, path, frames, fn):
    """Bake a 3-vector, e.g. object location, sampling fn per frame."""
    for f in frames:
        setattr(owner, path, tuple(fn(f)))
        owner.keyframe_insert(data_path=path, frame=f)


def bake_float(owner, path, frames, fn, index=-1):
    """Bake a scalar or one component.

    `owner` must be the ID that owns the property (object, camera data, light data) because that is
    what carries keyframe_insert. A dotted path is resolved for the value assignment but keyed on the
    ID, which is how Blender expects nested RNA such as `dof.focus_distance` to be animated.
    """
    node = owner
    parts = path.split(".")
    for part in parts[:-1]:
        node = getattr(node, part)
    leaf = parts[-1]
    for f in frames:
        v = fn(f)
        if index >= 0:
            getattr(node, leaf)[index] = v
            owner.keyframe_insert(data_path=path, frame=f, index=index)
        else:
            setattr(node, leaf, v)
            owner.keyframe_insert(data_path=path, frame=f)


def bake_socket(socket, frames, fn, tree=None, path=None):
    for f in frames:
        socket.default_value = fn(f)
        if tree is not None and path is not None:
            tree.keyframe_insert(data_path=path, frame=f)
        else:
            socket.keyframe_insert(data_path="default_value", frame=f)


def emis_ref(mat_name):
    """(node_tree, data path, socket) for a material's Emission Strength."""
    mat = _MATERIALS[mat_name]
    bsdf = _DEFAULT_BSDF[mat_name]
    for i, inp in enumerate(bsdf.inputs):
        if inp.name == "Emission Strength":
            return mat.node_tree, f'nodes["{bsdf.name}"].inputs[{i}].default_value', inp
    raise KeyError(f"{mat_name} has no Emission Strength socket")


def bake_emis(mat_name, frames, fn):
    """Animate a material's emission strength, keyed through the node tree."""
    tree, path, sock = emis_ref(mat_name)
    bake_socket(sock, frames, fn, tree, path)


# --------------------------------------------------------------------------- bpy helpers
SOCKETS_ALIASES = {
    "base": ("Base Color",),
    "metallic": ("Metallic",),
    "rough": ("Roughness",),
    "emis": ("Emission Color", "Emission"),
    "emis_str": ("Emission Strength",),
    "alpha": ("Alpha",),
}

_DEFAULT_BSDF = {}   # material name -> principled node, so sockets can be animated later
_MATERIALS = {}      # material name -> material, so animation never has to re-look-up by name


def socket(node, key):
    for name in SOCKETS_ALIASES.get(key, (key,)):
        if name in node.inputs:
            return node.inputs[name]
    return None


def set_named(node, names, value):
    """Set the first input socket that exists under any of `names`. Socket names move between
    Blender releases (Lens Distortion is "Distort" before 3.0 and "Distortion" after), and a hard
    KeyError at build time costs a whole CI round trip."""
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return True
    print(f"[warn] {node.name if hasattr(node, 'name') else node} has none of {names}")
    return False


def material(name, base=None, rough=0.5, metallic=0.0, emis=None, emis_str=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) \
            or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    if base is not None:
        socket(bsdf, "base").default_value = base
    socket(bsdf, "rough").default_value = rough
    socket(bsdf, "metallic").default_value = metallic
    if emis is not None:
        socket(bsdf, "emis").default_value = emis
        socket(bsdf, "emis_str").default_value = emis_str
    if alpha < 1.0:
        socket(bsdf, "alpha").default_value = alpha
        try:
            mat.blend_method = "BLEND"
        except (AttributeError, TypeError):
            pass
    _DEFAULT_BSDF[mat.name] = bsdf
    _MATERIALS[mat.name] = mat
    return mat


def box(name, dims, loc=(0, 0, 0), rot=(0, 0, 0), mat=None, bevel=0.0, segments=3):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.scale = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0.0:
        md = ob.modifiers.new("bevel", "BEVEL")
        md.width = bevel
        md.segments = segments
        md.limit_method = "ANGLE"
        md.angle_limit = math.radians(35)
    if mat is not None:
        ob.data.materials.append(mat)
    return ob


def plane(name, size, loc, rot=(0, 0, 0), mat=None):
    bpy.ops.mesh.primitive_plane_add(size=size, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    if mat is not None:
        ob.data.materials.append(mat)
    return ob


def area_light(name, loc, target, energy, size, color, size_y=None):
    bpy.ops.object.light_add(type="AREA", location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.data.shape = "RECTANGLE"
    ob.data.size = size
    if size_y is not None:
        ob.data.size_y = size_y
    ob.data.energy = energy
    ob.data.color = color
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    return ob


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()


def camera(name, loc, target, lens, fstop=None, focus=None):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    cam.name = name
    cam.data.lens = lens
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.clip_start = 0.01
    cam.data.clip_end = 200.0
    aim(cam, target)
    if fstop is not None:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.focus_distance = focus if focus is not None else (
            Vector(target) - cam.location).length
    return cam


def vis_size(cam, distance, scene):
    """Visible width/height in world units on a plane `distance` in front of a camera."""
    w = 2.0 * distance * math.tan(cam.data.angle / 2.0)
    h = w * scene.render.resolution_y / float(scene.render.resolution_x)
    return w, h


class Rig:
    """A camera-facing empty. Children are laid out in screen space: +x right, +y up, +z toward cam."""

    def __init__(self, cam, distance, scene):
        bpy.context.view_layer.update()
        fwd = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        self.empty = bpy.data.objects.new("rig_" + cam.name, None)
        self.empty.location = cam.location + fwd * distance
        self.empty.rotation_euler = cam.rotation_euler
        scene.collection.objects.link(self.empty)
        self.distance = distance
        self.w, self.h = vis_size(cam, distance, scene)


def type_line(name, body, mat, rig, cap_frac, x=0.0, y=0.0, z=0.0, align="CENTER",
              tracking=1.06, extrude=0.010, bevel=0.0018):
    """Create a text object whose cap height is `cap_frac` of the visible frame height.

    Returns (object, width, height) in world units. The object is parented to the rig, so its
    location is screen-aligned: x in units right, y in units up (already centred on the block).
    """
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.align_x = "CENTER" if align == "CENTER" else "LEFT"
    cu.align_y = "BOTTOM"
    cu.size = 1.0
    cu.space_character = tracking
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(mat)
    bpy.context.view_layer.update()

    dims = ob.dimensions
    s = (cap_frac * rig.h) / max(dims.y, 1e-6)
    ob.scale = (s, s, s)
    bpy.context.view_layer.update()
    dims = ob.dimensions

    ob.parent = rig.empty
    ob.location = (x, y - dims.y * 0.5, z)
    return ob, dims.x, dims.y


def hide_except(obj, f0, f1):
    """Render only between f0 and f1 inclusive."""
    for frame, hidden in ((f0 - 1, True), (f0, False), (f1, False), (f1 + 1, True)):
        obj.hide_render = hidden
        obj.keyframe_insert(data_path="hide_render", frame=frame)


# --------------------------------------------------------------------------- scene skeleton
def configure(scene, preset_cfg):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = preset_cfg["samples"]
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 2
    scene.cycles.transparent_max_bounces = 2
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.use_light_tree = True
    scene.cycles.filter_width = 1.2
    scene.cycles.seed = 7

    scene.render.resolution_x = preset_cfg["width"]
    scene.render.resolution_y = preset_cfg["height"]
    scene.render.resolution_percentage = 100
    scene.render.fps = FC.FPS
    scene.render.film_transparent = False
    scene.render.use_persistent_data = True
    scene.render.use_motion_blur = preset_cfg["motion_blur"]
    scene.render.motion_blur_shutter = 0.35

    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 40

    scene.view_settings.view_transform = "AgX"
    for look in ("AgX - Punchy", "Punchy", "AgX - Medium High Contrast"):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            continue

    scene.frame_start = 1
    scene.frame_end = FC.FRAMES


def build_world(scene):
    """A gradient dome instead of flat black: cheap, and it gives every shot a soft studio sweep."""
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 0.55
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")

    nt.links.new(coord.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    els = ramp.color_ramp.elements
    els[0].position = 0.0
    els[0].color = FC.srgb("#050505")
    els[1].position = 0.62
    els[1].color = FC.srgb("#171310")
    mid = els.new(0.88)
    mid.color = FC.srgb("#2A211A")
    top = els.new(0.55)
    top.color = FC.srgb("#0C0B0A")
    return world


def build_compositor(scene):
    scene.use_nodes = True
    nt = scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)

    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 0.9
    glare.size = 8
    glare.mix = -0.88
    lens = nt.nodes.new("CompositorNodeLensdist")
    # the socket is "Distort" in old releases and "Distortion" from 3.0 on; never index by one name
    set_named(lens, ("Distortion", "Distort"), 0.004)
    set_named(lens, ("Dispersion",), 0.010)

    mask = nt.nodes.new("CompositorNodeEllipseMask")
    mask.mask_width = 0.92
    mask.mask_height = 0.92
    blur = nt.nodes.new("CompositorNodeBlur")
    blur.size_x = 220
    blur.size_y = 220
    vig = nt.nodes.new("CompositorNodeMixRGB")
    vig.blend_type = "MULTIPLY"
    vig.inputs[0].default_value = 0.55
    comp = nt.nodes.new("CompositorNodeComposite")

    nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
    nt.links.new(glare.outputs["Image"], lens.inputs["Image"])
    nt.links.new(lens.outputs["Image"], vig.inputs[1])
    nt.links.new(mask.outputs["Mask"], blur.inputs["Image"])
    nt.links.new(blur.outputs["Image"], vig.inputs[2])
    nt.links.new(vig.outputs["Image"], comp.inputs["Image"])
    return nt


def build_lights(scene):
    """One global three-light rig: soft key, copper rim, and a very low fill so nothing reads flat."""
    key = area_light("L_key", (3.4, -3.6, 3.1), (0.2, 0.4, 0.5), 420.0, 3.6, FC.srgb("#FFF4E4")[0:3])
    area_light("L_rim", (-3.1, 2.6, 2.4), (0.0, 0.0, 0.4), 620.0, 1.1,
               FC.srgb("#C9723F")[0:3], size_y=3.4)
    area_light("L_fill", (-2.8, -3.2, 0.9), (0.0, 0.0, 0.4), 55.0, 4.0, FC.srgb("#7C878E")[0:3])
    return key


# --------------------------------------------------------------------------- shot A
def shot_a(scene, cam, rig):
    s = FC.SHOTS[0]
    f0, f1 = s["start"], s["end"]
    rng = random.Random(11)

    floor = plane("A_floor", 26.0, (0.0, 1.0, -0.10), mat=material(
        "M_floor", FC.srgb("#0B0A09"), rough=0.42, metallic=0.15))
    hide_except(floor, f0, FC.SHOTS[1]["end"])

    # dust motes — the "sand" the voice-over names
    mats = [material("M_mote_sand", FC.srgb("#D8C4A2"), rough=0.35, emis=FC.srgb("#D8C4A2"),
                     emis_str=0.6),
            material("M_mote_copper", FC.srgb("#C9723F"), rough=0.3, emis=FC.srgb("#C9723F"),
                     emis_str=0.9),
            material("M_mote_bone", FC.srgb("#EDE4D6"), rough=0.25, emis=FC.srgb("#EDE4D6"),
                     emis_str=1.4)]
    for i in range(190):
        size = rng.uniform(0.0035, 0.016)
        x = rng.uniform(-2.7, 2.7)
        y = rng.uniform(-0.7, 3.5)
        z = rng.uniform(0.02, 2.5)
        pick = rng.random()
        mat = mats[0] if pick < 0.58 else (mats[1] if pick < 0.84 else mats[2])
        ob = box(f"A_mote_{i}", (size, size * rng.uniform(0.6, 1.4), size),
                 (x, y, z),
                 (rng.uniform(0, 6.3), rng.uniform(0, 6.3), rng.uniform(0, 6.3)), mat)
        hide_except(ob, f0, f1)
        # a slow tumble plus a little float, baked so it is identical on every render
        spin = rng.uniform(0.4, 1.7)
        ph = rng.uniform(0, math.tau)
        for f in sample(f0, f1, 6):
            t = (f - f0) / float(FC.FRAMES)
            ob.rotation_euler = (t * spin + ph, t * spin * 0.7, ph * 0.5)
            ob.location = (x + math.sin(t * 3.0 + ph) * 0.05,
                           y + t * 0.35,
                           z + math.cos(t * 2.2 + ph) * 0.05)
            ob.keyframe_insert("rotation_euler", frame=f)
            ob.keyframe_insert("location", frame=f)

    # the shaft: a narrow, hot area light raking in from the left
    shaft = area_light("A_shaft", (-2.5, -1.4, 2.6), (0.6, 0.2, 0.5), 900.0, 0.5,
                       FC.srgb("#FFF6EA")[0:3], size_y=3.2)
    hide_except(shaft, f0, f1)

    # ---- type: two lines, staggered, arriving out of depth
    lines = FC.TYPE["A"]
    for idx, (body, off, cap) in enumerate(lines):
        mat = material(f"M_A_type{idx}", FC.srgb("#EDE4D6"), rough=0.4,
                       emis=FC.srgb("#EDE4D6"), emis_str=0.0)
        y = (0.085 - idx * 0.165) * rig.h
        ob, w, h = type_line(f"A_type{idx}", body, mat, rig, cap, y=y, tracking=1.14, extrude=0.012)
        start = f0 + off
        bake_float(ob, "location", sample(start - 1, start + 12), lambda f, y=y, st=start: (
            y - (ob.dimensions.y * 0.5) + (1.0 - ease(f, st, st + 10, "decelerate")) * 0.055 * rig.h
        ), index=1)
        bake_float(ob, "location", sample(start - 1, start + 14), lambda f, st=start: (
            -0.5 + 0.5 * ease(f, st, st + 14, "decelerate")
        ), index=2)
        bake_emis(mat.name, sample(start - 1, start + 8),
                    lambda f, st=start: 2.8 * ease(f, st, st + 8, "decelerate"))
        hide_except(ob, f0, f1)

    # measure rule, draws in under the type
    rule_mat = material("M_A_rule", FC.srgb("#C9723F"), rough=0.3,
                                       emis=FC.srgb("#C9723F"), emis_str=2.2)
    rule_w = 0.30 * rig.w
    rule = box("A_rule", (rule_w, 0.0022 * rig.h, 0.004), (0.0, 0.0, 0.0), mat=rule_mat)
    rule.parent = rig.empty
    rule.location = (0.0, -0.205 * rig.h, 0.0)
    start = f0 + 24
    bake_float(rule, "scale", sample(start, start + 16),
               lambda f, st=start: 0.001 + 0.999 * ease(f, st, st + 16, "standard"), index=0)
    bake_float(rule, "location", sample(start, start + 16),
               lambda f, st=start: -0.5 * rule_w * (1.0 - ease(f, st, st + 16, "standard")),
               index=0)
    bake_emis(rule_mat.name, sample(start - 1, start + 18),
                lambda f, st=start: 2.4 * ease(f, st, st + 10, "decelerate"))
    hide_except(rule, f0, f1)

    # camera: slow push, then a whip out on the last beat
    bake_vec(cam, "location", sample(f0, f1), lambda f: (
        0.15 + 0.10 * ease(f, f0, f1, "linear"),
        lerp(-4.62, -4.06, ease(f, f0, f1, "decelerate")),
        0.85,
    ))
    bake_float(cam.data, "dof.aperture_fstop", sample(f0, f1, 10),
               lambda f: 2.4 + 0.9 * ease(f, f0 + 30, f1, "linear"))
    bake_float(cam, "rotation_euler", sample(f0, f1, 10),
               lambda f: math.radians(-0.55) * ease(f, f1 - 9, f1, "accelerate"), index=2)

    # whip the whole typographic plane out of frame in the last 7 frames
    bake_float(rig.empty, "location", sample(f1 - 7, f1),
               lambda f: 1.35 * ease(f, f1 - 7, f1, "accelerate"), index=0)


# --------------------------------------------------------------------------- shot B
def build_die(scene):
    """A silicon die: dark substrate, copper pads, corner tabs. Returns (root, pads)."""
    root = bpy.data.objects.new("B_die", None)
    scene.collection.objects.link(root)

    sub = material("M_substrate", FC.srgb("#14171A"), rough=0.28, metallic=0.85)
    copper = material("M_copper", FC.srgb("#C9723F"), rough=0.26, metallic=1.0)
    edge = material("M_edge", FC.srgb("#EDE4D6"), rough=0.2, metallic=1.0)

    base = box("B_die_base", (2.20, 2.20, 0.085), (0, 0, 0), mat=sub, bevel=0.006, segments=3)
    base.parent = root

    for i in range(4):
        a = math.radians(45 + 90 * i)
        tab = box(f"B_tab_{i}", (0.30, 0.16, 0.055),
                  (math.cos(a) * 1.02, math.sin(a) * 1.02, 0.05), (0, 0, a), mat=edge,
                  bevel=0.004)
        tab.parent = root

    pads = []
    n = 12
    span = 1.86
    step = span / (n - 1)
    for iy in range(n):
        for ix in range(n):
            x = -span / 2 + ix * step
            y = -span / 2 + iy * step
            h = 0.014 if (ix + iy) % 5 else 0.022
            p = box(f"B_pad_{ix}_{iy}", (0.105, 0.105, h), (x, y, 0.043 + h / 2), mat=copper,
                    bevel=0.0015, segments=2)
            p.parent = root
            pads.append(p)
    return root, pads, base, copper


def shot_b(scene, cam, rig, die, pads, base):
    s = FC.SHOTS[1]
    f0, f1 = s["start"], s["end"]

    under = plane("B_underglow", 7.0, (0.0, 0.0, -0.06),
                  mat=material("M_underglow", FC.srgb("#C9723F"), rough=0.6,
                               emis=FC.srgb("#C9723F"), emis_str=1.6))
    hide_except(under, f0 - 6, FC.FRAMES)

    # wireframe shell that resolves into solid geometry
    wire_mat = material("M_wire", FC.srgb("#C9723F"), rough=0.4, emis=FC.srgb("#E88A4E"),
                        emis_str=7.0)
    wire = box("B_wire", (2.34, 2.34, 0.13), (0, 0, 0.0), mat=wire_mat)
    md = wire.modifiers.new("wire", "WIREFRAME")
    md.thickness = 0.0045
    md.use_replace = True
    hide_except(wire, f0, f0 + 34)
    bake_emis("M_wire", sample(f0 + 20, f0 + 34),
                lambda f: 7.0 * (1.0 - ease(f, f0 + 20, f0 + 34, "accelerate")))

    # the sweep: a moving strip light, invisible to camera, that rakes a specular band across the die
    sweep = area_light("B_sweep", (-3.2, -0.5, 1.35), (0.0, 0.0, 0.05), 0.0, 0.14,
                       FC.srgb("#FFF6EA")[0:3], size_y=7.0)
    hide_except(sweep, f0, f1)
    bake_vec(sweep, "location", sample(f0 + 36, f0 + 52), lambda f: (
        lerp(-3.3, 3.5, ease(f, f0 + 36, f0 + 52, "standard")), -0.5, 1.35))
    bake_float(sweep.data, "energy", sample(f0 + 34, f0 + 54), lambda f: (
        1400.0 * math.sin(math.pi * ease(f, f0 + 34, f0 + 54, "linear"))))

    # silicon caption, small and quiet
    cap_mat = material("M_B_cap", FC.srgb("#7C878E"), rough=0.5,
                                      emis=FC.srgb("#7C878E"), emis_str=0.0)
    cap, _, _ = type_line("B_cap", "Si  ·  14", cap_mat, rig, 0.030,
                          x=-0.50 * rig.w, y=-0.40 * rig.h, align="LEFT", tracking=1.3)
    bake_emis(cap_mat.name, sample(f0 + 56, f0 + 68),
                lambda f: 1.6 * ease(f, f0 + 56, f0 + 68, "decelerate"))
    hide_except(cap, f0, f1)

    # die motion: a slow settle and quarter turn
    bake_vec(die, "rotation_euler", sample(f0, f1), lambda f: (
        math.radians(lerp(13.0, -5.0, ease(f, f0, f1, "decelerate"))),
        math.radians(lerp(-4.0, 3.0, ease(f, f0, f1, "standard"))),
        math.radians(lerp(24.0, 74.0, ease(f, f0, f1, "decelerate"))),
    ))
    bake_vec(die, "location", sample(f0, f1), lambda f: (
        0.0, 0.0, 0.02 * math.sin((f - f0) / 26.0),
    ))

    # camera orbit: 4.9 m out, swinging 22 degrees, shallow enough to keep the pads crisp
    def orbit(f):
        a = math.radians(lerp(-34.0, -12.0, ease(f, f0, f1, "linear")))
        r = lerp(5.05, 4.55, ease(f, f0, f1, "decelerate"))
        h = lerp(2.60, 2.25, ease(f, f0, f1, "linear"))
        return (math.sin(a) * r, -math.cos(a) * r, h)

    bake_vec(cam, "location", sample(f0, f1), orbit)
    for f in sample(f0, f1):
        cam.location = orbit(f)
        aim(cam, (0.0, 0.0, 0.10))
        cam.keyframe_insert("rotation_euler", frame=f)
    bake_float(cam.data, "dof.focus_distance", sample(f0, f1, 10),
               lambda f: 4.9 - 0.35 * ease(f, f0, f1, "decelerate"))

    # push in over the last beat so the cut into shot C lands hard
    bake_vec(cam, "location", sample(f1 - 8, f1), lambda f: (
        orbit(f)[0] * lerp(1.0, 0.72, ease(f, f1 - 8, f1, "accelerate")),
        orbit(f)[1] * lerp(1.0, 0.72, ease(f, f1 - 8, f1, "accelerate")),
        orbit(f)[2],
    ))


# --------------------------------------------------------------------------- shot C
def reel_digits(rig, y, cap, target, x, mat_bone, mat_copper, first_two_copper):
    """One mechanical odometer column: ten digits on a reel that slides into place."""
    dy = cap * 1.22
    reel = bpy.data.objects.new(f"C_reel_{target}_{int(x * 1000)}", None)
    scene = bpy.context.scene
    scene.collection.objects.link(reel)
    reel.parent = rig.empty
    reel.location = (x, y, 0.0)
    mat = mat_copper if first_two_copper else mat_bone
    for v in range(10):
        cu = bpy.data.curves.new(f"C_d{v}", "FONT")
        cu.body = str(v)
        cu.align_x = "CENTER"
        cu.align_y = "CENTER"
        cu.size = 1.0
        cu.space_character = 1.0
        cu.extrude = 0.010
        cu.bevel_depth = 0.0016
        ob = bpy.data.objects.new(f"C_d{target}{v}_{int(x * 1000)}", cu)
        scene.collection.objects.link(ob)
        ob.data.materials.append(mat)
        bpy.context.view_layer.update()
        s = cap / max(ob.dimensions.y, 1e-6)
        ob.scale = (s, s, s)
        ob.parent = reel
        ob.location = (0.0, (v - target) * dy, 0.0)
        hide_except(ob, FC.SHOTS[2]["start"], FC.SHOTS[2]["end"])
    return reel


def shot_c(scene, cam, rig, die, y_cap=0.062):
    s = FC.SHOTS[2]
    f0, f1 = s["start"], s["end"]

    bone = material("M_C_bone", FC.srgb("#EDE4D6"), rough=0.42, emis=FC.srgb("#EDE4D6"),
                    emis_str=0.0)
    copper = material("M_C_copper", FC.srgb("#C9723F"), rough=0.36, emis=FC.srgb("#E88A4E"),
                      emis_str=0.0)

    # ---- three lines of kinetic type, left aligned on one edge
    x0 = -0.36 * rig.w
    for idx, (body, off, cap) in enumerate(FC.TYPE["C"]):
        m = material(f"M_C_line{idx}", FC.srgb("#EDE4D6"), rough=0.42,
                     emis=FC.srgb("#EDE4D6"), emis_str=0.0)
        ob, w, h = type_line(f"C_line{idx}", body, m, rig, cap,
                             x=x0, y=(0.235 - idx * 0.150) * rig.h, align="LEFT", tracking=1.10)
        start = f0 + off
        bake_float(ob, "location", sample(start - 1, start + 12),
                   lambda f, st=start: x0 - 0.11 * rig.w * (1.0 - ease(f, st, st + 12, "decelerate")),
                   index=0)
        bake_emis(m.name, sample(start - 1, start + 9),
                    lambda f, st=start: 2.6 * ease(f, st, st + 9, "decelerate"))
        hide_except(ob, f0, f1)

    # ---- odometer: 26,000,000,000
    digits = list("26000000000")
    cell = 0.049 * rig.w
    comma_w = 0.017 * rig.w
    total = len(digits) * cell + 3 * comma_w
    x = -(total / 2.0) - rig.w * 0.005
    y = -0.215 * rig.h
    reels = []
    for i, ch in enumerate(digits):
        reel = reel_digits(rig, y, y_cap * rig.h, int(ch), x,
                           bone, copper, first_two_copper=(i < 2))
        reels.append(reel)
        x += cell
        if i in (1, 4, 7):        # groups of three after the leading pair
            cu = bpy.data.curves.new(f"C_comma{i}", "FONT")
            cu.body = ","
            cu.align_x = "CENTER"
            cu.align_y = "CENTER"
            cu.size = 1.0
            cu.space_character = 1.0
            comma = bpy.data.objects.new(f"C_comma{i}", cu)
            scene.collection.objects.link(comma)
            comma.data.materials.append(bone)
            bpy.context.view_layer.update()
            cs = (y_cap * rig.h) / max(comma.dimensions.y, 1e-6)
            comma.scale = (cs, cs, cs)
            comma.parent = rig.empty
            comma.location = (x - cell * 0.5, y - y_cap * rig.h * 0.30, 0.0)
            hide_except(comma, f0, f1)
            x += comma_w

    dy = y_cap * rig.h * 1.22
    for i, reel in enumerate(reels):
        start = f0 + 18 + i * 2
        bake_float(reel, "location", sample(start - 1, start + 26),
                   lambda f, st=start, d=dy, by=y: by + d * 3.0 * (
                       1.0 - ease(f, st, st + 26, "emphasized")),
                   index=1)

    # ---- the die falls back into the frame as out-of-focus depth
    bake_vec(die, "location", [196], lambda f: (0.55, 5.2, -1.15))
    bake_vec(die, "rotation_euler", [196], lambda f: (
        math.radians(58.0), math.radians(6.0), math.radians(112.0)))
    bake_vec(die, "scale", [196], lambda f: (2.9, 2.9, 2.9))

    # ---- camera: locked off, breathing, then a push into the cut
    bake_vec(cam, "location", sample(f0, f1), lambda f: (
        0.0, lerp(-5.65, -5.42, ease(f, f0, f1, "linear")), 0.42))
    bake_vec(cam, "location", sample(f1 - 7, f1), lambda f: (
        0.0, lerp(-5.42, -4.55, ease(f, f1 - 7, f1, "accelerate")), 0.42))
    bake_float(cam, "rotation_euler", sample(f0, f1, 10),
               lambda f: math.radians(0.35) * ease(f, f1 - 7, f1, "accelerate"), index=1)


# --------------------------------------------------------------------------- shot D
def shot_d(scene, cam, rig):
    s = FC.SHOTS[3]
    f0, f1 = s["start"], s["end"]

    slab_mat = material("M_slab", FC.srgb("#1B1E21"), rough=0.24, metallic=0.9)
    edge_mat = material("M_slab_edge", FC.srgb("#C9723F"), rough=0.3, metallic=1.0,
                        emis=FC.srgb("#C9723F"), emis_str=0.8)

    specs = [((0.0, 0.30, 0.94), -8.0, 0.0), ((0.06, 0.95, 0.62), 5.0, 1.2),
             ((-0.04, 1.60, 0.30), -3.0, -0.8)]
    for i, (loc, rot_z, tilt) in enumerate(specs):
        slab = box(f"D_slab{i}", (1.95, 0.80, 0.075), loc,
                   (math.radians(tilt), 0.0, math.radians(rot_z)), mat=slab_mat, bevel=0.004)
        strip = box(f"D_edge{i}", (1.97, 0.022, 0.020),
                    (loc[0], loc[1] - 0.39, loc[2] + 0.036),
                    (math.radians(tilt), 0.0, math.radians(rot_z)), mat=edge_mat)
        hide_except(slab, f0 - 4, f1)
        hide_except(strip, f0 - 4, f1)
        for f in sample(f0, f1, 8):
            t = ease(f, f0, f1, "linear")
            slab.location = (loc[0] + math.sin(t * 2.0 + i) * 0.012, loc[1], loc[2] + t * 0.02)
            slab.keyframe_insert("location", frame=f)

    rim = area_light("D_top", (0.0, 0.4, 2.5), (0.0, 0.6, 0.5), 520.0, 2.4,
                     FC.srgb("#FFF4E4")[0:3], size_y=0.6)
    hide_except(rim, f0 - 4, f1)

    for idx, (body, off, cap) in enumerate(FC.TYPE["D"]):
        m = material(f"M_D_type{idx}", FC.srgb("#EDE4D6"), rough=0.4,
                                    emis=FC.srgb("#EDE4D6"), emis_str=0.0)
        ob, w, h = type_line(f"D_type{idx}", body, m, rig, cap,
                             x=-0.30 * rig.w, y=(0.275 - idx * 0.150) * rig.h,
                             align="LEFT", tracking=1.12)
        start = f0 + off
        bake_float(ob, "scale", sample(start - 1, start + 14),
                   lambda f, st=start, s0=ob.scale[0]: s0 * (1.14 - 0.14 * ease(
                       f, st, st + 14, "emphasized")), index=0)
        bake_float(ob, "scale", sample(start - 1, start + 14),
                   lambda f, st=start, s0=ob.scale[1]: s0 * (1.14 - 0.14 * ease(
                       f, st, st + 14, "emphasized")), index=1)
        bake_float(ob, "scale", sample(start - 1, start + 14),
                   lambda f, st=start, s0=ob.scale[2]: s0 * (1.14 - 0.14 * ease(
                       f, st, st + 14, "emphasized")), index=2)
        bake_emis(m.name, sample(start - 1, start + 10),
                    lambda f, st=start: 3.5 * ease(f, st, st + 10, "decelerate"))
        hide_except(ob, f0, f1)

    # Focus rack that lands on the lettering and stays there. These are 100 mm frames: at f/2 the
    # depth of field is about 15 cm, so a rack that runs from 2.35 m to 4.30 m through a type plane
    # at 3.0 m guarantees the words are soft for the whole shot -- which is what the type gate
    # caught. Rack from the near slab onto the type plane, hold, then close down for the exit.
    bake_float(cam.data, "dof.focus_distance", sample(f0, f1),
               lambda f: lerp(2.45, 2.10, ease(f, f0, f0 + 16, "decelerate")))
    bake_float(cam.data, "dof.aperture_fstop", sample(f0, f1),
               lambda f: lerp(2.2 + 0.8 * ease(f, f0, f0 + 30, "linear"),
                              16.0, ease(f, f1 - 8, f1, "accelerate")))
    # a small lateral drift only: the type plane is 2.1 m out now, so the old 0.25 m slide would
    # read as the words skating across the frame rather than as parallax
    bake_vec(cam, "location", sample(f0, f1), lambda f: (
        lerp(0.95, 0.86, ease(f, f0, f1, "linear")), -2.30, 0.55))


# --------------------------------------------------------------------------- shot E
def shot_e(scene, cam, rig):
    s = FC.SHOTS[4]
    f0, f1 = s["start"], s["end"]

    glow = area_light("E_glow", (0.0, 1.9, 1.15), (0.0, 0.0, 0.65), 700.0, 2.2,
                      FC.srgb("#C9723F")[0:3], size_y=1.2)
    hide_except(glow, f0 - 10, f1)
    bake_float(glow.data, "energy", sample(f1 - 12, f1),
               lambda f: 700.0 * (1.0 - 0.85 * ease(f, f1 - 12, f1, "accelerate")))

    card = plane("E_card", 9.0, (0.0, 3.6, 0.55),
                 mat=material("M_E_card", FC.srgb("#C9723F"), rough=0.7,
                              emis=FC.srgb("#C9723F"), emis_str=1.1))
    hide_except(card, f0 - 10, f1)
    bake_emis("M_E_card", sample(f1 - 12, f1),
                lambda f: 1.1 * (1.0 - 0.9 * ease(f, f1 - 12, f1, "accelerate")))

    # ---- the wordmark, one letter at a time
    word = FC.TITLE_WORD
    cap = 0.205
    tracking = 1.08
    letters = []
    mats = []
    x_cursor = 0.0
    for i, ch in enumerate(word):
        m = material(f"M_E_letter{i}", FC.srgb("#EDE4D6"), rough=0.38,
                                    emis=FC.srgb("#EDE4D6"), emis_str=0.0)
        ob, w, h = type_line(f"E_letter{i}_{ch}", ch, m, rig, cap, x=0.0, y=0.0,
                             tracking=tracking, extrude=0.016, bevel=0.0022)
        bpy.context.view_layer.update()
        letters.append((ob, w))
        mats.append(m)
        x_cursor += w + 0.012 * rig.w

    total = sum(w for _, w in letters) + 0.012 * rig.w * (len(letters) - 1)
    x = -total / 2.0
    for i, (ob, w) in enumerate(letters):
        ob.location = (x + w / 2.0, -0.02 * rig.h, 0.0)
        start = f0 + 3 + i * 3
        base_y = ob.location[1]
        bake_float(ob, "location", sample(start - 1, start + 16),
                   lambda f, st=start, by=base_y: (
                       by - 0.10 * rig.h * (1.0 - ease(f, st, st + 16, "emphasized"))), index=1)
        bake_emis(mats[i].name, sample(start - 1, start + 12),
                    lambda f, st=start: 3.0 * ease(f, st, st + 12, "decelerate"))
        hide_except(ob, f0, f1)
        x += w + 0.012 * rig.w

    # ---- copper rule, then the tagline
    rule_mat = material("M_E_rule", FC.srgb("#C9723F"), rough=0.3,
                                       emis=FC.srgb("#C9723F"), emis_str=0.0)
    rule_w = 0.46 * rig.w
    rule = box("E_rule", (rule_w, 0.0020 * rig.h, 0.004), (0.0, 0.0, 0.0), mat=rule_mat)
    rule.parent = rig.empty
    rule.location = (0.0, -0.115 * rig.h, 0.0)
    start = f0 + 25
    bake_float(rule, "scale", sample(start, start + 15),
               lambda f, st=start: 0.001 + 0.999 * ease(f, st, st + 15, "decelerate"), index=0)
    bake_float(rule, "location", sample(start, start + 15),
               lambda f, st=start: -0.5 * rule_w * (1.0 - ease(f, st, st + 15, "decelerate")),
               index=0)
    bake_emis(rule_mat.name, sample(start - 1, start + 16),
                lambda f, st=start: 2.2 * ease(f, st, st + 12, "decelerate"))
    hide_except(rule, f0, f1)

    tag_mat = material("M_E_tag", FC.srgb("#B9AF9E"), rough=0.5,
                                      emis=FC.srgb("#B9AF9E"), emis_str=0.0)
    tag, _, _ = type_line("E_tag", FC.TAGLINE, tag_mat, rig, 0.036, y=-0.175 * rig.h,
                          tracking=1.34)
    bake_emis(tag_mat.name, sample(f0 + 38, f0 + 50),
                lambda f: 1.5 * ease(f, f0 + 38, f0 + 50, "decelerate"))
    hide_except(tag, f0, f1)

    bake_vec(cam, "location", sample(f0, f1), lambda f: (
        0.0, lerp(-5.35, -5.05, ease(f, f0, f1, "linear")), 0.58))
    bake_float(cam.data, "lens", sample(f0, f1, 15), lambda f: lerp(85.0, 88.0, ease(f, f0, f1)))


# --------------------------------------------------------------------------- main
def build(preset, out_dir):
    cfg = FC.PRESETS[preset]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    configure(scene, cfg)
    build_world(scene)
    build_compositor(scene)
    build_lights(scene)

    # ---- cameras, one per shot, bound to timeline markers
    cams = {}
    cams["A"] = camera("CAM_A", (0.15, -4.62, 0.85), (0.0, 0.0, 0.72), 85, fstop=2.4,
                       focus=4.9)
    cams["B"] = camera("CAM_B", (-2.7, -4.2, 2.6), (0.0, 0.0, 0.10), 100, fstop=5.6,
                       focus=4.9)
    cams["C"] = camera("CAM_C", (0.0, -5.65, 0.42), (0.0, 0.0, 0.30), 85, fstop=2.8,
                       focus=5.65)
    cams["D"] = camera("CAM_D", (0.95, -2.30, 0.55), (0.0, 0.60, 0.45), 100, fstop=1.8,
                       focus=2.35)
    cams["E"] = camera("CAM_E", (0.0, -5.35, 0.58), (0.0, 0.0, 0.58), 85, fstop=5.6,
                       focus=5.35)

    for shot in FC.SHOTS:
        m = scene.timeline_markers.new(shot["key"], frame=shot["start"])
        m.camera = cams[shot["key"]]
    scene.camera = cams["A"]

    bpy.context.view_layer.update()
    rigs = {k: Rig(c, 5.0 if k != "D" else 2.10, scene) for k, c in cams.items()}

    # ---- the die spans shots B and C, so it is built once and driven twice
    die, pads, base, _ = build_die(scene)
    hide_except(die, 91, 300)

    shot_a(scene, cams["A"], rigs["A"])
    shot_b(scene, cams["B"], rigs["B"], die, pads, base)
    shot_c(scene, cams["C"], rigs["C"], die)
    shot_d(scene, cams["D"], rigs["D"])
    shot_e(scene, cams["E"], rigs["E"])

    # ---- global exposure: a soft fade up out of black, and a fade down to black at the end.
    # The delivered preview measured mean luma 0.3757 against a 0.34 ceiling, so the whole curve
    # sits 0.6 of a stop lower. This is a trim on the curve, not a change to the lighting design.
    EXPOSURE_TRIM = -0.6
    for f, val in ((1, -9.0), (10, 0.0), (376, 0.0), (382, -3.2), (390, 0.0),
                   (440, 0.0), (450, -10.0)):
        scene.view_settings.exposure = val + EXPOSURE_TRIM
        scene.keyframe_insert(data_path="view_settings.exposure", frame=f)

    scene.camera = cams["A"]
    scene.frame_set(1)

    type_rows = []
    for key, rows in FC.TYPE.items():
        start = next(sh["start"] for sh in FC.SHOTS if sh["key"] == key)
        for (body, off, cap) in rows:
            type_rows.append(dict(shot=key, body=body, frame=start + off, cap_frac=cap))

    # ---- project each line of type to a screen box, so the gates can measure the words themselves
    # rather than the whole frame. A frame-wide edge metric cannot tell a blurred word from a
    # deliberately sparse shot, which is exactly how shot D failed three times in a row.
    from bpy_extras.object_utils import world_to_camera_view

    res_x, res_y = cfg["width"], cfg["height"]
    seen = {"A": 0, "C": 0, "D": 0}
    for row in type_rows:
        key = row["shot"]
        if key == "B":
            name = "B_cap"
        else:
            name = {"A": "A_type{}", "C": "C_line{}", "D": "D_type{}"}[key].format(seen[key])
            seen[key] += 1
        ob = scene.objects.get(name)
        if ob is None:
            print(f"[scene] WARNING no object {name} for type row '{row['body']}'")
            row["box"] = None
            continue
        scene.frame_set(row["frame"])
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        eo = ob.evaluated_get(dg)
        pts = [world_to_camera_view(scene, scene.camera, eo.matrix_world @ Vector(c))
               for c in eo.bound_box]
        xs, ys = [p.x for p in pts], [p.y for p in pts]
        row["box"] = [round(min(xs), 4), round(1.0 - max(ys), 4),
                      round(max(xs), 4), round(1.0 - min(ys), 4)]
    scene.frame_set(1)

    manifest = dict(
        preset=preset,
        frames=FC.FRAMES,
        fps=FC.FPS,
        resolution=[cfg["width"], cfg["height"]],
        samples=cfg["samples"],
        objects=len(scene.objects),
        shots=[dict(key=s["key"], start=s["start"], end=s["end"], camera=s["camera"])
               for s in FC.SHOTS],
        type=type_rows,
        vo=FC.VO_LINES,
        palette=FC.PALETTE,
    )
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"manifest_{preset}.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    return scene, cams, manifest


def probe(scene, frames, boxes_out=""):
    """Print where every text object actually is at the given frames, and optionally its pixel box.

    The type gate can only say 'this line never produced a sharp frame'. It cannot say whether the
    words were hidden, off-screen, behind geometry, dark, or blown out into a smooth blob, so this
    answers that directly: hide flag, screen position, distance, emission strength, and the corners
    of its projected bounding box so a measurement can be taken inside the words themselves.
    """
    from bpy_extras.object_utils import world_to_camera_view

    w, h = scene.render.resolution_x, scene.render.resolution_y
    boxes = {}
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        cam = scene.camera
        print(f"[probe] frame {f}: camera {cam.name} at "
              f"{tuple(round(v, 2) for v in cam.location)}")
        boxes[str(f)] = {}
        for ob in scene.objects:
            if ob.type != "FONT":
                continue
            eo = ob.evaluated_get(dg)
            corners = [eo.matrix_world @ Vector(c) for c in eo.bound_box]
            centre = sum(corners, Vector()) / 8.0
            co = world_to_camera_view(scene, cam, centre)
            in_view = 0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0 and co.z > 0.0
            px = [world_to_camera_view(scene, cam, c) for c in corners]
            xs, ys = [p.x for p in px], [p.y for p in px]
            box = [int(min(xs) * w), int((1.0 - max(ys)) * h),
                   int(max(xs) * w), int((1.0 - min(ys)) * h)]
            boxes[str(f)][ob.name] = box
            mat = ob.active_material
            emis = None
            if mat is not None and mat.use_nodes:
                for n in mat.node_tree.nodes:
                    if n.type == "BSDF_PRINCIPLED" and "Emission Strength" in n.inputs:
                        emis = round(float(n.inputs["Emission Strength"].default_value), 2)
            print(f"[probe]   {ob.name:14s} hidden={int(bool(eo.hide_render))} "
                  f"in_view={int(in_view)} ndc=({co.x:.2f},{co.y:.2f}) depth={co.z:.2f} "
                  f"pos={tuple(round(v, 2) for v in centre)} emis={emis} box={box}")

    if boxes_out:
        os.makedirs(os.path.dirname(boxes_out) or ".", exist_ok=True)
        with open(boxes_out, "w") as fh:
            json.dump(boxes, fh, indent=1)
        print(f"[probe] boxes -> {boxes_out}")
    return boxes


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="preview", choices=sorted(FC.PRESETS))
    ap.add_argument("--out", default="blender-film/out")
    ap.add_argument("--smoke", default="", help="comma separated frames to render at low res instead")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--frame-start", type=int, default=1)
    ap.add_argument("--frame-end", type=int, default=FC.FRAMES)
    ap.add_argument("--probe", default="", help="comma separated frames: report type placement and exit")
    ap.add_argument("--probe-render", default="",
                    help="comma separated frames: render stills to out/probe/ at preview size, then exit")
    args = ap.parse_args(argv)

    scene, cams, manifest = build(args.preset, args.out)
    print(f"[scene] built {manifest['objects']} objects, {manifest['frames']} frames, "
          f"{manifest['resolution'][0]}x{manifest['resolution'][1]} @ {manifest['samples']} spp")

    if args.probe:
        probe(scene, [int(x) for x in args.probe.split(",") if x.strip()])
        return

    if args.no_render:
        return

    if args.probe_render:
        out = os.path.join(args.out, "probe")
        os.makedirs(out, exist_ok=True)
        scene.render.use_motion_blur = False
        frames = [int(x) for x in args.probe_render.split(",") if x.strip()]
        probe(scene, frames, os.path.join(out, "boxes.json"))
        for f in frames:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out, f"f_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"[probe-render] frame {f} -> {scene.render.filepath}")
        return

    if args.smoke:
        frames = [int(x) for x in args.smoke.split(",") if x.strip()]
        scene.render.resolution_x //= 2
        scene.render.resolution_y //= 2
        scene.cycles.samples = 8
        scene.render.use_motion_blur = False
        out = os.path.join(args.out, "smoke")
        os.makedirs(out, exist_ok=True)
        for f in frames:
            scene.frame_set(f)
            scene.render.filepath = os.path.join(out, f"smoke_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            print(f"[smoke] frame {f} written")
        return

    out = os.path.join(args.out, f"frames_{args.preset}")
    os.makedirs(out, exist_ok=True)
    scene.render.filepath = os.path.join(out, "f_")
    scene.render.use_overwrite = False
    # shards: a 1080p Cycles pass on a 2 vCPU runner is hours; split it across runners instead
    scene.frame_start = max(1, args.frame_start)
    scene.frame_end = min(FC.FRAMES, args.frame_end)
    print(f"[render] frames {scene.frame_start}..{scene.frame_end} of {FC.FRAMES}")
    bpy.ops.render.render(animation=True)
    print(f"[render] {args.preset} frames -> {out}")


if __name__ == "__main__":
    main()
