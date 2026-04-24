"""Vision component: capture the screen and ship it to a VLM.

Surface: `grab()` returns a Screenshot. `see()` runs a one-shot Q&A turn.
Voice-loop integration lives in `sabrina.voice_loop`, not here.
"""

from sabrina.vision.capture import Screenshot, downscale_size, grab
from sabrina.vision.see import see

__all__ = ["Screenshot", "downscale_size", "grab", "see"]
