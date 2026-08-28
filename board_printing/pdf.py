"""Create print-ready PDFs from a saved bingo board folder."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from bingo_rules import rule_set_from_config
from board_storage import load_board_set


PAPER_SIZES = {"letter": letter, "a4": A4}


def generate_board_pdfs(
    board_folder: str | Path,
    *,
    output_directory: str | Path | None = None,
    paper_size: str = "letter",
    include_individual: bool = True,
    include_combined: bool = True,
) -> list[Path]:
    """Create individual board PDFs and/or one combined printable PDF."""

    if not include_individual and not include_combined:
        raise ValueError("at least one PDF output type must be enabled")
    if paper_size not in PAPER_SIZES:
        raise ValueError(f"paper_size must be one of: {', '.join(PAPER_SIZES)}")

    source_folder = Path(board_folder)
    config, boards = load_board_set(source_folder)
    output = (
        Path(output_directory)
        if output_directory is not None
        else Path("output") / "pdf" / source_folder.name
    )
    output.mkdir(parents=True, exist_ok=True)
    page_size = PAPER_SIZES[paper_size]
    regular_font, bold_font = _register_fonts()
    created: list[Path] = []

    if include_individual:
        digits = max(3, len(str(len(boards))))
        for board_id, board in enumerate(boards, start=1):
            path = output / f"board-{board_id:0{digits}d}.pdf"
            pdf = Canvas(str(path), pagesize=page_size)
            _set_document_metadata(pdf, config, f"Bingo Board {board_id}")
            _draw_board_page(
                pdf,
                board,
                board_id,
                len(boards),
                config,
                page_size,
                regular_font,
                bold_font,
            )
            pdf.save()
            created.append(path.resolve())

    if include_combined:
        path = output / "all-boards.pdf"
        pdf = Canvas(str(path), pagesize=page_size)
        _set_document_metadata(pdf, config, "Music Video Bingo Boards")
        for board_id, board in enumerate(boards, start=1):
            _draw_board_page(
                pdf,
                board,
                board_id,
                len(boards),
                config,
                page_size,
                regular_font,
                bold_font,
            )
            pdf.showPage()
        pdf.save()
        created.append(path.resolve())

    return created


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create print-ready PDFs from a saved bingo board folder."
    )
    parser.add_argument(
        "board_folder", help="folder containing config.json and boards.json"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="output folder (default: output/pdf/<board-folder-name>)",
    )
    parser.add_argument(
        "--paper",
        choices=sorted(PAPER_SIZES),
        default="letter",
        help="paper size (default: letter)",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--combined-only",
        action="store_true",
        help="create only all-boards.pdf",
    )
    output_group.add_argument(
        "--individual-only",
        action="store_true",
        help="create only one PDF per board",
    )
    args = parser.parse_args(argv)

    try:
        paths = generate_board_pdfs(
            args.board_folder,
            output_directory=args.output_dir,
            paper_size=args.paper,
            include_individual=not args.combined_only,
            include_combined=not args.individual_only,
        )
    except ValueError as error:
        parser.error(str(error))

    print(f"Created {len(paths)} PDF{'s' if len(paths) != 1 else ''}:")
    for path in paths:
        print(f"  {path}")
    return 0


def _draw_board_page(
    pdf: Canvas,
    board: tuple[tuple[int | None, ...], ...],
    board_id: int,
    board_count: int,
    config: dict[str, Any],
    page_size: tuple[float, float],
    regular_font: str,
    bold_font: str,
) -> None:
    page_width, page_height = page_size
    width = len(board)
    top_limit = page_height - 1.35 * inch
    bottom_limit = 0.72 * inch
    grid_size = min(page_width - inch, top_limit - bottom_limit)
    cell_size = grid_size / width
    grid_left = (page_width - grid_size) / 2
    grid_bottom = bottom_limit + (top_limit - bottom_limit - grid_size) / 2

    pdf.setFillColor(colors.HexColor("#172033"))
    pdf.setFont(bold_font, 22)
    pdf.drawCentredString(page_width / 2, page_height - 0.58 * inch, "MUSIC VIDEO BINGO")
    pdf.setFont(regular_font, 11)
    pdf.setFillColor(colors.HexColor("#526071"))
    pdf.drawCentredString(page_width / 2, page_height - 0.86 * inch, f"BOARD {board_id}")

    for row_index, row in enumerate(board):
        for column_index, value in enumerate(row):
            x = grid_left + column_index * cell_size
            y = grid_bottom + (width - row_index - 1) * cell_size
            if value is None:
                pdf.setFillColor(colors.HexColor("#E6EDF5"))
            else:
                pdf.setFillColor(colors.white)
            pdf.rect(x, y, cell_size, cell_size, stroke=0, fill=1)
            label = "FREE" if value is None else str(value)
            _draw_fitted_text(
                pdf,
                label,
                x,
                y,
                cell_size,
                cell_size,
                bold_font if value is None else regular_font,
                colors.HexColor("#172033"),
            )

    pdf.setStrokeColor(colors.HexColor("#172033"))
    pdf.setLineWidth(1.15)
    for index in range(width + 1):
        offset = index * cell_size
        pdf.line(grid_left + offset, grid_bottom, grid_left + offset, grid_bottom + grid_size)
        pdf.line(grid_left, grid_bottom + offset, grid_left + grid_size, grid_bottom + offset)
    pdf.setLineWidth(2.2)
    pdf.rect(grid_left, grid_bottom, grid_size, grid_size, stroke=1, fill=0)

    seed = config.get("generator", {}).get("seed", "unknown")
    rule_name = rule_set_from_config(config).name
    pdf.setFillColor(colors.HexColor("#667085"))
    pdf.setFont(regular_font, 7.5)
    pdf.drawString(0.5 * inch, 0.36 * inch, f"Rules: {rule_name} | Seed: {seed}")
    pdf.drawRightString(
        page_width - 0.5 * inch,
        0.36 * inch,
        f"Board {board_id} of {board_count}",
    )


def _draw_fitted_text(
    pdf: Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    font_name: str,
    color: colors.Color,
) -> None:
    horizontal_padding = min(8.0, width * 0.08)
    vertical_padding = min(8.0, height * 0.08)
    available_width = width - horizontal_padding * 2
    available_height = height - vertical_padding * 2
    chosen_size = 6.0
    lines = [text]

    for font_size in range(16, 5, -1):
        wrapped = _wrap_text(text, font_name, font_size, available_width)
        line_height = font_size * 1.18
        if len(wrapped) * line_height <= available_height:
            chosen_size = float(font_size)
            lines = wrapped
            break

    line_height = chosen_size * 1.18
    maximum_lines = max(1, int(available_height // line_height))
    if len(lines) > maximum_lines:
        lines = lines[:maximum_lines]
        lines[-1] = _truncate_text(
            lines[-1], font_name, chosen_size, available_width
        )

    pdf.setFillColor(color)
    pdf.setFont(font_name, chosen_size)
    first_baseline = y + height / 2 + ((len(lines) - 1) * line_height) / 2 - chosen_size * 0.34
    for index, line in enumerate(lines):
        pdf.drawCentredString(
            x + width / 2,
            first_baseline - index * line_height,
            line,
        )


def _wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        pieces = _split_long_word(word, font_name, font_size, max_width)
        for piece in pieces:
            candidate = f"{current} {piece}".strip()
            if current and pdfmetrics.stringWidth(candidate, font_name, font_size) > max_width:
                lines.append(current)
                current = piece
            else:
                current = candidate
    if current:
        lines.append(current)
    return lines


def _split_long_word(
    word: str, font_name: str, font_size: float, max_width: float
) -> list[str]:
    if pdfmetrics.stringWidth(word, font_name, font_size) <= max_width:
        return [word]
    pieces: list[str] = []
    current = ""
    for character in word:
        candidate = current + character
        if current and pdfmetrics.stringWidth(candidate, font_name, font_size) > max_width:
            pieces.append(current)
            current = character
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _truncate_text(text: str, font_name: str, font_size: float, max_width: float) -> str:
    suffix = "..."
    shortened = text
    while shortened and pdfmetrics.stringWidth(
        shortened + suffix, font_name, font_size
    ) > max_width:
        shortened = shortened[:-1]
    return shortened + suffix


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ),
    ]
    for regular_path, bold_path in candidates:
        if regular_path.is_file() and bold_path.is_file():
            if "BingoSans" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("BingoSans", regular_path))
                pdfmetrics.registerFont(TTFont("BingoSans-Bold", bold_path))
            return "BingoSans", "BingoSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _set_document_metadata(pdf: Canvas, config: dict[str, Any], title: str) -> None:
    pdf.setTitle(title)
    pdf.setAuthor("Music Video Bingo")
    pdf.setSubject(
        f"Printable {config.get('board_size', '')}x{config.get('board_size', '')} bingo board"
    )
