"""Screenshot capture using mss.

Why mss: ~15ms per grab on a 4K primary, no GPU dependency, MIT-licensed,
pure-Python wheels on every platform we care about. Beats PIL.ImageGrab
(slower, primary-monitor-only) and dxcam (blazing fast but drags in a
DirectX toolchain we don't need).

The grab path:
  1. mss.sct().grab(monitor) -> BGRA numpy-adjacent buffer
  2. PIL.Image.frombytes(...) -> RGB image
  3. optional resize so the longest edge <= max_edge_px
  4. encode to PNG bytes
  5. return a Screenshot dataclass

PNG over JPEG because:
  - text on screen (code, chat, errors) stays crisp
  - Claude's vision endpoint accepts both but prefers PNG for UIs
  - PNG is lossless so downscaling is the only quality knob we control
"""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class Screenshot:
    data: bytes
    media_type: Literal["image/png"] = "image/png"
    width: int = 0
    height: int = 0
    source_width: int = 0
    source_height: int = 0
    capture_duration_s: float = 0.0


def grab(
    monitor: int = 1,
    *,
    max_edge_px: int = 1568,
) -> Screenshot:
    """Capture `monitor` and return an encoded Screenshot.

    Args:
        monitor: mss monitor index. 0 = virtual union of all monitors,
                 1 = primary, 2+ = additional displays. Out-of-range falls
                 back to monitor 1.
        max_edge_px: longest-edge pixel cap for downscaling. 0 disables.
                     Claude's vision sweet spot is ~1500-1600 px — larger
                     wastes tokens without helping recognition.
    """
    import mss  # local import keeps non-vision commands light
    from PIL import Image

    start = time.monotonic()
    with mss.mss() as sct:
        monitors = sct.monitors
        # monitors[0] is the virtual screen; monitors[1..] are the physical ones.
        idx = monitor if 0 <= monitor < len(monitors) else 1
        shot = sct.grab(monitors[idx])
        src_w, src_h = shot.width, shot.height
        # mss gives BGRA bytes. PIL wants RGB (or RGBA); easiest route is
        # frombytes with mode "RGB" and 'raw', 'BGRX', 0, 1 — but that's
        # fiddly. Using bgra -> RGBA -> RGB conversion via PIL is clean.
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    target_w, target_h = downscale_size(src_w, src_h, max_edge_px)
    if (target_w, target_h) != (src_w, src_h):
        img = img.resize((target_w, target_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return Screenshot(
        data=buf.getvalue(),
        media_type="image/png",
        width=target_w,
        height=target_h,
        source_width=src_w,
        source_height=src_h,
        capture_duration_s=time.monotonic() - start,
    )


def downscale_size(width: int, height: int, max_edge_px: int) -> tuple[int, int]:
    """Return (w, h) scaled so max(w, h) <= max_edge_px, preserving aspect.

    If the image is already within budget or max_edge_px <= 0, returns the
    input unchanged. Rounds to the nearest integer so we never end up with
    zero-sized dimensions on tiny inputs.
    """
    if max_edge_px <= 0 or width <= 0 or height <= 0:
        return width, height
    longest = max(width, height)
    if longest <= max_edge_px:
        return width, height
    scale = max_edge_px / longest
    return max(1, round(width * scale)), max(1, round(height * scale))
