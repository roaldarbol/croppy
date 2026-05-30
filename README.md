# croppy

Visual GUI for drawing crop boxes on a video frame and producing cropped output files via ffmpeg.

Draw one or more rectangles on a preview frame, optionally tweak the encoding settings, hit **Process**, and croppy will spawn one ffmpeg job per crop and report progress in a panel you can cancel from.

## Status

Early development. Wiring up the basics. See [the project memory](../../.claude/projects/-Users-roaldarbol-Filen-Projects-python-croppy/memory/project_croppy.md) for design decisions if you have access.

## Install

### With pixi (recommended)

```bash
pixi install
pixi run croppy
```

`ffmpeg` is pulled in as a conda-forge dependency automatically.

### With pip

```bash
pip install croppy
```

You must have `ffmpeg` and `ffprobe` installed and on your `PATH`.

## Usage

```bash
croppy                  # opens the GUI; drop a video onto it or click to browse
croppy path/to/clip.mp4 # opens the GUI with that video pre-loaded
```

## Development

```bash
pixi run -e dev test
```

## License

MIT — see [LICENSE](LICENSE).
