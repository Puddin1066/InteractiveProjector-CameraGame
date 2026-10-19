# Third-party notices

The MIT license in [LICENSE](LICENSE) covers this project's own code and art.
The pieces below come from other people and keep their own terms.

## Fruit Ninja HTML5 game (bundled, no license)

- What: the browser game engine under `web/spooky_slash`, including its Ucren
  and tween libraries, which Spooky Slash and Midnight Slash reskin and extend.
- Source: the Baidu JS team's Fruit Ninja, <https://github.com/ChineseDron/fruit-ninja>.
- Terms: the upstream repository has **no license**, so its authors keep all
  rights. It is included here for private, non-commercial, educational use and
  is **not** covered by this project's MIT license. Do not reuse it
  commercially. The upstream authors can ask for its removal at any time
  through this repository's issues.

## Raphael and buzz (bundled, MIT)

- Raphael 1.5.2, Copyright (c) 2010 Dmitry Baranovskiy, MIT:
  `web/spooky_slash/scripts/lib/raphael.js`.
- buzz, Copyright (C) 2011 Jay Salvat, MIT: `web/spooky_slash/scripts/lib/buzz.js`.

Their license headers are kept in the files.

## Ultralytics YOLO (dependency, not bundled)

- What: the `ultralytics` Python package and the YOLO11 pose and segmentation
  models (`yolo11n-pose.pt`, `yolo11n-seg.pt`) it downloads on first run.
- Terms: [AGPL-3.0](https://github.com/ultralytics/ultralytics/blob/main/LICENSE),
  or an Ultralytics enterprise license. Installing it is your choice; anyone
  distributing or hosting this project together with Ultralytics must meet the
  AGPL-3.0 terms for that combined work.

## Other models (downloaded on first run, not bundled)

- MediaPipe hand landmarker and selfie segmenter, Google,
  [Apache-2.0](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE).

## Halloween artwork and sounds (CC0)

- Haunted Wall assets: listed with links in [HALLOWEEN_ASSETS.md](HALLOWEEN_ASSETS.md),
  downloaded by `tools/prepare_halloween_assets.py`.
- Midnight Slash music and voices, all CC0, made by
  `tools/make_midnight_slash_sounds.py` and credited in
  `web/midnight_slash/index.html`:
  - "Harpsichord Flurry" by Spring Spring, OpenGameArt.org
  - "Spooky Loop" by wipics, OpenGameArt.org
  - "Witch Cackle" by AntumDeluge, OpenGameArt.org
  - "Ghostly Cackle Laugh 1" by Nocturnal_Vanguard, OpenGameArt.org
  - "Shouts and Applauses of Teens #1" by Denis Chardonnet, BigSoundBank.com

## Generated artwork

The Midnight Slash source paintings in `art/midnight_slash` were made with an
AI image generator for this project and are released with it under the MIT
license.
