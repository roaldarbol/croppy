# Install & launch

Croppy needs **ffmpeg** to do the actual work. The install methods below bring it
along automatically — you don't have to install ffmpeg separately.

## Recommended: `pixi global`

Install Croppy as a global command-line app with [pixi](https://pixi.sh), from
the `sleeb-forge` channel (until it lands on conda-forge):

```bash
pixi global install croppy -c https://prefix.dev/sleeb-forge
```

That puts a `croppy` command on your `PATH`, with its own isolated environment
(Python, Qt, ffmpeg) — nothing else to set up.

!!! note "Coming to conda-forge"
    Croppy is on its way to **conda-forge**. Once it lands you'll be able to
    `pixi add croppy` or `conda install -c conda-forge croppy`.

## From a checkout

To run the latest from source (also handy for hacking on it):

```bash
git clone https://github.com/roaldarbol/croppy
cd croppy
pixi run croppy
```

`pixi run croppy` sets up an isolated environment the first time and launches the
app.

## Launching

<p align="center" markdown>
  ![Croppy app icon](assets/launch-icon-light.png#only-light){ width="160" }
  ![Croppy app icon](assets/launch-icon-dark.png#only-dark){ width="160" }
</p>

Once installed, launch **Croppy** like any other app — look for this icon. It
registers itself in the usual places:

- **Windows** — the **Start menu** (and a desktop shortcut)
- **macOS** — the **Applications** folder / Launchpad
- **Linux** — your application menu

Prefer the terminal? It's also a command:

```bash
croppy                    # opens on the Clip tab — drop a video or click to browse
croppy path/to/clip.mp4   # opens straight into the Clip editor with that clip
```

!!! note "Requirements"
    A working `ffmpeg`/`ffprobe` (the install methods above provide both). A
    recent NVIDIA GPU is optional — Croppy uses it for faster encoding when it's
    there and falls back to the CPU when it isn't.
