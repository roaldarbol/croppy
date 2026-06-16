"""Typer entry point. Launches the Qt GUI, optionally pre-loading a video."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from croppy import __version__
from croppy.logging import configure as configure_logging

cli = typer.Typer(
    name="croppy",
    help="Visual GUI for drawing crop boxes on a video and producing cropped outputs via ffmpeg.",
    add_completion=False,
    no_args_is_help=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"croppy {__version__}")
        raise typer.Exit()


@cli.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    video: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Optional video file to open on launch.",
        ),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "-v",
            "--verbose",
            count=True,
            help="Increase log verbosity from the default INFO to DEBUG.",
        ),
    ] = 0,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Print version and exit.",
        ),
    ] = False,
) -> None:
    """Launch the croppy GUI."""
    if ctx.invoked_subcommand is not None:
        return
    configure_logging(verbose)
    from croppy.app import run  # lazy: keep --help / --version fast and Qt-free

    raise typer.Exit(code=run(video))


def app() -> None:
    """Console-script entry point."""
    cli()


if __name__ == "__main__":
    app()
