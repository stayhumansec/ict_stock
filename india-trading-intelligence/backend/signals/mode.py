"""Methodology mode selection.

Release 1 is SMC-only. ICT and HYBRID exist as named enum members so the
rest of the codebase (signal records, config, future confluence scoring)
never needs to change shape when those modes are actually implemented —
but nothing in this release computes an ICT or HYBRID signal.
"""

from __future__ import annotations

from enum import Enum


class MethodologyMode(str, Enum):
    SMC = "SMC"
    ICT = "ICT"
    HYBRID = "HYBRID"


# The only mode active in Release 1. Any code path that would produce an
# ICT or HYBRID signal must refuse to run rather than silently falling
# back to SMC or fabricating output.
ACTIVE_MODE = MethodologyMode.SMC

ENABLED_MODES = {MethodologyMode.SMC}


def is_mode_enabled(mode: MethodologyMode) -> bool:
    return mode in ENABLED_MODES
