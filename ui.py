# -*- coding: utf-8 -*-
"""
Modern CLI interface for EDI File Processor.

Provides professional ASCII art banner and colored logging output
using Rich library for enhanced terminal experience.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

BANNER = r"""
   ================================================================

     ######   ######  ##       ######## ########   ######
    ##    ## ##    ## ##       ##       ##     ## ##    ##
    ##       ##       ##       ##       ##     ## ##
    ##        ######  ##       ######   ##     ## ##
    ##             ## ##       ##       ##     ## ##
    ##    ## ##    ## ##       ##       ##     ## ##    ##
     ######   ######  ######## ######## ########   ######

            File Processor v0.9.0-beta
         CSV to XLSX with Data Integrity Validation

   ================================================================
"""

CUSTOM_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "bold magenta",
    "dim": "dim cyan",
})

console = Console(theme=CUSTOM_THEME)


def display_banner() -> None:
    banner_text = Text(BANNER, style="bold cyan")
    console.print(banner_text)
    console.print()


def display_startup_info(watch_path: Path) -> None:
    startup_panel = Panel.fit(
        f"[bold cyan]Monitoring:[/bold cyan] {watch_path}\n"
        f"[bold cyan]Status:[/bold cyan] [success]Active[/success]\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        title="[bold]System Status[/bold]",
        border_style="cyan",
    )
    console.print(startup_panel)
    console.print()


def display_processing_start(filename: str, file_type: str) -> None:
    console.print(f"[highlight]>>>[/highlight] Processing {file_type}: [bold]{filename}[/bold]")


def display_success(message: str) -> None:
    console.print(f"[success]SUCCESS[/success] {message}")


def display_warning(message: str) -> None:
    console.print(f"[warning]WARNING[/warning] {message}")


def display_error(message: str) -> None:
    console.print(f"[error]ERROR[/error] {message}")


def display_info(message: str) -> None:
    console.print(f"[info]INFO[/info] {message}")


def display_validation_result(
    is_valid: bool,
    dimensions_match: bool,
    columns_match: bool,
    data_types_preserved: bool,
    sample_data_match: bool
) -> None:
    if is_valid:
        console.print("[success]VALIDATION PASSED[/success] Data integrity confirmed")
    else:
        console.print("[error]VALIDATION FAILED[/error] Issues detected:")
        console.print(f"  Dimensions match: {'[success]Yes[/success]' if dimensions_match else '[error]No[/error]'}")
        console.print(f"  Columns match: {'[success]Yes[/success]' if columns_match else '[error]No[/error]'}")
        console.print(f"  Types preserved: {'[success]Yes[/success]' if data_types_preserved else '[error]No[/error]'}")
        console.print(f"  Data match: {'[success]Yes[/success]' if sample_data_match else '[error]No[/error]'}")


def display_shutdown() -> None:
    console.print()
    shutdown_panel = Panel.fit(
        "[bold yellow]Watcher stopped by user[/bold yellow]\n"
        "[dim]All pending operations completed[/dim]",
        title="[bold]Shutdown[/bold]",
        border_style="yellow",
    )
    console.print(shutdown_panel)


def setup_rich_logging(log_file_path: Path) -> None:
    if logging.getLogger().hasHandlers():
        logging.getLogger().handlers.clear()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[
            RichHandler(
                console=console,
                show_time=True,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
                tracebacks_show_locals=False,
            ),
            logging.FileHandler(log_file_path, encoding='utf-8')
        ]
    )


class RichLogger:
    @staticmethod
    def info(message: str) -> None:
        logging.info(f"[info]{message}[/info]")

    @staticmethod
    def success(message: str) -> None:
        logging.info(f"[success]{message}[/success]")

    @staticmethod
    def warning(message: str) -> None:
        logging.warning(f"[warning]{message}[/warning]")

    @staticmethod
    def error(message: str) -> None:
        logging.error(f"[error]{message}[/error]")

    @staticmethod
    def highlight(message: str) -> None:
        logging.info(f"[highlight]{message}[/highlight]")

    @staticmethod
    def dim(message: str) -> None:
        logging.info(f"[dim]{message}[/dim]")


logger = RichLogger()