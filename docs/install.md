# Install & launch

croppy needs **ffmpeg** to do the actual work. The easiest way to get both is
[pixi](https://pixi.sh), which brings ffmpeg along automatically — you don't have
to install it separately.

## From a checkout (works today)

```bash
git clone https://github.com/roaldarbol/croppy
cd croppy
pixi run croppy
```

That's it — `pixi run croppy` sets up an isolated environment (Python, Qt, ffmpeg)
the first time and launches the app.

## From conda-forge (coming soon)

croppy is on its way to **conda-forge**. Once it lands:

```bash
pixi add croppy
# or
conda install -c conda-forge croppy
```

## Launching

```bash
croppy                    # opens on the Clip tab — drop a video or click to browse
croppy path/to/clip.mp4   # opens straight into the Clip editor with that clip
```

!!! note "Requirements"
    Python 3.12+ and a working `ffmpeg`/`ffprobe` on your `PATH` (pixi provides
    both). A recent NVIDIA GPU is optional — croppy uses it for faster encoding
    when it's there and falls back to the CPU when it isn't.
