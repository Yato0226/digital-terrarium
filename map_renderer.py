"""Pure-Python PNG map renderer (zlib + struct, no Pillow).

Renders the 5x5 terrarium grid as a small RGB PNG: each tile is a solid
color block, pawns override with a marker color, wildlife with another.
"""

import struct
import zlib

import state

CELL = 16  # pixels per grid tile
TILE_COLORS = {
    "🌲": (46, 125, 50),   # Forest
    "🫐": (161, 189, 105), # Meadow
    "🌊": (79, 129, 189),  # River
    "🏕️": (198, 156, 60),  # Camp
    "💀": (120, 120, 120), # Ruins
    "🪨": (140, 140, 140), # Quarry
    "🔥": (224, 92, 42),   # Burning
    "🌫️": (52, 52, 58),    # Ash / scorched earth
}
PAWN_COLOR = (240, 240, 240)
WILDLIFE_COLOR = (222, 111, 111)
FALLBACK_COLOR = (60, 60, 60)


def _chunk(tag, data):
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data))
    )


def render_png():
    """Return bytes of a PNG image of the current world map."""
    grid = state.world_state["grid"]
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    width, height = cols * CELL, rows * CELL

    pawn_cells = set()
    for p in state.world_state["pawns"].values():
        if p["status"] == "active":
            pawn_cells.add(tuple(p["pos"]))
    wild_cells = set(tuple(w["pos"]) for w in state.world_state["wildlife"])

    raw = bytearray()
    for py in range(height):
        raw.append(0)  # filter type None
        for px in range(width):
            gx, gy = px // CELL, py // CELL
            color = TILE_COLORS.get(grid[gy][gx], FALLBACK_COLOR)
            if (gx, gy) in pawn_cells:
                color = PAWN_COLOR
            elif (gx, gy) in wild_cells:
                color = WILDLIFE_COLOR
            raw += bytes(color)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    return png
