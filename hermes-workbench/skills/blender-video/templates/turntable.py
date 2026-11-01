#!/usr/bin/env python3
"""turntable.py — reference Blender video script (headless, parameterised).

Satisfies every rule in the blender-video skill contract:

    blender -b -P turntable.py -- --seconds 6 --look studio
    blender -b -P turntable.py -- --preview            # one still, cheap
    python  turntable.py -- --preview                  # same, via the bpy module

Options after `--`:
    --subject {monkey,cube,sphere,torus,text}   hero object (default: monkey)
    --look    {studio,neon,editorial,tech}      lighting/material preset (default: studio)
    --seconds FLOAT     duration (default 6)
    --fps     INT       frames per second (default 24)
    --width   INT       pixels (default 1920; preview default 640)
    --height  INT       pixels (default 1080; preview default 360)
    --samples INT       Cycles samples (default 64; preview 8)
    --frames  INT       render only N frames (default: all)
    --preview           render a single PNG still instead of video
    --out     PATH      output file (default render/<subject>_<look>.mp4)
"""

import argparse
import json
import math
import os
import random
import sys

import bpy


# ── scene construction ────────────────────────────────────────────────────────

def reset_scene():
    """Always start from an empty factory scene: no user state leaks in."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def add_world(scene, look: str):
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    if look == "neon":
        bg.inputs[0].default_value = (0.01, 0.012, 0.03, 1.0)
        bg.inputs[1].default_value = 0.35
    elif look == "editorial":
        bg.inputs[0].default_value = (0.86, 0.84, 0.80, 1.0)
        bg.inputs[1].default_value = 1.1
    elif look == "tech":
        bg.inputs[0].default_value = (0.02, 0.03, 0.05, 1.0)
        bg.inputs[1].default_value = 0.5
    else:  # studio
        bg.inputs[0].default_value = (0.92, 0.92, 0.92, 1.0)
        bg.inputs[1].default_value = 0.65


def aim(obj, target):
    """Point object -Z at a target via a constraint — never hand-rolled Euler math."""
    con = obj.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"


def add_hero(scene, subject: str, look: str):
    if subject == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1.4)
    elif subject == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.9, segments=48, ring_count=24)
    elif subject == "torus":
        bpy.ops.mesh.primitive_torus_add(major_radius=0.9, minor_radius=0.32)
    elif subject == "text":
        bpy.ops.object.text_add(location=(0, 0, 0))
        obj = bpy.context.object
        obj.data.body = "HERMES"
        obj.data.align_x = "CENTER"
        obj.data.align_y = "CENTER"
        obj.data.extrude = 0.08
        obj.data.size = 0.9
        obj.rotation_euler = (math.radians(72), 0, 0)
        obj.location = (0, 0.35, 0)
        return obj
    else:  # monkey
        bpy.ops.mesh.primitive_monkey_add(size=2.0)

    obj = bpy.context.object
    obj.name = "Hero"

    mat = bpy.data.materials.new("HeroMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    palette = {
        "studio": ((0.80, 0.35, 0.18, 1.0), 0.28, 0.0),
        "neon": ((0.05, 0.08, 0.12, 1.0), 0.15, 0.85),
        "editorial": ((0.62, 0.66, 0.60, 1.0), 0.55, 0.0),
        "tech": ((0.10, 0.55, 0.75, 1.0), 0.20, 0.60),
    }
    base, rough, metal = palette.get(look, palette["studio"])
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if look == "neon":
        bsdf.inputs["Emission Color"].default_value = (0.10, 0.65, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 2.0
    obj.data.materials.append(mat)
    return obj


def add_ground(scene, look: str):
    if look in {"neon", "tech"}:
        return None
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -1.05))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("GroundMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    shade = (0.78, 0.76, 0.74, 1.0) if look == "studio" else (0.70, 0.68, 0.64, 1.0)
    bsdf.inputs["Base Color"].default_value = shade
    bsdf.inputs["Roughness"].default_value = 0.65
    ground.data.materials.append(mat)
    return ground


def add_lights(scene, look: str, aim_target):
    specs = {
        "studio": [(400, 4.0, (3.2, -3.2, 3.6)), (90, 5.0, (-3.5, -2.0, 2.0))],
        "editorial": [(280, 6.0, (4.0, -1.5, 4.5)), (60, 6.0, (-4.0, -3.0, 2.5))],
        "neon": [(800, 0.6, (2.4, -2.2, 1.6)), (600, 0.5, (-2.6, -1.4, 2.2))],
        "tech": [(300, 3.0, (2.8, -2.8, 3.2)), (180, 0.8, (-3.0, -2.0, 1.2))],
    }[look]
    for energy, size, loc in specs:
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.name = f"Key_{energy}"
        light.data.energy = energy
        light.data.size = size
        if look == "neon":
            light.data.color = (0.35, 0.75, 1.0) if loc[0] > 0 else (1.0, 0.35, 0.55)
        aim(light, aim_target)


def add_camera(scene, aim_target, seconds: float):
    bpy.ops.object.camera_add(location=(4.4, -4.4, 2.6))
    cam = bpy.context.object
    cam.data.lens = 50
    aim(cam, aim_target)
    scene.camera = cam

    # Turntable: a pivot empty carries the camera around the subject.
    pivot = bpy.data.objects.new("Pivot", None)
    scene.collection.objects.link(pivot)
    cam.parent = pivot
    cam.matrix_parent_inverse = pivot.matrix_world.inverted()

    start, end = scene.frame_start, scene.frame_end
    pivot.rotation_euler = (0, 0, 0)
    pivot.keyframe_insert("rotation_euler", frame=start)
    pivot.rotation_euler = (0, 0, math.radians(120))
    pivot.keyframe_insert("rotation_euler", frame=end)
    for fcurve in pivot.animation_data.action.fcurves:
        for kp in fcurve.keyframe_points:
            kp.interpolation = "BEZIER"          # smooth accel/decel
            try:
                kp.easing = "EASE_IN_OUT"
            except (AttributeError, TypeError):
                pass                              # interpolation already smooth
    return cam, pivot


def add_motion(hero, seconds: float, scene):
    """Small vertical bob so the frame never reads as a still."""
    start, end = scene.frame_start, scene.frame_end
    base_z = hero.location.z
    hero.keyframe_insert("location", frame=start)
    hero.location.z = base_z + 0.08
    hero.keyframe_insert("location", frame=int(start + (end - start) * 0.5))
    hero.location.z = base_z
    hero.keyframe_insert("location", frame=end)


# ── render configuration ─────────────────────────────────────────────────────

def configure(scene, args):
    width, height = args.width - (args.width % 2), args.height - (args.height % 2)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = bool(args.samples >= 16)

    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100

    scene.render.fps = args.fps
    scene.render.fps_base = 1.0
    scene.frame_start = 1
    scene.frame_end = max(1, int(round(args.fps * args.seconds)))

    try:
        scene.view_settings.view_transform = "AgX"
    except TypeError:  # Blender 3.x
        scene.view_settings.view_transform = "Filmic"

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    scene.render.filepath = args.out

    if args.preview:
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
    else:
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
        scene.render.ffmpeg.audio_codec = "NONE"
    return width, height


def write_manifest(args, width, height, scene):
    manifest = {
        "subject": args.subject,
        "look": args.look,
        "frames": scene.frame_end - scene.frame_start + 1,
        "fps": scene.render.fps,
        "seconds": round((scene.frame_end - scene.frame_start + 1) / scene.render.fps, 3),
        "resolution": [width, height],
        "engine": scene.render.engine,
        "samples": scene.cycles.samples,
        "preview": bool(args.preview),
        "output": os.path.abspath(args.out),
    }
    path = os.path.splitext(os.path.abspath(args.out))[0] + ".manifest.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest, path


# ── entry point ──────────────────────────────────────────────────────────────

def parse_args(argv):
    parser = argparse.ArgumentParser(description="Headless Blender turntable")
    parser.add_argument("--subject", default="monkey",
                        choices=["monkey", "cube", "sphere", "torus", "text"])
    parser.add_argument("--look", default="studio",
                        choices=["studio", "neon", "editorial", "tech"])
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--out", default=None)
    # Ignore anything Blender itself put on the command line.
    args = parser.parse_args(argv)
    return args


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parse_args(argv)

    if args.width is None:
        args.width = 640 if args.preview else 1920
    if args.height is None:
        args.height = 360 if args.preview else 1080
    if args.samples is None:
        args.samples = 8 if args.preview else 64
    if args.out is None:
        ext = "png" if args.preview else "mp4"
        args.out = os.path.join("render", f"{args.subject}_{args.look}.{ext}")

    random.seed(7)

    scene = reset_scene()
    add_world(scene, args.look)

    aim_target = bpy.data.objects.new("AimTarget", None)
    scene.collection.objects.link(aim_target)
    aim_target.location = (0, 0, 0)

    hero = add_hero(scene, args.subject, args.look)
    add_ground(scene, args.look)
    add_lights(scene, args.look, aim_target)

    width, height = configure(scene, args)
    add_camera(scene, aim_target, args.seconds)
    add_motion(hero, args.seconds, scene)

    if args.frames:
        scene.frame_end = scene.frame_start + max(1, args.frames) - 1

    manifest, manifest_path = write_manifest(args, width, height, scene)

    if args.preview:
        scene.frame_set(scene.frame_start + (scene.frame_end - scene.frame_start) // 2)
        bpy.ops.render.render(write_still=True)
    else:
        bpy.ops.render.render(animation=True)

    print("MANIFEST " + manifest_path)
    print("DONE " + json.dumps(manifest))


if __name__ == "__main__":
    main()
