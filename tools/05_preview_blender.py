"""
05 — Vista previa 3D: la textura aplicada a la malla canónica, en tres vistas.

Uso (desde la raíz del repo, después de 04_rasterize.py):
    blender --background --factory-startup --python tools/05_preview_blender.py
    blender ... --python tools/05_preview_blender.py -- calavera_alt   # otra textura

Salida: docs/screenshots/preview_<textura>_{frente,3q_izq,3q_der}.png

El material no tiene iluminación (emisión pura), igual que el shader del filtro, así que los
colores se ven como en el celular. Los huecos de ojos y boca dejan ver un fondo gris.
"""
import math
import os
import sys

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJ_PATH = os.path.join(ROOT, "assets", "face", "canonical_face_model.obj")
OUT_DIR = os.path.join(ROOT, "docs", "screenshots")
RES = 1024
BACKGROUND = (0.18, 0.16, 0.15)
# Vistas: nombre -> giro de la cámara alrededor de la cara (grados; + = lado izquierdo
# de la persona, que en Blender queda en +X).
VIEWS = {"frente": 0, "3q_izq": 38, "3q_der": -38}


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return argv[0] if argv else "calavera"


def setup_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16
        scene.cycles.use_denoising = False
    except Exception:  # noqa: BLE001 — sin Cycles se usa EEVEE
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = scene.render.resolution_y = RES
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"   # colores de la textura sin tone mapping
    world = bpy.data.worlds.new("fondo")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (*BACKGROUND, 1)
    scene.world = world
    return scene


def import_face(texture_path):
    bpy.ops.wm.obj_import(filepath=OBJ_PATH)
    obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    for poly in obj.data.polygons:
        poly.use_smooth = True

    mat = bpy.data.materials.new("mascara")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(texture_path)
    tex.image.alpha_mode = "STRAIGHT"
    tex.interpolation = "Cubic"
    emit = nt.nodes.new("ShaderNodeEmission")
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def add_camera(scene, target):
    cam = bpy.data.objects.new("camara", bpy.data.cameras.new("camara"))
    cam.data.lens = 85
    scene.collection.objects.link(cam)
    scene.camera = cam
    track = cam.constraints.new("TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    return cam


def main():
    name = args()
    texture = os.path.join(ROOT, "assets", "mask", f"{name}.png")
    if not os.path.exists(texture):
        raise SystemExit(f"[05] no existe {texture}; corre primero tools/04_rasterize.py")
    scene = setup_scene()
    face = import_face(texture)

    # Centro de la cara (la cara mira hacia -Y en Blender, con Z hacia arriba).
    center = bpy.data.objects.new("centro", None)
    scene.collection.objects.link(center)
    center.location = (0, 0, -0.5)
    cam = add_camera(scene, center)
    dist = 62

    os.makedirs(OUT_DIR, exist_ok=True)
    for view, deg in VIEWS.items():
        a = math.radians(deg)
        cam.location = (dist * math.sin(a), -dist * math.cos(a), 1.0)
        scene.render.filepath = os.path.join(OUT_DIR, f"preview_{name}_{view}.png")
        bpy.ops.render.render(write_still=True)
        print(f"[05] {scene.render.filepath}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as err:
        print(f"[05] ERROR: {err}")
        sys.exit(1)
