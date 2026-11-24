import io
import math
import random
import struct
import wave

RATE = 22050     # smaller file than CD quality, still fine for these sounds


def _mix(buf, freq, start, dur, vol, decay):
    """Add a fading sine-wave note into the buffer."""
    s0 = int(start * RATE)
    for n in range(int(dur * RATE)):
        i = s0 + n
        if i >= len(buf):
            break
        t = n / RATE
        buf[i] += vol * math.sin(2 * math.pi * freq * t) * math.exp(-decay * t)


def _click(buf, at):
    _mix(buf, 1800, at, 0.06, 0.5, 70)


def _flick(buf, at):
    start = int(at * RATE)
    burst = int(0.02 * RATE)
    for n in range(burst):                         # finger-snap noise
        if start + n < len(buf):
            buf[start + n] += random.uniform(-0.4, 0.4) * (1 - n / burst)
    _mix(buf, 2600, at, 0.5, 0.4, 9)               # metallic "ting"
    _mix(buf, 3900, at, 0.5, 0.2, 12)
    _mix(buf, 5200, at, 0.3, 0.1, 18)


def _spin(buf, at, dur):
    start = int(at * RATE)
    phase_c = phase_m = 0.0
    for n in range(int(dur * RATE)):
        i = start + n
        if i >= len(buf):
            break
        t = n / RATE
        wobble = 3 + 25 * math.exp(-t / 1.8)       # wobble slows down
        phase_m += 2 * math.pi * wobble / RATE
        phase_c += 2 * math.pi * (1300 + 200 * math.sin(phase_m)) / RATE
        env = (0.5 + 0.5 * math.sin(phase_m)) * 0.18
        fade = min(1.0, (dur - t) / 0.8, t / 0.05)
        buf[i] += math.sin(phase_c) * env * fade


def _land(buf, at):
    _mix(buf, 1318, at, 1.4, 0.30, 3.5)            # three-note chime
    _mix(buf, 1760, at + 0.10, 1.3, 0.25, 3.5)
    _mix(buf, 2637, at + 0.20, 1.2, 0.25, 3.5)


def build_track(release_s, reveal_s, total_s, lead=0.0):
    """One WAV file timed to the animation.
    release_s = when the coin leaves his fingers, reveal_s = when the result
    appears, total_s = animation length, lead = extra silence at the start."""
    buf = [0.0] * int((total_s + lead + 1.5) * RATE)
    _click(buf, lead)
    _flick(buf, lead + release_s)
    _spin(buf, lead + release_s, reveal_s - release_s + 0.2)
    _land(buf, lead + reveal_s)
    data = b"".join(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767))
                    for s in buf)
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(data)
    return out.getvalue()