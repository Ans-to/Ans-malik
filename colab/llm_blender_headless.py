"""
Headless bridge for saofund/LLM-Blender-Agent on Google Colab.

The upstream repo drives Blender over a TCP socket on :9876 into an add-on that only exists inside
the Blender *GUI*. Colab has no display, so that path cannot work: there is no N-panel to press
"Start MCP Server", and the add-on marshals every command onto the main thread through
`bpy.app.timers`, which never ticks without Blender's event loop.

This module keeps the parts that are actually the project — the agent loop in `src/agent/agent.py`,
the provider abstraction, the Gradio UI — and swaps only the transport: `send_command()` is answered
by an in-process dispatcher that speaks the same JSON envelopes the add-on speaks.

    # in Colab, after the bpy cell of blender_on_colab.ipynb
    !git clone https://github.com/saofund/LLM-Blender-Agent.git /content/llmba
    %cd /content/llmba
    !pip -q install "anthropic>=0.40" tenacity gradio
    import sys; sys.path.insert(0, "/content/Ans-malik/colab")
    import llm_blender_headless as bridge
    client = bridge.install()            # also patches the import the Gradio UI uses
    client.get_scene_info()["result"]

Then put a key in `config.json` and run `app.py` with share=True.

Status: written against commit bcbb686 (2025-03-27). The command handlers mirror `addon.py`'s
handlers line for line — same parameter names, same result keys — but they have only been exercised
against a mock, never a live Blender. Verify with `client.get_scene_info()` before trusting a chat.

Two handlers are deliberately disabled here:
  * `execute_code`  - arbitrary bpy/python execution. Upstream comments it out of the tool list for
                      the same reason. Running a language model's generated code is not something a
                      "make me a red cube" request should be able to reach.
  * `generate_3d_model` - needs a separate GPU box serving Hunyuan3D-2 with 46-115 GB of weights.
"""

from __future__ import annotations

import base64
import os
import tempfile
import traceback

__all__ = ["dispatch", "install", "HANDLERS"]


# --------------------------------------------------------------------------- helpers

def _bbox(obj):
    """World-space axis aligned bounding box, as addon.py's _get_aabb returns it."""
    import mathutils

    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    lo = mathutils.Vector(map(min, zip(*corners)))
    hi = mathutils.Vector(map(max, zip(*corners)))
    return [list(lo), list(hi)]


def _object_summary(obj):
    return {
        "name": obj.name,
        "type": obj.type,
        "location": [obj.location.x, obj.location.y, obj.location.z],
        "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
        "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
    }


# --------------------------------------------------------------------------- handlers

def get_scene_info():
    import bpy

    scene = bpy.context.scene
    info = {
        "name": scene.name,
        "object_count": len(scene.objects),
        "objects": [],
        "materials_count": len(bpy.data.materials),
    }
    for i, obj in enumerate(scene.objects):
        if i >= 10:                      # upstream caps at 10 to keep the token count down
            break
        info["objects"].append({
            "name": obj.name,
            "type": obj.type,
            "location": [round(float(obj.location.x), 2),
                         round(float(obj.location.y), 2),
                         round(float(obj.location.z), 2)],
        })
    return info


def create_object(type="CUBE", name=None, location=(0, 0, 0), rotation=(0, 0, 0),
                  scale=(1, 1, 1), align="WORLD", major_segments=48, minor_segments=12,
                  mode="MAJOR_MINOR", major_radius=1.0, minor_radius=0.25,
                  abso_major_rad=1.25, abso_minor_rad=0.75, generate_uvs=True):
    import bpy

    kind = str(type).upper()
    common = dict(location=location, rotation=rotation)

    if kind == "CUBE":
        bpy.ops.mesh.primitive_cube_add(scale=scale, **common)
    elif kind == "SPHERE":
        bpy.ops.mesh.primitive_uv_sphere_add(scale=scale, **common)
    elif kind == "CYLINDER":
        bpy.ops.mesh.primitive_cylinder_add(scale=scale, **common)
    elif kind == "PLANE":
        bpy.ops.mesh.primitive_plane_add(scale=scale, **common)
    elif kind == "CONE":
        bpy.ops.mesh.primitive_cone_add(scale=scale, **common)
    elif kind == "TORUS":
        bpy.ops.mesh.primitive_torus_add(
            location=location, rotation=rotation,
            major_segments=major_segments, minor_segments=minor_segments,
            mode=mode, major_radius=major_radius, minor_radius=minor_radius,
            abso_major_rad=abso_major_rad, abso_minor_rad=abso_minor_rad,
            generate_uvs=generate_uvs,
        )
    elif kind == "EMPTY":
        bpy.ops.object.empty_add(location=location, rotation=rotation)
    elif kind == "CAMERA":
        bpy.ops.object.camera_add(location=location, rotation=rotation)
    elif kind == "LIGHT":
        bpy.ops.object.light_add(location=location, rotation=rotation)
    else:
        raise ValueError(f"Unsupported object type: {type}")

    obj = (getattr(getattr(bpy.context, "view_layer", None), "objects", None)
           and getattr(bpy.context.view_layer.objects, "active", None)) \
        or getattr(bpy.context, "object", None)
    if obj is None:
        raise RuntimeError("Blender created nothing - no active object in the view layer")
    if name:
        obj.name = name
    if kind not in ("TORUS", "EMPTY", "CAMERA", "LIGHT"):
        obj.scale = scale

    result = _object_summary(obj)
    if obj.type == "MESH":
        result["world_bounding_box"] = _bbox(obj)
    return result


def modify_object(name, location=None, rotation=None, scale=None, visible=None):
    import bpy

    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")
    if location is not None:
        obj.location = location
    if rotation is not None:
        obj.rotation_euler = rotation
    if scale is not None:
        obj.scale = scale
    if visible is not None:
        obj.hide_viewport = not visible
        obj.hide_render = not visible

    result = _object_summary(obj)
    result["visible"] = bool(visible) if visible is not None else True
    if obj.type == "MESH":
        result["world_bounding_box"] = _bbox(obj)
    return result


def delete_object(name):
    import bpy

    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")
    gone = obj.name
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"deleted": gone}


def get_object_info(name):
    import bpy

    obj = bpy.data.objects.get(name)
    if not obj:
        raise ValueError(f"Object not found: {name}")

    info = _object_summary(obj)
    info["materials"] = [s.material.name for s in obj.material_slots if s.material]
    if obj.type == "MESH" and obj.data:
        info["world_bounding_box"] = _bbox(obj)
        info["mesh"] = {
            "vertices": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "polygons": len(obj.data.polygons),
        }
    return info


def set_material(object_name, material_name=None, create_if_missing=True, color=None):
    """create_if_missing is accepted for signature compatibility; a material is always created
    when absent, because the agent cannot do anything useful with a failure here."""
    import bpy

    obj = bpy.data.objects.get(object_name)
    if not obj:
        raise ValueError(f"Object not found: {object_name}")

    mat = bpy.data.materials.get(material_name) if material_name else None
    if mat is None:
        mat = bpy.data.materials.new(name=material_name or f"{object_name}_mat")

    mat.use_nodes = True
    nt = mat.node_tree
    principled = nt.nodes.get("Principled BSDF")
    if principled is None:
        principled = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(principled.outputs[0], out.inputs[0])

    if color and len(color) >= 3:
        rgba = (color[0], color[1], color[2], color[3] if len(color) > 3 else 1.0)
        principled.inputs["Base Color"].default_value = rgba
        mat.diffuse_color = rgba

    # "set material" should be visible immediately. Appending would leave the old material in slot 0
    # still driving the surface, so an existing slot is replaced and only an empty one is appended.
    if getattr(obj, "data", None) is not None and hasattr(obj.data, "materials"):
        if obj.data.materials:
            if obj.data.materials[0] is not mat:
                obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

    return {"object": obj.name, "material": mat.name, "color": list(color) if color else None}


def render_scene(output_path=None, resolution_x=None, resolution_y=None, return_image=False):
    import bpy

    scene = bpy.context.scene
    if resolution_x is not None:
        scene.render.resolution_x = resolution_x
    if resolution_y is not None:
        scene.render.resolution_y = resolution_y

    temp_path = None
    if return_image or not output_path:
        fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)

    path = output_path or temp_path
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

    result = {
        "rendered": True,
        "output_path": output_path or "[temp file]",
        "resolution": [scene.render.resolution_x, scene.render.resolution_y],
    }
    if return_image and os.path.exists(path):
        with open(path, "rb") as fh:
            result["image_data"] = base64.b64encode(fh.read()).decode("utf-8")
        if temp_path and not output_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return result


def execute_code(code):
    raise NotImplementedError(
        "execute_code is disabled in the headless bridge on purpose: it runs arbitrary bpy/Python "
        "generated by a model. Use the other handlers, or call bpy yourself in a notebook cell."
    )


def generate_3d_model(*args, **kwargs):
    raise NotImplementedError(
        "generate_3d_model needs a separate Hunyuan3D-2 server (46-115 GB of weights + a GPU). "
        "See hunyuan/api_server.py in the upstream repo, then pass its URL as api_url."
    )


HANDLERS = {
    "get_scene_info": get_scene_info,
    "create_object": create_object,
    "modify_object": modify_object,
    "delete_object": delete_object,
    "get_object_info": get_object_info,
    "set_material": set_material,
    "render_scene": render_scene,
    "execute_code": execute_code,
    "generate_3d_model": generate_3d_model,
}


# --------------------------------------------------------------------------- transport

def dispatch(command):
    """Same contract as the add-on's socket handler: {"type","params"} in, {"status",...} out."""
    cmd_type = (command or {}).get("type")
    params = (command or {}).get("params") or {}
    handler = HANDLERS.get(cmd_type)
    if handler is None:
        return {"status": "error",
                "message": f"Unknown command type: {cmd_type}. Known: {sorted(HANDLERS)}"}
    try:
        return {"status": "success", "result": handler(**params)}
    except Exception as exc:                     # noqa: BLE001 - the agent needs the message back
        traceback.print_exc()
        return {"status": "error", "message": str(exc)}


def _load_client_class():
    """Get BlenderClient without dragging in the whole provider registry.

    `src/blender/__init__.py` imports `src.llm`, which eagerly imports every vendor SDK (zhipuai,
    volcengine, ...). Importing the client module straight off disk keeps the bridge usable with only
    the provider you actually picked installed.
    """
    try:
        from src.blender.client import BlenderClient          # normal path, in the repo checkout
        return BlenderClient
    except ImportError:
        import importlib.util
        import sys
        from pathlib import Path

        seen = [Path("src/blender/client.py")]
        seen += [Path(p) / "src/blender/client.py" for p in sys.path if p]
        path = next((p for p in seen if p.is_file()), None)
        if path is None:
            raise RuntimeError(
                "run this with the working directory set to the LLM-Blender-Agent checkout "
                "(src/blender/client.py was not found)"
            )
        spec = importlib.util.spec_from_file_location("_llmba_client", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.BlenderClient


def install(verbose=True):
    """Return a BlenderClient lookalike that answers locally, and patch the class the UI imports."""
    BlenderClient = _load_client_class()

    class InProcessClient(BlenderClient):
        def __init__(self, *args, **kwargs):
            self.host = "in-process"
            self.port = 0
            self.sock = None
            self.is_connected = True

        def close(self):
            self.is_connected = False

        def send_command(self, command_type, params=None):
            return dispatch({"type": command_type, "params": params or {}})

    # app.py / ui/utils/blender_utils.py do `from src.blender import BlenderClient` *inside* their
    # functions, so rebinding the attribute on the package is enough to redirect the whole UI.
    try:
        import src.blender as pkg
        pkg.BlenderClient = InProcessClient
        patched = True
    except Exception:
        patched = False

    if verbose:
        print("in-process Blender client ready;",
              "UI import patched" if patched else "UI import NOT patched (import src.blender failed)")
    return InProcessClient()


if __name__ == "__main__":
    import json

    print(json.dumps(dispatch({"type": "get_scene_info"}), indent=2)[:1200])
