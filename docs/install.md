# Install & launch

## Recommended: `pixi global`

Install Croppy as a global command-line app with [pixi](https://pixi.sh), from
the `sleeb-forge` channel (until it lands on conda-forge):

```bash
pixi global install croppy -c https://prefix.dev/sleeb-forge -c conda-forge
```

!!! note "Coming to conda-forge"
    Croppy is on its way to **conda-forge**. Once it lands you'll be able to
    `pixi add croppy` or `conda install -c conda-forge croppy`.

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

!!! tip "GPU is optional"
    A recent NVIDIA GPU lets Croppy encode faster (NVENC). Without one it simply
    uses the CPU instead.
