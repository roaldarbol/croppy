# Encoding & presets

Every tab shares the same **Encoding** panel. The **Settings** tab holds the
*default*; each thing you queue carries its own copy, so different jobs can encode
differently.

<figure markdown="span">
  ![The Encoding panel](assets/encoding-light.png#only-light){ width="380" loading=lazy }
  ![The Encoding panel](assets/encoding-dark.png#only-dark){ width="380" loading=lazy }
</figure>

## Apply a setting, or inherit it

Each row has a **checkbox**. Checked means Croppy forces that value; unchecked
means it leaves the source's value (or lets the encoder decide). So you can say
"only change the container, keep everything else as the source had it" by ticking
just **Container**.

The buttons at the top flip every row at once:

- **All** — force Croppy's value for every setting.
- **Match source** — keep the source's container, codec, pixel format, frame
  rate, and audio, and let the encoder pick the rest.
- **Reset** — restore every field to your saved default.

!!! note "What 'inherit' means per setting"
    Disabled quality/preset/pixel-format/frame-rate/audio rows simply drop their
    ffmpeg flag, so the source's value (or the encoder default) is kept. A
    disabled **Container** or **Encoder** is taken from the source itself —
    its file extension, and a matching CPU encoder for its codec
    (h264 → libx264, hevc → libx265).

## The settings

- **Container** — `mp4` (plays everywhere), `mkv`, or `mov`.
- **Encoder** — how the video is compressed. **Auto** uses your **graphics card**
  when it can (faster) and the **CPU** otherwise; you can also force GPU
  (**NVENC HEVC**) or CPU (**libx265** / **libx264**).

=== "GPU (NVENC)"

    - **NVENC CQ** — quality; lower is better/bigger (≈23 looks great, ≈28 is fine
      for sharing).
    - **NVENC preset** — effort, `p1` (fastest) … `p7` (best).

=== "CPU (libx264/libx265)"

    - **CPU CRF** — quality; lower is better/bigger (18 ≈ visually lossless,
      23 is a good default).
    - **CPU preset** — effort, `ultrafast` … `veryslow`.
    - **Pixel format** — leave `yuv420p` for maximum compatibility.

- **Frame rate** — optionally resample to a lower fps (e.g. 60 → 10 keeps every
  6th frame). Off keeps the source rate.
- **Re-encode audio** — on re-encodes audio to AAC at the chosen bitrate; off
  stream-copies the source audio untouched (fastest).
- **Faststart** — moves the index to the front so an mp4/mov starts playing in a
  browser before it fully downloads.
- **Creation date** — copies the source's "Date created" onto the output
  (Windows; a no-op elsewhere).

## Presets — Export & Import

Beside the panel are **Import…** and **Export…**. These read and write a small,
hand-editable `.toml` **preset** file — handy to share a configuration or keep
several around.

```toml
# croppy encoding preset
container = "mp4"
encoder = "auto"
cq = 28
applied = ["container", "encoder", "cq", "nvenc_preset", "crf", "preset", "pixel_format"]
```

!!! warning "Export/Import vs Save settings"
    They are different actions:

    - **Export… / Import…** move settings to/from a **file**. On the operation
      tabs, importing applies the preset to the current item. On the **Settings**
      tab, importing loads it into the form — you still click **Save settings**.
    - **Save settings** (Settings tab) persists the current form as the **default**
      every tab starts from.

## The Settings tab

The **Settings** tab is where that default encoding lives, alongside the log
level. Edit the form and click **Save settings** to make it the starting point
for every tab.

![The Settings tab](assets/app-settings-light.png#only-light){ loading=lazy }
![The Settings tab](assets/app-settings-dark.png#only-dark){ loading=lazy }
