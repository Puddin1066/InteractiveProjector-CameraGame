# Halloween visual assets

The polished Haunted Wall theme uses a small set of third-party assets that are
**CC0 / public domain**. They are downloaded locally by
`prepare_halloween_assets.py`; the repository does not depend on paid or
attribution-restricted artwork.

## Graveyard background layers

**Seamless 2D Graveyard Background** — LarryIRL, OpenGameArt

- Asset page: https://opengameart.org/content/seamless-2d-graveyard-background
- License: CC0 / public domain
- Files used: `Graveyard1.png`, `Graveyard2.png`
- Purpose: parallax tree, ground, mountain and graveyard silhouette layers

## Ghost animation

**Ghost Sprite** — ChiliGames, OpenGameArt

- Asset page: https://opengameart.org/content/ghost-sprite
- License: CC0
- File used: `enemy-sheet0.png` (downloaded as `ghost_sheet.png`)
- Purpose: animated foreground targets that children can collide with

## Runtime behavior

`python launch_haunted_wall_macos.py` checks whether the visual assets are
present. If they are missing it calls `prepare_halloween_assets.py`. If the
download fails (for example the Mac is offline), Haunted Wall still starts with
the original procedural moon/fog/ghost rendering.

The interaction engine is unchanged by the theme: the iPhone camera provides
person detections, calibration maps them into projector space, and the MoGo 4
renders the composite scene.
