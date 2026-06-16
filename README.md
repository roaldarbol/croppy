# croppy

Common lab video chores — cropping, joining, and compressing — in one window, the parts ffmpeg handles in a handful of flags nobody wants to type by hand.

croppy is organized into three tabs that share one **Compression** panel and one progress dock at the bottom you can watch and cancel from:

- **Crop** — draw one or more boxes on a preview frame and get one cropped file per box.
- **Combine** — pick videos, drag them into the order you want, and join them into a single file. Queue as many combine jobs as you like.
- **Compress** — pick any number of videos and re-encode them smaller in one go.

Compression settings are shared across all three tabs: set them once and every operation uses them. By default croppy encodes with **NVENC HEVC on the GPU when it's available** and falls back to CPU **libx265** otherwise, so files shrink without you choosing an encoder — but the panel lets you force GPU or CPU and tune quality.

## What you can do

- **Crop**: open a video by drag-and-drop or the file picker; pick the preview frame (handy when a clip starts on black); draw, resize (corner/edge handles), and reposition multiple boxes; each box is an independent output.
- **Combine**: add videos, drag-reorder them, set the output folder and name, and queue a join. Joins are written as fragmented mp4 to a `.partial.mp4` and renamed only on success, so an interrupted run leaves a playable, clearly-partial file.
- **Compress**: add videos and queue one compress job each; outputs are named `<name>_compressed.mp4`.
- Watch every job (from any tab) encode in real time in the shared progress dock and cancel any of them mid-flight.
- Run several jobs at once with the **Parallel** toggle in the progress dock — useful for keeping an NVENC GPU's encode engines busy.
- Tune the shared **Compression** panel: container (`mp4` / `mkv` / `mov`), encoder (Auto / NVENC HEVC / CPU libx265 / CPU libx264), NVENC CQ + preset, CPU CRF + preset + tune + pixel format, audio mode, audio bitrate, and faststart.

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
croppy                    # opens on the Crop tab — drop a video or click to browse
croppy path/to/clip.mp4   # opens the Crop tab straight into the editor with that clip
```

On the **Crop** tab, once a video is open:

- **Click-and-drag** on the frame to draw a crop box.
- **Click a box** to select it; its handles appear. Drag the body to move it, drag a handle to resize. The selected box is also highlighted in the sidebar list (and vice-versa).
- **Delete** or **Backspace** removes the selected box.
- **Reload** in the *Preview frame* group re-extracts the preview at a different frame number — useful for finding a representative moment.
- **Process** queues one ffmpeg job per box. Outputs are named `<original_stem>_crop1.<ext>`, `_crop2.<ext>`, …

On the **Combine** and **Compress** tabs, **Add videos…** to build a list (each row shows a thumbnail), drag to reorder, select rows and **Remove selected** or press Delete to prune. Combine joins the list into one file in the order shown; Compress queues one job per video. Both let you choose an **Output folder** (Combine also takes a file name).

Every job, whatever tab it came from, shows up in the progress dock at the bottom — progress bar, status, **Cancel** — and **Clear finished** tidies completed rows away.

## Contributing

The codebase is small and meant to stay readable. Layout:

```text
src/croppy/ffmpeg/   # subprocess wrappers around ffmpeg / ffprobe (no Qt here):
                     #   encoder.py (NVENC/CPU args), crop.py, compress.py, combine.py
src/croppy/gui/      # PySide6 widgets: one tab per operation + shared
                     #   CompressionPanel, VideoList, OutputFolderPicker, progress dock
src/croppy/jobs/     # job queue + per-job QProcess worker; Job has crop/compress/combine variants
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
