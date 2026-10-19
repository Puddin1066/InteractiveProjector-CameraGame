"""Look and sound shared by the Halloween games: team colors, text, audio."""
from typing import Optional, Tuple

import pygame

from . import config
from .audio_manager_thread import AudioManager
from .teams import LEFT, RIGHT

SIDES = {
    LEFT: {"name": "Pumpkin", "color": (255, 140, 30)},
    RIGHT: {"name": "Slime", "color": (150, 255, 90)},
}
GHOST_WHITE = (240, 232, 210)
SHADOW = (20, 8, 30)


def draw_text(surface: pygame.Surface, text: str, font: pygame.font.Font,
              color: Tuple[int, int, int], center: Tuple[float, float], alpha: int = 255) -> None:
    """Text with a drop shadow, readable over the busy backdrop."""
    for offset, shade in ((4, SHADOW), (0, color)):
        rendered = font.render(text, True, shade)
        if alpha < 255:
            rendered.set_alpha(alpha)
        surface.blit(rendered, rendered.get_rect(center=(center[0] + offset, center[1] + offset)))


def start_audio(game_state) -> Optional[AudioManager]:
    try:
        audio = AudioManager(game_state, config.BASE_DIR)
        audio.start()
        return audio
    except Exception as audio_error:
        print(f"Audio unavailable: {audio_error}")
        return None
