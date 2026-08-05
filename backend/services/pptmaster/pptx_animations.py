#!/usr/bin/env python3
"""
PPT Master - PPTX Animation Module

Provides XML generation for slide transition effects and entrance animations.

Supported transition effects:
    - fade: Fade in/out
    - push: Push
    - wipe: Wipe
    - split: Split
    - strips: Strips (diagonal wipe)
    - cover: Cover
    - random: Random

Supported entrance animations (per-element):
    appear, fade, fly, cut, zoom, wipe, split, blinds, checkerboard,
    dissolve, random_bars, peek, wheel, box, circle, diamond, plus,
    strips, wedge, stretch, expand, swivel

Animation modes used by the builder:
    - single effect name (one of the above) — apply to every element
    - 'mixed'  — first element fades, the rest cycle through a curated visible pool
    - 'random' — pick a random effect from the same visible pool per element

Dependencies: None (pure XML generation)
"""

from typing import Optional, Dict, Any


# ============================================================================
# Transition effect definitions
# ============================================================================

TRANSITIONS: Dict[str, Dict[str, Any]] = {
    'fade': {
        'name': 'Fade',
        'element': 'fade',
        'attrs': {},
    },
    'push': {
        'name': 'Push',
        'element': 'push',
        'attrs': {'dir': 'r'},  # Push from right
    },
    'wipe': {
        'name': 'Wipe',
        'element': 'wipe',
        'attrs': {'dir': 'r'},  # Wipe from right
    },
    'split': {
        'name': 'Split',
        'element': 'split',
        'attrs': {'orient': 'horz', 'dir': 'out'},
    },
    'strips': {
        'name': 'Strips',
        'element': 'strips',
        'attrs': {'dir': 'rd'},  # Diagonal wipe from bottom-right
    },
    'cover': {
        'name': 'Cover',
        'element': 'cover',
        'attrs': {'dir': 'r'},
    },
    'random': {
        'name': 'Random',
        'element': 'random',
        'attrs': {},
    },
}

def create_transition_xml(
    effect: str = 'fade',
    duration: float = 0.5,
    advance_after: Optional[float] = None
) -> str:
    """
    Generate a slide transition effect XML fragment

    Args:
        effect: Transition effect name (fade/push/wipe/split/strips/cover/random)
        duration: Transition duration (seconds, precise to milliseconds)
        advance_after: Auto-advance interval (seconds); None means manual advance

    Returns:
        A <p:transition> element string insertable into slide XML
    """
    if effect not in TRANSITIONS:
        effect = 'fade'

    trans_info = TRANSITIONS[effect]
    element_name = trans_info['element']
    attrs = trans_info['attrs']

    # Build dur attribute (milliseconds, precise control via Office 2010 extension)
    dur_ms = int(duration * 1000)
    dur_attr = f' p14:dur="{dur_ms}" xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main"'

    # Build auto-advance attribute
    adv_attr = ''
    if advance_after is not None:
        adv_tm = int(advance_after * 1000)  # Convert to milliseconds
        adv_attr = f' advTm="{adv_tm}"'

    # Build effect element attributes
    effect_attrs = ' '.join(f'{k}="{v}"' for k, v in attrs.items())
    if effect_attrs:
        effect_attrs = ' ' + effect_attrs

    # Generate XML
    return f'''  <p:transition{dur_attr}{adv_attr}>
    <p:{element_name}{effect_attrs}/>
  </p:transition>'''


def get_available_transitions() -> list:
    """Get a list of all available transition effects"""
    return list(TRANSITIONS.keys())


if __name__ == '__main__':
    # Test output
    print("=== Transition Effect XML Example (fade, 500ms) ===")
    print(create_transition_xml('fade', 0.5))
