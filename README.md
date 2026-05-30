# croppy

Crop videos visually. Draw boxes on a frame, hit a button, get one cropped file per box.

croppy exists for the case ffmpeg handles in five command-line flags but no one wants to type by hand: extracting one or more rectangular regions from a video. Drag your clip onto the window, draw the boxes you want on the preview frame, optionally tweak the quality settings, and hit **Process**. croppy spawns one ffmpeg job per box, encodes them in sequence, and shows you a progress panel you can watch and cancel from.

Defaults are picked so most people can ignore the settings panel entirely: H.264 video, even-aligned crop dimensions (libx264 is fussy about odd numbers), audio passthrough, `.mp4` output. The settings panel is there for the times you need something else.

## What you can do

- Open a video by drag-and-drop or via the file picker
- Pick which frame to use as the preview — handy when a clip starts on black
- Draw multiple crop rectangles, resize them with corner/edge handles, drag the body to reposition
- Overlap them freely; each one is an independent output
- Watch each crop encode in real time and cancel any job mid-flight
- Set the output folder, container (`mp4` / `mkv` / `mov`), video codec (`libx264` / `libx265`), CRF, preset, tune, pixel format, audio mode, audio bitrate, and faststart from a collapsible **Encoding settings** panel

## Install

croppy is on its way to **conda-forge**. Once it lands you'll be able to:

```bash
pixi add croppy
# or
conda install -c conda-forge croppy
```

In the meantime, you can run it straight from a checkout — [pixi](https://pixi.sh) handles everything, including bringing in `ffmpeg`:

```bash
git clone https://github.com/roaldarbol/croppy
cd croppy
pixi run croppy
```

## Using it

```bash
croppy                    # opens the landing screen — drop a video or click to browse
croppy path/to/clip.mp4   # opens straight into the editor with that clip loaded
```

Once a video is open:

- **Click-and-drag** on the frame to draw a crop box.
- **Click a box** to select it; its handles appear. Drag the body to move it, drag a handle to resize. The selected box is also highlighted in the sidebar list (and vice-versa).
- **Delete** or **Backspace** removes the selected box.
- **Reload** in the *Preview frame* group re-extracts the preview at a different frame number — useful for finding a representative moment.
- **Process** queues one ffmpeg job per box. The progress dock appears at the bottom of the window with a row per job: progress bar, status, **Cancel** button. **Clear finished** tidies completed rows away when you're done.

Output files land in the folder shown under **Output folder** (the source video's directory by default) and are named `<original_stem>_crop1.<ext>`, `_crop2.<ext>`, and so on.

## Contributing

The codebase is small and meant to stay readable. Layout:

```text
src/croppy/ffmpeg/   # subprocess wrappers around ffmpeg / ffprobe (no Qt here)
src/croppy/gui/      # PySide6 widgets
src/croppy/jobs/     # job queue + per-job QProcess worker
src/croppy/models.py # CropRegion, EncodeSettings — plain dataclasses
```

To set up a working copy:

```bash
pixi run -e dev install-hooks  # one-time: wire lefthook pre-commit hooks
pixi run -e dev test
pixi run -e dev lint
pixi run -e dev format
```

Pre-commit hooks (via [lefthook](https://github.com/evilmartians/lefthook)) run `ruff check --fix` and `ruff format` on staged Python files automatically.

## License

MIT — see [LICENSE](LICENSE).
