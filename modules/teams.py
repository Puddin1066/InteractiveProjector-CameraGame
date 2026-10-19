"""The two teams of a split-wall game: each owns one half of the projection."""
LEFT, RIGHT = "left", "right"


def side_of(x: float, width: float) -> str:
    return LEFT if x < width / 2 else RIGHT
