"""
Single source of truth for the 15-second film: timeline, palette, easing, voice-over lines.

Every other module (scene.py, vo.py, score.py, gates.py) imports from here, so the picture, the
sound and the checks cannot drift apart. If a shot moves, it moves everywhere at once.

Timing is on a 120 BPM grid: at 30 fps one beat is exactly 15 frames, so 15.0 s == 30 beats ==
450 frames and every cut lands on a beat boundary.
"""

FPS = 30
DURATION = 15.0
FRAMES = int(FPS * DURATION)          # 450
BEAT = 15                             # frames per beat at 120 BPM

# Render presets. `preview` exists to be looked at cheaply before spending 40 minutes on `final`.
PRESETS = {
    "preview": dict(width=960, height=540, samples=12, motion_blur=False),
    "final":   dict(width=1920, height=1080, samples=16, motion_blur=True),
}

# --------------------------------------------------------------------------- shots
# frame ranges are inclusive; Blender frames are 1-based.
SHOTS = [
    dict(key="A", name="sand",      start=1,   end=90,  camera="CAM_A"),
    dict(key="B", name="die",       start=91,  end=195, camera="CAM_B"),
    dict(key="C", name="switches",  start=196, end=300, camera="CAM_C"),
    dict(key="D", name="virus",     start=301, end=378, camera="CAM_D"),
    dict(key="E", name="lockup",    start=379, end=450, camera="CAM_E"),
]

def shot_at(frame):
    for s in SHOTS:
        if s["start"] <= frame <= s["end"]:
            return s
    return None

# --------------------------------------------------------------------------- voice-over
# "start" is the frame the line begins; lines are generated separately so each one can be placed
# exactly on the beat instead of hoping a single read finishes on time.
VO_LINES = [
    dict(id="l1", start=10,  text="It begins as sand."),
    dict(id="l2", start=97,  text="Then light does the work."),
    dict(id="l3", start=199, text="Twenty-six billion switches."),
    dict(id="l4", start=298, text="Each one smaller than a virus."),
    dict(id="l5", start=384, text="This is silicon."),
]
VO_VOICE = "af_heart"
VO_SPEED = 0.92
VO_SR = 24000

# --------------------------------------------------------------------------- palette
# Given as sRGB hex (what a designer would hand you) and converted to linear for Cycles.
def srgb(hex_str, alpha=1.0):
    h = hex_str.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, alpha)

PALETTE = {
    "ink":    "#0B0A09",   # warm near-black, the base every shot sits on
    "bone":   "#EDE4D6",   # warm off-white, all primary type
    "copper": "#C9723F",   # the single accent; used sparingly so it stays an accent
    "steel":  "#7C878E",   # desaturated cool, secondary surfaces
    "sand":   "#D8C4A2",   # highlight tint for dust and rims
    "deep":   "#171310",   # mid-dark used for gradients behind subjects
}

# --------------------------------------------------------------------------- easing
# Cubic-bezier control points, not invented curves: these are the Material 3 motion tokens.
# Every animation in the film is baked by sampling one of these, frame by frame.
EASING = {
    "standard":    (0.20, 0.00, 0.00, 1.00),
    "decelerate":  (0.00, 0.00, 0.20, 1.00),
    "accelerate":  (0.40, 0.00, 1.00, 1.00),
    "emphasized":  (0.05, 0.70, 0.10, 1.00),
    "linear":      (0.00, 0.00, 1.00, 1.00),
}

# --------------------------------------------------------------------------- copy
TITLE_WORD = "SILICON"
TAGLINE = "EVERY LAYER, PLACED BY LIGHT."

# Text block per shot, as (line, beat_offset_in_frames_since_shot_start, size_frac).
# size_frac is a fraction of the visible frame height at the text plane, so the layout survives
# any lens or resolution change.
TYPE = {
    "A": [("IT BEGINS", 6,  0.115), ("AS SAND.", 14, 0.115)],
    "C": [("TWENTY-SIX", 8, 0.105), ("BILLION", 16, 0.105), ("SWITCHES.", 24, 0.105)],
    "D": [("SMALLER", 6, 0.115), ("THAN A VIRUS.", 15, 0.115)],
}
