# Install & launch

## Recommended: `pixi global`

Croppy is on **conda-forge**, so install it as a global command-line app with
[Pixi](https://pixi.sh) in one line:

```bash
pixi global install croppy
```

!!! note "Don't have Pixi?"
    [Install Pixi first](https://pixi.sh/latest/installation/) — it's a one-line
    command for macOS, Linux, and Windows.

!!! note "Prefer conda?"
    Croppy is on conda-forge, so `conda install -c conda-forge croppy` works too.

## Updating

Update Croppy to the latest release with:

```bash
pixi global update croppy
```

Croppy also checks for a newer version on startup and lets you know when one is
available.

## Uninstalling

Remove Croppy with:

```bash
pixi global uninstall croppy
```

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
