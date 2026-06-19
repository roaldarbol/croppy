<p align="center">
  <img src="src/croppy/assets/croppy.png" alt="croppy logo" width="200">
</p>

<h1 align="center">croppy</h1>

<p align="center">
  <em>Common lab video chores — cropping, joining, and compressing — in one window.</em>
</p>

<p align="center">
  <a href="https://github.com/roaldarbol/croppy/actions/workflows/tests.yml"><img src="https://github.com/roaldarbol/croppy/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License: MIT"></a>
</p>

---

croppy does the parts ffmpeg handles in a handful of flags nobody wants to type by hand. It's organized into three operation tabs — **Crop**, **Combine**, **Compress** — plus a **Jobs** queue and a **Settings** tab, all sharing one **Encoding** panel design and one progress strip at the bottom you can watch and cancel from:

- **Crop** — draw one or more boxes on a preview frame and get one cropped file per box.
- **Combine** — pick videos, drag them into the order you want, and join them into a single file. Queue as many combine jobs as you like.
- **Compress** — pick any number of videos and re-encode them smaller in one go.

Each tab builds jobs with an **Add Job to Queue** button (which flashes a short confirmation so you know it landed); the **Jobs** tab collects everything you've staged from any tab. From there you start them — **Start all** or **Start selected** — so you can assemble a batch and fire it off when you're ready. A slim strip along the bottom of the window always shows what's happening (counts + progress), from whichever tab you're on.

Encoding is **per item**: the **Settings** tab holds the *default*, and each thing you queue carries its own. In Crop every open video has its own settings; in Compress every video row does; in Combine every group does. So you can queue the same video a few times with small differences and compare. By default croppy encodes with **NVENC HEVC on the GPU when it's available** and falls back to CPU **libx265** otherwise, so files shrink without you choosing an encoder — but the panel lets you force GPU or CPU and tune quality.

## What you can do

- **Crop**: open one or more videos — drop them on the canvas or use **Add video…** (you can **select or drag in several at once**). They collect in a left **Videos** list where each clip keeps its own crops, encoding, output folder, and preview frame; **Duplicate** reuses a clip's crops/settings and **Remove** drops one. Pick the preview frame (handy when a clip starts on black); draw, resize (corner/edge handles), and reposition multiple boxes — each box is an independent output.
- **Combine**: organize joins as **groups** — each group is one ordered set of videos with its own output name and encoding. Build several groups in the left list, then **Add Job to Queue** stages the selected group. Joins are written as fragmented mp4 to a `.partial.mp4` and renamed only on success, so an interrupted run leaves a playable, clearly-partial file.
- **Compress**: drop or add videos and queue one compress job each (named `<name>_compressed.mp4`, auto-numbered if you queue the same source again). Each row has its **own encoding** (click a row to edit it; the row shows a summary). **Duplicate selected** copies rows; the list stays put after queueing so you can re-queue with tweaked settings.
- **Jobs**: see every staged job from every tab (grouped by state, with a crop/combine/compress tag), start all or just the ones you select, cancel a running job, and remove or clear finished rows.
- **Settings**: set the default encoding every tab starts from and the runtime log level; one **Save settings** button persists the whole tab (unsaved edits revert if you switch away and back).
- Run several jobs at once with the **Parallel** toggle on the Jobs tab — useful for keeping an NVENC GPU's encode engines busy.
- Tune any **Encoding** panel: container (`mp4` / `mkv` / `mov`), encoder (Auto / NVENC HEVC / CPU libx265 / CPU libx264), NVENC CQ + preset, CPU CRF + preset + tune + pixel format, audio mode, audio bitrate, and faststart.

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
- **Add Job to Queue** stages one job per box (named `<original_stem>_crop1.<ext>`, `_crop2.<ext>`, …) on the Jobs tab.

On the **Combine** and **Compress** tabs, drop videos onto the list (or **Add videos…**) — each row is a thumbnail plus the file's resolution, fps, duration, and frame count. Drag to reorder, select rows and **Remove selected** (or press Delete) to prune; Compress also has **Duplicate selected**. In **Combine** the list belongs to the selected **group** (use **New group** to stage another join); in **Compress** clicking a row shows that video's own encoding. Choose an **Output folder** (Combine groups also take a file name), and tweak the **Encoding** panel for the selected item before queueing.

Staged jobs collect on the **Jobs** tab. Hit **Start all** or tick a few rows and **Start selected**; **Cancel** stops a running job, **Remove selected** drops staged ones, and **Clear finished** tidies completed rows away. The bottom strip summarizes it all from any tab.

## Contributing

The codebase is small and meant to stay readable. Layout:

```text
src/croppy/ffmpeg/   # subprocess wrappers around ffmpeg / ffprobe (no Qt here):
                     #   encoder.py (NVENC/CPU args), crop.py, compress.py, combine.py
src/croppy/gui/      # PySide6 widgets: one tab per operation + shared
                     #   CompressionPanel, VideoList, OutputFolderPicker, StatusStrip
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
