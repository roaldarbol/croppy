<p align="center">
  <img src="src/croppy/assets/croppy.png" alt="Croppy logo" width="200">
</p>

<h1 align="center">Croppy</h1>

<p align="center">
  <em>Common video chores — cropping, trimming, joining, and compressing — in one window.</em>
</p>

<p align="center">
  <a href="https://github.com/roaldarbol/croppy/actions/workflows/tests.yml"><img src="https://github.com/roaldarbol/croppy/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.12%2B-blue.svg" alt="Python 3.12+"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-yellow.svg" alt="License: MIT"></a>
</p>

---

Croppy is a **desktop app for everyday video chores — cropping, trimming, joining, and compressing** — turning the ffmpeg flags nobody wants to type into a point-and-click window: draw on a frame, pick a quality, and click **Add Job to Queue**.

<p align="center">
  <img src="docs/assets/app-clip-light.png#gh-light-mode-only" alt="The Clip tab" width="820">
  <img src="docs/assets/app-clip-dark.png#gh-dark-mode-only" alt="The Clip tab" width="820">
</p>

> [!TIP]
> **Full documentation:** **[roald-arboel.com/croppy](https://roald-arboel.com/croppy)**

## What's in the window

Croppy is organised into a few tabs that share one **Encoding** panel design and one progress strip along the bottom you can watch and cancel from:

- 🎬 **[Clip](https://roald-arboel.com/croppy/clip/)** — draw crop boxes and/or set time ranges (*trims*) on a video and get one file per combination.
- 🗜️ **[Compress](https://roald-arboel.com/croppy/compress/)** — re-encode any number of videos smaller in one go.
- 🔗 **[Combine](https://roald-arboel.com/croppy/combine/)** — join videos, in the order you choose, into one file.
- ▶️ **[Jobs](https://roald-arboel.com/croppy/output-and-jobs/)** — everything you've staged from any tab; start, cancel, and clear from here.
- ⚙️ **[Settings](https://roald-arboel.com/croppy/encoding/)** — the default encoding every tab starts from.

## The ideas that run through it

- 📥 **Stage, then run.** Each tab's **Add Job to Queue** button stages work on the **Jobs** tab; you assemble a batch and fire it off when you're ready. A slim strip at the bottom always shows what's happening, from whichever tab you're on.
- 🎛️ **Encoding is per item.** The **Settings** tab holds the default; everything you queue carries its own copy, so you can queue the same video twice with small differences and compare. By default Croppy encodes on your **graphics card** when it can — which is much faster — and on the **CPU** otherwise.
- ✅ **Apply only what you mean to.** Every encoding setting can be applied or left to inherit from the source instead of being forced.
- 🏷️ **You name the output.** Every tab shows a sensible default name and lets you change it.

## Install

Install Croppy as a global command-line app with [Pixi](https://pixi.sh), from the `sleeb-forge` channel (until it lands on conda-forge):

```bash
pixi global install croppy -c https://prefix.dev/sleeb-forge -c conda-forge
```

> [!NOTE]
> Don't have Pixi? [Install it first](https://pixi.sh/latest/installation/) — it's a one-liner. Croppy is on its way to **conda-forge**; once it lands you'll be able to drop the `sleeb-forge` channel.

Once installed, launch **Croppy** from your Start menu / Applications folder / app menu, or run it from a terminal:

```bash
croppy                    # opens on the Clip tab — drop a video or click to browse
croppy path/to/clip.mp4   # opens straight into the Clip editor with that clip
```

## Contributing

The codebase is small and meant to stay readable. Layout:

```text
src/croppy/ffmpeg/   # subprocess wrappers around ffmpeg / ffprobe (no Qt here):
                     #   encoder.py (GPU/CPU args), clip.py, compress.py, combine.py
src/croppy/gui/      # PySide6 widgets: one tab per operation + shared
                     #   CompressionPanel, VideoList, OutputFolderPicker, StatusStrip
src/croppy/jobs/     # job queue + per-job QProcess worker; Job has clip/compress/combine variants
src/croppy/models.py # CropRegion, Trim, EncodeSettings — plain dataclasses
```

To set up a working copy — [Pixi](https://pixi.sh) handles everything, including `ffmpeg`:

```bash
git clone https://github.com/roaldarbol/croppy
cd croppy
pixi run croppy                # launch the app from source

pixi run -e dev install-hooks  # one-time: wire lefthook pre-commit hooks
pixi run -e dev test
pixi run -e dev lint
pixi run -e dev format
```

Pre-commit hooks (via [lefthook](https://github.com/evilmartians/lefthook)) run `ruff check --fix` and `ruff format` on staged Python files automatically.

## License

MIT — see [LICENSE](LICENSE).
