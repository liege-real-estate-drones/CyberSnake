# --- ChatGPT consolidated patch (inputs+safejson+attract+debounce) 2025-08-07 ---

try:
    import pygame
except Exception:
    pygame = None
try:
    import config
except Exception:
    class _Fallback: pass
    config = _Fallback()
    config.BUTTON_PRIMARY_ACTION = 0
    config.BUTTON_SECONDARY_ACTION = 1
    config.BUTTON_TERTIARY_ACTION = 2
    config.BUTTON_PAUSE = 7
    config.JOYSTICK_THRESHOLD = 0.5
    config.NAV_REPEAT_DELAY_MS = 180
def is_confirm_button(button: int) -> bool:
    return button in (getattr(config, "BUTTON_PRIMARY_ACTION", 0), 0, 1)
def is_back_button(button: int) -> bool:
    return button in (getattr(config, "BUTTON_SECONDARY_ACTION", 1), 8)
def is_pause_button(button: int) -> bool:
    return button == getattr(config, "BUTTON_PAUSE", 7)
def axis_to_nav(value: float) -> int:
    thr = getattr(config, "JOYSTICK_THRESHOLD", 0.5)
    if value > thr: return 1
    if value < -thr: return -1
    return 0
