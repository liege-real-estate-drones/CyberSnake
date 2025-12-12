# --- ChatGPT patch set: Game Options + UI polish (2025-08-07) ---

from utils import load_game_options
_cache = None
def get_opts(refresh=False):
    global _cache
    if refresh or _cache is None:
        _cache = load_game_options()
    return _cache
