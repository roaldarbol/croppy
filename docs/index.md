# Croppy

[![Tests](https://github.com/roaldarbol/croppy/actions/workflows/tests.yml/badge.svg)](https://github.com/roaldarbol/croppy/actions/workflows/tests.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://github.com/roaldarbol/croppy)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](https://github.com/roaldarbol/croppy/blob/main/LICENSE)

Croppy is a **desktop app for everyday video chores — cropping, trimming, joining,
and compressing** — turning the ffmpeg flags nobody wants to type into a
point-and-click window: draw on a frame, pick a quality, and click **Add Job to
Queue**.

![The Clip tab](assets/app-clip-light.png#only-light){ loading=lazy }
![The Clip tab](assets/app-clip-dark.png#only-dark){ loading=lazy }

!!! success "Free & open source"
    Croppy is **MIT-licensed** and developed in the open — free to use, read,
    fork, and build on, with no strings attached. The code lives at
    [github.com/roaldarbol/croppy](https://github.com/roaldarbol/croppy).

## What's in the window

Croppy is organised into a few tabs that share one **Encoding** panel design and
one progress strip along the bottom you can watch and cancel from:

- 🎬 **[Clip](clip.md)** — draw crop boxes and/or set time ranges (*trims*) on a
  video and get one file per combination.
- 🗜️ **[Compress](compress.md)** — re-encode any number of videos smaller in one go.
- 🔗 **[Combine](combine.md)** — join videos, in the order you choose, into one file.
- ▶️ **[Jobs](output-and-jobs.md)** — everything you've staged from any tab; start,
  cancel, and clear from here.
- ⚙️ **[Settings](encoding.md)** — the default encoding every tab starts from.

## The ideas that run through it

- 📥 **Stage, then run.** Each tab's **Add Job to Queue** button stages work on the
  **Jobs** tab; you assemble a batch and fire it off when you're ready. A slim
  strip at the bottom always shows what's happening, from whichever tab you're on.
- 🎛️ **Encoding is per item.** The **Settings** tab holds the default; everything you
  queue carries its own copy, so you can queue the same video twice with small
  differences and compare. By default Croppy encodes on your **graphics card**
  when it can — which is much faster — and on the **CPU** otherwise.
- ✅ **Apply only what you mean to.** Every encoding setting can be left to inherit
  from the source instead of being forced — see [Encoding & presets](encoding.md).
- 🏷️ **You name the output.** Every tab shows a sensible default name and lets you
  change it — see [Output names & the Jobs queue](output-and-jobs.md).

!!! tip "New here?"
    Start with [Install & launch](install.md), then open the
    [Clip tab](clip.md) walkthrough — it covers the parts (preview frame, crops,
    trims, output) that the other tabs reuse.
