import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------- Sizes and timing ----------
W, H = 760, 300
INTRO_FRAMES = 72        # pre-rendered part (man, flick, camera move)
SLOWMO_FRAMES = 40       # live part: slow-motion spin
REVEAL_FRAMES = 14       # live part: result reveal
INTRO_END_ANGLE = 14 * math.pi   # coin rotation at the end of the intro

COIN_CX, COIN_CY, COIN_R = W // 2, 112, 76   # overhead coin
WIDE_COIN_R = 10                              # coin size in the wide shot
T_RELEASE = 0.26    # moment the coin leaves his fingers (0 to 1)
T_CAMERA = 0.62     # moment the camera starts moving overhead

# ---------- Colours ----------
GOLD = (212, 175, 55)
GOLD_LIGHT = (245, 215, 110)
GOLD_DARK = (140, 108, 20)
SKIN = (176, 138, 112)
SKIN_SHADE = (124, 96, 80)
HAIR = (24, 20, 20)
JACKET = (38, 42, 58)
SHIRT = (205, 205, 212)
TROUSERS = (26, 28, 38)
SHOES = (14, 14, 18)

_cache = {}
_faces = {}


# ---------- Small helpers ----------
def _lerp(a, b, t):
    return a + (b - a) * t


def _smooth(x):
    """Ease in/out: 0 to 1 with soft start and end."""
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)      # built-in font (Pillow 10.1+)
    except TypeError:
        return ImageFont.load_default()


def _radial(inner, outer):
    """Spotlight look: bright centre fading to dark edges."""
    mask = Image.radial_gradient("L").resize((W, H), Image.Resampling.BICUBIC)
    return Image.composite(Image.new("RGB", (W, H), outer),
                           Image.new("RGB", (W, H), inner), mask)


# ---------- Backgrounds ----------
def wide_background():
    if "wide" not in _cache:
        bg = _radial((58, 50, 36), (6, 6, 8))
        pool = Image.new("L", (W, H), 0)
        ImageDraw.Draw(pool).ellipse([W//2 - 130, 258, W//2 + 130, 286], fill=80)
        bg.paste((100, 84, 50), mask=pool.filter(ImageFilter.GaussianBlur(8)))
        shadow = Image.new("L", (W, H), 0)
        ImageDraw.Draw(shadow).ellipse([W//2 - 60, 262, W//2 + 60, 280], fill=170)
        bg.paste((0, 0, 0), mask=shadow.filter(ImageFilter.GaussianBlur(6)))
        _cache["wide"] = bg
    return _cache["wide"].copy()


def overhead_background():
    if "over" not in _cache:
        bg = _radial((44, 38, 28), (5, 5, 7))
        d = ImageDraw.Draw(bg)
        for rr, col in ((110, (58, 50, 34)), (160, (40, 35, 25))):
            d.ellipse([COIN_CX - rr, COIN_CY - rr, COIN_CX + rr, COIN_CY + rr],
                      outline=col, width=2)
        # The man seen from above (shoulders + head), bottom-left corner
        d.ellipse([56, 246, 144, 272], fill=JACKET)
        d.ellipse([84, 240, 116, 274], fill=HAIR)
        _cache["over"] = bg
    return _cache["over"].copy()


# ---------- The coin ----------
def _face(r, side):
    """One coin face (cached). Drawn 4x larger, then shrunk for smooth edges."""
    key = (r, side)
    if key in _faces:
        return _faces[key]
    S = 4
    size = 2 * r * S
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([0, 0, size - 1, size - 1], fill=GOLD_DARK)
    m = int(size * 0.04)
    d.ellipse([m, m, size - 1 - m, size - 1 - m], fill=GOLD)
    m2 = int(size * 0.13)
    d.ellipse([m2, m2, size - 1 - m2, size - 1 - m2], outline=GOLD_LIGHT,
              width=max(1, int(size * 0.025)))
    letter = "H" if side == "HEADS" else "T"
    d.text((size / 2, size / 2), letter, font=_font(int(size * 0.42)),
           fill=GOLD_DARK, anchor="mm")
    im = im.resize((2 * r, 2 * r), Image.Resampling.LANCZOS)
    _faces[key] = im
    return im


def draw_coin(img, cx, cy, r, angle, blur=0.0):
    """Draw the coin at a rotation angle. Squashing its height while the
    face flips between H and T is what makes it look like it is spinning."""
    r = max(4, int(round(r)))
    if blur > 0.02:
        samples = [(-blur, 0.35), (blur, 0.35), (0.0, 1.0)]   # motion blur
    else:
        samples = [(0.0, 1.0)]
    for d_ang, opacity in samples:
        a = angle + d_ang
        c = math.cos(a)
        side = "HEADS" if c >= 0 else "TAILS"
        h = max(3, int(2 * r * abs(c)))
        coin = _face(r, side).resize((2 * r, h), Image.Resampling.BILINEAR)
        if opacity < 1:
            coin.putalpha(coin.getchannel("A").point(lambda v, o=opacity: int(v * o)))
        img.paste(coin, (int(cx - r), int(cy - h / 2)), coin)


def draw_shadow(img, cx, cy, r, strength=1.0):
    if strength <= 0.02:
        return
    r = int(round(r))          # Pillow needs whole numbers for sizes
    pad = 30
    size = 2 * r + 2 * pad
    sh = Image.new("L", (size, size), 0)
    ImageDraw.Draw(sh).ellipse([pad, pad, pad + 2 * r, pad + 2 * r],
                               fill=int(130 * strength))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    img.paste((0, 0, 0), (int(cx - r - pad + 16), int(cy - r - pad + 22)), sh)


# ---------- The man ----------
def _arm(t):
    """How far the right arm is raised (0 = down, 1 = flick, >1 = follow-through)."""
    if t < 0.12:
        return 0.0
    if t < T_RELEASE:
        return _smooth((t - 0.12) / (T_RELEASE - 0.12))
    if t < 0.40:
        return 1 + 0.25 * _smooth((t - T_RELEASE) / (0.40 - T_RELEASE))
    return 1.25 - 0.45 * _smooth((t - 0.40) / 0.22)


def _hand(a):
    return W // 2 + 30 + 16 * a, 150 - 56 * a


def _man_scene(arm, tilt):
    """Wide shot: the man standing in the dark studio (no coin drawn here)."""
    S = 2   # draw at double size, shrink at the end = smooth edges
    layer = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = W // 2

    def P(x, y):
        return (x * S, y * S)

    # Legs and shoes (feet stay planted on the floor)
    d.rectangle([*P(cx - 27, 176), *P(cx - 3, 262)], fill=TROUSERS)
    d.rectangle([*P(cx + 3, 176), *P(cx + 27, 262)], fill=TROUSERS)
    d.ellipse([*P(cx - 33, 258), *P(cx - 1, 274)], fill=SHOES)
    d.ellipse([*P(cx + 1, 258), *P(cx + 33, 274)], fill=SHOES)
    # Torso, shirt collar, belt, neck
    d.polygon([P(cx - 38, 100), P(cx + 38, 100), P(cx + 29, 182), P(cx - 29, 182)],
              fill=JACKET)
    d.polygon([P(cx - 9, 100), P(cx + 9, 100), P(cx, 124)], fill=SHIRT)
    d.rectangle([*P(cx - 29, 176), *P(cx + 29, 184)], fill=(20, 20, 24))
    d.rectangle([*P(cx - 8, 84), *P(cx + 8, 102)], fill=SKIN_SHADE)
    # Left arm hangs down
    d.line([P(cx - 36, 106), P(cx - 44, 146), P(cx - 42, 184)],
           fill=JACKET, width=14 * S, joint="curve")
    d.ellipse([*P(cx - 49, 180), *P(cx - 35, 194)], fill=SKIN_SHADE)
    # Right arm (the flicking arm)
    hand = _hand(arm)
    elbow = (cx + 52, 148 - 10 * arm)
    d.line([P(cx + 36, 106), P(*elbow), P(*hand)],
           fill=JACKET, width=13 * S, joint="curve")
    d.ellipse([*P(hand[0] - 7, hand[1] - 7), *P(hand[0] + 7, hand[1] + 7)], fill=SKIN)
    # Head: tilts back as `tilt` goes 0 to 1; eyes and pupils look UP
    hx, hy = cx, 70 - 3 * tilt
    d.ellipse([*P(hx - 17, hy - 19), *P(hx + 17, hy + 19)], fill=SKIN)
    d.chord([*P(hx - 18, hy - 21), *P(hx + 18, hy + 17)],
            190 + 12 * tilt, 350 - 12 * tilt, fill=HAIR)
    ey = hy - 1 - 6 * tilt
    for ex in (hx - 7, hx + 7):
        d.ellipse([*P(ex - 4, ey - 2.5), *P(ex + 4, ey + 2.5)], fill=(235, 235, 235))
        d.ellipse([*P(ex - 1.8, ey - 1.8 - 0.8 * tilt), *P(ex + 1.8, ey + 1.8 - 0.8 * tilt)],
                  fill=(25, 20, 20))
    my = hy + 9 - 8 * tilt
    d.line([P(hx - 5, my), P(hx + 5, my)], fill=(95, 55, 48), width=2 * S)

    layer = layer.resize((W, H), Image.Resampling.LANCZOS)
    bg = wide_background()
    bg.paste(layer, (0, 0), layer)
    return bg


# ---------- Where the coin is in the wide shot ----------
def _coin_state(t):
    if t < T_RELEASE:                       # still in his fingers
        hx, hy = _hand(_arm(t))
        return hx, hy - 9, 0.25, True
    f = (t - T_RELEASE) / (1 - T_RELEASE)   # 0 to 1 during flight
    x0, y0 = _hand(1.0)
    y0 -= 9
    ph = min(f / 0.45, 1.0)
    x = x0 - 34 * _smooth(ph)               # drifts above his head
    y = y0 - (y0 - 24) * math.sin(ph * math.pi / 2)
    if f > 0.45:
        y += 10 * (f - 0.45) / 0.55         # slowly sinking at the top
    angle = 0.25 + (INTRO_END_ANGLE - 0.25) * f
    return x, y, angle, False


# ---------- Phase A: frames saved by the generator ----------
def render_intro_frame(i, n=INTRO_FRAMES):
    t = i / (n - 1)
    arm = _arm(t)
    tilt = _smooth((t - 0.24) / 0.20)       # head tilts up after the flick
    wide = _man_scene(arm, tilt)
    x, y, angle, in_hand = _coin_state(t)

    if t < T_CAMERA:                        # Scenes 1-3: wide shot
        draw_coin(wide, x, y, WIDE_COIN_R, angle, blur=0.0 if in_hand else 0.22)
        return wide

    # Scene 4: camera glides toward the coin and crossfades to overhead
    e = _smooth((t - T_CAMERA) / (1 - T_CAMERA))
    z = 1 + 2.2 * e
    mx = W / 2 + (x - W / 2) * e
    my = H / 2 + (y - H / 2) * e
    bw, bh = W / z, H / z
    box = (mx - bw / 2, my - bh / 2, mx + bw / 2, my + bh / 2)
    cam = wide.transform((W, H), Image.Transform.EXTENT, box, Image.Resampling.BICUBIC)
    frame = Image.blend(cam, overhead_background(), e)
    sx = (x - box[0]) / bw * W
    sy = (y - box[1]) / bh * H + (COIN_CY - H / 2) * e
    r = WIDE_COIN_R * z * (1 - e) + COIN_R * e
    draw_shadow(frame, sx, sy, r, strength=e)
    draw_coin(frame, sx, sy, r, angle, blur=0.22 + 0.2 * e)
    return frame


# ---------- Phase B: drawn live, using the result Python already chose ----------
def _final_angle(result):
    # cos(angle) >= 0 shows HEADS, otherwise TAILS
    return INTRO_END_ANGLE + (4 * math.pi if result == "HEADS" else 5 * math.pi)


def render_slowmo_frame(k, result):
    u = (k + 1) / SLOWMO_FRAMES
    ease = 1 - (1 - u) ** 3                 # fast start, gentle stop
    a0 = INTRO_END_ANGLE
    angle = a0 + (_final_angle(result) - a0) * ease
    img = overhead_background()
    draw_shadow(img, COIN_CX, COIN_CY, COIN_R)
    draw_coin(img, COIN_CX, COIN_CY, COIN_R, angle, blur=0.5 * (1 - u) ** 2)
    return img


def render_reveal_frame(k, result):
    u = (k + 1) / REVEAL_FRAMES
    img = overhead_background()
    draw_shadow(img, COIN_CX, COIN_CY, COIN_R)
    draw_coin(img, COIN_CX, COIN_CY, COIN_R, _final_angle(result))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    rr = COIN_R + 10 + 60 * u               # golden ring that expands and fades
    d.ellipse([COIN_CX - rr, COIN_CY - rr, COIN_CX + rr, COIN_CY + rr],
              outline=(*GOLD_LIGHT, int(200 * (1 - u))), width=3)
    d.text((W // 2, 246), result, font=_font(54),
           fill=(*GOLD, int(255 * _smooth(u * 1.6))), anchor="mm")
    glow = overlay.filter(ImageFilter.GaussianBlur(8))
    out = Image.alpha_composite(img.convert("RGBA"), glow)
    out = Image.alpha_composite(out, overlay)
    return out.convert("RGB")


def render_final_frame(result):
    return render_reveal_frame(REVEAL_FRAMES - 1, result)