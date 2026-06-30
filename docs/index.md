# croppy

*Common lab video chores — cropping, trimming, joining, and compressing — in one window.*

croppy does the parts of ffmpeg that take a handful of flags nobody wants to type
by hand. You draw on a frame, type a couple of numbers, pick a quality, and click
**Add Job to Queue** — croppy builds the ffmpeg command and runs it for you.

![The Clip tab](assets/app-clip-light.png#only-light){ loading=lazy }
![The Clip tab](assets/app-clip-dark.png#only-dark){ loading=lazy }

## What's in the window

croppy is organised into a few tabs that share one **Encoding** panel design and
one progress strip along the bottom you can watch and cancel from:

- **[Clip](clip.md)** — draw crop boxes and/or set time ranges (*trims*) on a
  video and get one file per combination.
- **[Compress](compress.md)** — re-encode any number of videos smaller in one go.
- **[Combine](combine.md)** — join videos, in the order you choose, into one file.
- **[Jobs](output-and-jobs.md)** — everything you've staged from any tab; start,
  cancel, and clear from here.
- **[Settings](encoding.md)** — the default encoding every tab starts from.

## The ideas that run through it

- **Stage, then run.** Each tab's **Add Job to Queue** button stages work on the
  **Jobs** tab; you assemble a batch and fire it off when you're ready. A slim
  strip at the bottom always shows what's happening, from whichever tab you're on.
- **Encoding is per item.** The **Settings** tab holds the default; everything you
  queue carries its own copy, so you can queue the same video twice with small
  differences and compare. By default croppy uses **NVENC HEVC on the GPU when
  it's available** and falls back to CPU **libx265** otherwise.
- **Apply only what you mean to.** Every encoding setting can be left to inherit
  from the source instead of being forced — see [Encoding & presets](encoding.md).
- **You name the output.** Every tab shows a sensible default name and lets you
  change it — see [Output names & the Jobs queue](output-and-jobs.md).

!!! tip "New here?"
    Start with [Install & launch](install.md), then open the
    [Clip tab](clip.md) walkthrough — it covers the parts (preview frame, crops,
    trims, output) that the other tabs reuse.
