"""Context-aware map legend: the on-image key for order/result symbols and power
colors, drawn onto the board after everything else.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from .board import KNOWN_POWER_NAMES, _convert_color_to_rgb
from .visualization_config import get_config

_viz_config = get_config()


def _draw_legend(image: Image.Image, map_type: str, active_powers: list[str] | None = None) -> None:
    """
    Draw a context-aware legend on the map image.

    Args:
        image: PIL Image to draw on
        map_type: Type of map - "orders", "resolution", "initial", "final", "builds"
        active_powers: List of active power names to show in legend
    """
    if not _viz_config.is_legend_enabled():
        return

    legend_specs = _viz_config.get_legend_specs()
    padding = legend_specs["padding"]
    item_spacing = legend_specs["item_spacing"]
    symbol_size = legend_specs["symbol_size"]
    title_font_size = legend_specs["title_font_size"]
    item_font_size = legend_specs["item_font_size"]

    # Determine legend items based on map type
    legend_items = []

    if map_type == "orders":
        legend_items = [
            ("move", "Move"),
            ("hold", "Hold"),
            ("support", "Support"),
            ("convoy", "Convoy"),
        ]
    elif map_type == "resolution":
        legend_items = [
            ("success", "Success"),
            ("failed", "Failed"),
            ("bounce", "Bounced"),
            ("dislodged", "Dislodged"),
            ("cut", "Support Cut"),
        ]
    elif map_type == "builds":
        legend_items = [
            ("build", "Build"),
            ("destroy", "Destroy"),
        ]
    elif map_type in ["initial", "final"]:
        # Just show power colors for initial/final maps
        legend_items = []

    # Add power colors if active_powers provided (only use known power names; ignore unit strings like "A BUD" if wrong format was passed)
    power_items = []
    if active_powers:
        for power in sorted(active_powers):
            if power in KNOWN_POWER_NAMES:
                power_items.append(("power", power))

    # Calculate legend dimensions
    total_items = len(legend_items) + len(power_items)
    if total_items == 0:
        return

    # Estimate text width (approximate)
    max_text_width = 100  # Default
    for _, label in legend_items + power_items:
        max_text_width = max(max_text_width, len(label) * 8)

    legend_width = padding * 2 + symbol_size + 10 + max_text_width
    item_height = max(symbol_size, 18) + item_spacing

    # Add title height if we have legend items
    title_height = title_font_size + 10 if legend_items else 0

    # Add separator height if we have both legend items and power items
    separator_height = 15 if legend_items and power_items else 0

    legend_height = padding * 2 + title_height + (len(legend_items) * item_height) + separator_height + (len(power_items) * item_height)

    # Position legend (bottom-left by default)
    position = legend_specs.get("position", "bottom-left")
    if position == "bottom-left":
        legend_x = 20
        legend_y = image.height - legend_height - 20
    elif position == "bottom-right":
        legend_x = image.width - legend_width - 20
        legend_y = image.height - legend_height - 20
    elif position == "top-left":
        legend_x = 20
        legend_y = 20
    else:  # top-right
        legend_x = image.width - legend_width - 20
        legend_y = 20

    # Create overlay for legend with transparency
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)

    # Draw legend background
    bg_color = tuple(legend_specs["background_color"])
    border_color = tuple(legend_specs["border_color"])
    border_width = legend_specs["border_width"]

    overlay_draw.rectangle(
        [legend_x, legend_y, legend_x + legend_width, legend_y + legend_height],
        fill=bg_color,
        outline=border_color[:3],
        width=border_width
    )

    # Draw legend title if we have legend items
    current_y = legend_y + padding
    if legend_items:
        title_text = {
            "orders": "Orders",
            "resolution": "Results",
            "builds": "Adjustments",
        }.get(map_type, "Legend")

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_font_size)
        except OSError:
            font = ImageFont.load_default()

        overlay_draw.text(
            (legend_x + padding, current_y),
            title_text,
            fill=(0, 0, 0, 255),
            font=font
        )
        current_y += title_font_size + 10

    # Draw legend items
    try:
        item_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", item_font_size)
    except OSError:
        item_font = ImageFont.load_default()

    symbol_x = legend_x + padding
    text_x = symbol_x + symbol_size + 10

    for item_type, label in legend_items:
        symbol_center_y = current_y + symbol_size // 2

        # Draw the symbol based on type
        if item_type == "move":
            # Draw a small arrow
            arrow_start = (symbol_x, symbol_center_y)
            arrow_end = (symbol_x + symbol_size, symbol_center_y)
            _draw_mini_arrow(overlay_draw, arrow_start, arrow_end, (0, 0, 0), "solid")
        elif item_type == "hold":
            # Draw a dashed circle
            r = symbol_size // 3
            overlay_draw.ellipse(
                [symbol_x + symbol_size//2 - r, symbol_center_y - r,
                 symbol_x + symbol_size//2 + r, symbol_center_y + r],
                outline=(100, 100, 100, 255),
                width=2
            )
        elif item_type == "support":
            # Draw a dashed line with green tint
            _draw_mini_arrow(overlay_draw,
                (symbol_x, symbol_center_y),
                (symbol_x + symbol_size, symbol_center_y),
                (144, 238, 144), "dashed")
        elif item_type == "convoy":
            # Draw golden curved line
            _draw_mini_arrow(overlay_draw,
                (symbol_x, symbol_center_y),
                (symbol_x + symbol_size, symbol_center_y),
                (255, 215, 0), "solid")
        elif item_type == "success":
            # Draw checkmark
            _draw_mini_checkmark(overlay_draw,
                (symbol_x + symbol_size//2, symbol_center_y), (0, 200, 0))
        elif item_type == "failed":
            # Draw X
            _draw_mini_x(overlay_draw,
                (symbol_x + symbol_size//2, symbol_center_y), (255, 0, 0))
        elif item_type == "bounce":
            # Draw orange X
            _draw_mini_x(overlay_draw,
                (symbol_x + symbol_size//2, symbol_center_y), (255, 165, 0))
        elif item_type == "dislodged":
            # Draw red-bordered circle
            r = symbol_size // 3
            overlay_draw.ellipse(
                [symbol_x + symbol_size//2 - r, symbol_center_y - r,
                 symbol_x + symbol_size//2 + r, symbol_center_y + r],
                fill=(200, 200, 200, 255),
                outline=(255, 0, 0, 255),
                width=3
            )
        elif item_type == "cut":
            # Draw support line with X through it
            _draw_mini_arrow(overlay_draw,
                (symbol_x, symbol_center_y),
                (symbol_x + symbol_size, symbol_center_y),
                (144, 238, 144), "dashed")
            _draw_mini_x(overlay_draw,
                (symbol_x + symbol_size//2, symbol_center_y), (255, 0, 0), size=6)
        elif item_type == "build":
            # Draw green circle with plus
            r = symbol_size // 3
            cx, cy = symbol_x + symbol_size//2, symbol_center_y
            overlay_draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=(0, 200, 0, 255),
                outline=(0, 100, 0, 255),
                width=2
            )
            overlay_draw.line([cx - r + 3, cy, cx + r - 3, cy], fill=(255, 255, 255), width=2)
            overlay_draw.line([cx, cy - r + 3, cx, cy + r - 3], fill=(255, 255, 255), width=2)
        elif item_type == "destroy":
            # Draw red circle with X
            r = symbol_size // 3
            cx, cy = symbol_x + symbol_size//2, symbol_center_y
            overlay_draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=(200, 0, 0, 255),
                outline=(100, 0, 0, 255),
                width=2
            )
            _draw_mini_x(overlay_draw, (cx, cy), (255, 255, 255), size=r-2)

        # Draw label
        overlay_draw.text(
            (text_x, current_y + (symbol_size - item_font_size) // 2),
            label,
            fill=(0, 0, 0, 255),
            font=item_font
        )

        current_y += item_height

    # Draw separator line if we have both sections
    if legend_items and power_items:
        current_y += 5
        overlay_draw.line(
            [legend_x + padding, current_y, legend_x + legend_width - padding, current_y],
            fill=(150, 150, 150, 255),
            width=1
        )
        current_y += 10

    # Draw power color items
    for item_type, power in power_items:
        symbol_center_y = current_y + symbol_size // 2

        # Draw power color box
        power_color = _viz_config.get_power_color(power)
        rgb_color = _convert_color_to_rgb(power_color)
        # Ensure rgb_color is a tuple, not a string
        if isinstance(rgb_color, str):
            # Convert named color to RGB using PIL
            from PIL import ImageColor
            try:
                rgb_color = ImageColor.getrgb(rgb_color)
            except ValueError:
                rgb_color = (128, 128, 128)  # Fallback to gray
        r = symbol_size // 3
        cx, cy = symbol_x + symbol_size//2, symbol_center_y
        overlay_draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=rgb_color + (255,),
            outline=(0, 0, 0, 255),
            width=2
        )

        # Draw power name
        overlay_draw.text(
            (text_x, current_y + (symbol_size - item_font_size) // 2),
            power.title(),
            fill=(0, 0, 0, 255),
            font=item_font
        )

        current_y += item_height

    # Composite overlay onto image
    if image.mode == 'RGBA':
        image.alpha_composite(overlay)
    else:
        # Convert to RGBA, composite, convert back
        image_rgba = image.convert('RGBA')
        image_rgba.alpha_composite(overlay)
        # Paste back (for RGB images)
        image.paste(image_rgba.convert('RGB'))


def _draw_mini_arrow(
    draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], color: tuple, style: str = "solid"
) -> None:
    """Draw a small arrow for legend."""
    x1, y1 = start
    x2, y2 = end

    if style == "dashed":
        # Draw dashed line
        for i in range(0, int(x2 - x1), 6):
            draw.line([x1 + i, y1, x1 + i + 3, y2], fill=color + (255,), width=2)
    else:
        draw.line([x1, y1, x2, y2], fill=color + (255,), width=2)

    # Draw arrowhead
    arrow_size = 5
    draw.polygon([
        (x2, y2),
        (x2 - arrow_size, y2 - arrow_size//2),
        (x2 - arrow_size, y2 + arrow_size//2)
    ], fill=color + (255,))


def _draw_mini_checkmark(draw: ImageDraw.ImageDraw, center: tuple[float, float], color: tuple) -> None:
    """Draw a small checkmark for legend."""
    x, y = center
    size = 8
    points = [
        (x - size, y),
        (x - size//3, y + size//2),
        (x + size, y - size//2)
    ]
    draw.line([points[0], points[1], points[2]], fill=color + (255,), width=3)


def _draw_mini_x(draw: ImageDraw.ImageDraw, center: tuple[float, float], color: tuple, size: int = 8) -> None:
    """Draw a small X for legend."""
    x, y = center
    draw.line([x - size, y - size, x + size, y + size], fill=color + (255,), width=3)
    draw.line([x - size, y + size, x + size, y - size], fill=color + (255,), width=3)
