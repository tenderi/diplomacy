"""Army/fleet unit icon loading and drawing.

Icons are PNG files under ``icons/`` (project root); ``_load_and_process_icon``
recolors the white pixels to the requested power color, adds an outline, and
caches the processed image by ``(path, fill_color, outline_color, size)`` so the
per-pixel recolor pass only runs once per distinct combination.
"""
from __future__ import annotations

import logging
import os

from PIL import Image, ImageDraw

from .visualization_config import get_config

logger = logging.getLogger("diplomacy.rendering.map")

# Icon processing cache: keyed by (path, fill_color, outline_color, size)
_icon_cache: dict[tuple[str, tuple[int, ...], tuple[int, ...], int], Image.Image] = {}

_viz_config = get_config()


def _load_and_process_icon(
    icon_path: str, fill_color: tuple[int, ...], outline_color: tuple[int, ...], size: int
) -> Image.Image | None:
    """
    Load an icon PNG file, replace white pixels with fill_color, add outline, and scale to size.

    Args:
        icon_path: Path to the icon PNG file
        fill_color: RGB tuple for the icon color
        outline_color: RGB tuple for the outline
        size: Target size (diameter) for the icon

    Returns:
        Processed PIL Image, or None if file not found
    """
    if not os.path.exists(icon_path):
        logger.warning(f"Icon file not found: {icon_path}")
        return None

    cache_key = (icon_path, tuple(fill_color), tuple(outline_color), size)
    global _icon_cache
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    try:
        # Load the icon image
        icon_img = Image.open(icon_path).convert("RGBA")
        original_size = icon_img.size

        # Create a new image with the same size for processing
        processed = Image.new("RGBA", original_size, (0, 0, 0, 0))
        pixels = icon_img.load()
        processed_pixels = processed.load()

        # Replace white/light pixels with fill_color, preserve transparency
        # White is approximately (255, 255, 255) or close to it
        white_threshold = 200  # Consider pixels brighter than this as "white"
        for y in range(original_size[1]):
            for x in range(original_size[0]):
                r, g, b, a = pixels[x, y]
                if a > 0:  # Not fully transparent
                    # Check if pixel is white/light
                    if r >= white_threshold and g >= white_threshold and b >= white_threshold:
                        # Replace with fill_color, preserve original alpha
                        processed_pixels[x, y] = (*fill_color, a)
                    else:
                        # Keep original pixel (for any non-white details)
                        processed_pixels[x, y] = (r, g, b, a)

        # Add outline using a simple expansion approach
        outline_width = 2
        # Create a slightly larger canvas
        canvas_size = (original_size[0] + outline_width * 2, original_size[1] + outline_width * 2)
        outlined = Image.new("RGBA", canvas_size, (0, 0, 0, 0))

        # Extract alpha channel as mask
        alpha_channel = processed.split()[3]

        # Create outline by drawing the icon slightly larger with outline_color
        # Simple approach: paste the icon multiple times at offsets to create outline
        outline_offsets = [(-outline_width, -outline_width), (-outline_width, 0), (-outline_width, outline_width),
                           (0, -outline_width), (0, outline_width),
                           (outline_width, -outline_width), (outline_width, 0), (outline_width, outline_width)]

        # Create outline version (colored with outline_color)
        outline_base = Image.new("RGBA", original_size, (0, 0, 0, 0))
        outline_pixels = outline_base.load()
        alpha_pixels = alpha_channel.load()
        for y in range(original_size[1]):
            for x in range(original_size[0]):
                if alpha_pixels[x, y] > 0:
                    outline_pixels[x, y] = (*outline_color, alpha_pixels[x, y])

        # Paste outline versions at offsets
        for dx, dy in outline_offsets:
            outlined.paste(outline_base, (outline_width + dx, outline_width + dy), outline_base)

        # Paste the colored icon on top (centered)
        outlined.paste(processed, (outline_width, outline_width), processed)

        # Scale to target size (maintaining aspect ratio)
        # Scale to fit within the diameter
        scale_factor = size / max(canvas_size)
        new_size = (int(canvas_size[0] * scale_factor), int(canvas_size[1] * scale_factor))
        scaled = outlined.resize(new_size, Image.Resampling.LANCZOS)

        _icon_cache[cache_key] = scaled
        return scaled

    except Exception as e:
        logger.error(f"Error loading icon {icon_path}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def _draw_army_icon(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    fill_color: tuple[int, ...],
    outline_color: tuple[int, ...],
    size: int,
    base_image: Image.Image | None = None,
) -> None:
    """
    Draw an army icon from PNG file with background circle for visibility.

    Args:
        draw: ImageDraw object
        center: (x, y) center coordinates
        fill_color: RGB tuple for fill
        outline_color: RGB tuple for outline
        size: Icon size (diameter)
        base_image: Optional PIL Image object to paste onto (if None, tries to get from draw.im)
    """
    x, y = center
    r = size // 2

    # Get config for background circle
    unit_specs = _viz_config.get_unit_specs()
    use_background = unit_specs.get("background_circle", True)
    bg_color = tuple(unit_specs.get("background_circle_color", [255, 255, 255, 230]))

    # Draw background circle for contrast
    if use_background:
        bg_r = r + 2  # Slightly larger than icon
        draw.ellipse([x - bg_r, y - bg_r, x + bg_r, y + bg_r],
                    fill=bg_color, outline=outline_color, width=3)

    # Find icon file path (relative to project root)
    # icons.py is at: new_implementation/src/rendering/icons.py
    # icons are at: new_implementation/icons/army.png
    current_file = os.path.abspath(__file__)
    # Go up from src/rendering/icons.py to src, then to new_implementation, then to icons
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    icon_path = os.path.join(project_root, "icons", "army.png")

    # Load and process the icon
    icon_img = _load_and_process_icon(icon_path, fill_color, outline_color, size)

    if icon_img:
        # Get the underlying image from the draw object or use provided base_image
        try:
            if base_image is None:
                base_image = draw.im
                # Try to convert ImagingCore to Image if needed
                if not isinstance(base_image, Image.Image):
                    # For ImagingCore, we need to work with it differently
                    # Get the image from the draw's underlying object
                    try:
                        # Try accessing through the image that created the draw
                        base_image = getattr(draw, '_image', None) or draw.im
                    except Exception:
                        pass

            # Ensure base_image is a proper PIL Image
            if not isinstance(base_image, Image.Image):
                logger.warning(f"base_image is not a PIL Image: {type(base_image)}, falling back")
                draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
                return

            icon_width, icon_height = icon_img.size
            paste_x = int(round(x - icon_width // 2))
            paste_y = int(round(y - icon_height // 2))

            # Ensure coordinates are within image bounds
            img_width, img_height = base_image.size
            paste_x = max(0, min(paste_x, img_width - icon_width))
            paste_y = max(0, min(paste_y, img_height - icon_height))

            # Paste the icon with alpha compositing
            if icon_img.mode == 'RGBA':
                # Extract alpha channel for mask
                alpha = icon_img.split()[3]
                base_image.paste(icon_img, (paste_x, paste_y), alpha)
            else:
                base_image.paste(icon_img, (paste_x, paste_y))

        except (AttributeError, Exception) as e:
            logger.warning(f"Could not paste icon image: {e}, falling back to programmatic drawing")
            import traceback
            logger.debug(traceback.format_exc())
            # Fallback: draw a simple circle as placeholder
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
    else:
        # Fallback: draw a simple circle as placeholder
        logger.warning(f"Icon not loaded from {icon_path}")
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)


def _draw_fleet_icon(
    draw: ImageDraw.ImageDraw,
    center: tuple[float, float],
    fill_color: tuple[int, ...],
    outline_color: tuple[int, ...],
    size: int,
    base_image: Image.Image | None = None,
) -> None:
    """
    Draw a fleet icon from PNG file with background circle for visibility.

    Args:
        draw: ImageDraw object
        center: (x, y) center coordinates
        fill_color: RGB tuple for fill
        outline_color: RGB tuple for outline
        size: Icon size (diameter)
        base_image: Optional PIL Image object to paste onto (if None, tries to get from draw.im)
    """
    x, y = center
    r = size // 2

    # Get config for background circle
    unit_specs = _viz_config.get_unit_specs()
    use_background = unit_specs.get("background_circle", True)
    bg_color = tuple(unit_specs.get("background_circle_color", [255, 255, 255, 230]))

    # Draw background circle for contrast
    if use_background:
        bg_r = r + 2  # Slightly larger than icon
        draw.ellipse([x - bg_r, y - bg_r, x + bg_r, y + bg_r],
                    fill=bg_color, outline=outline_color, width=3)

    # Find icon file path (relative to project root)
    # icons.py is at: new_implementation/src/rendering/icons.py
    # icons are at: new_implementation/icons/ship.png
    current_file = os.path.abspath(__file__)
    # Go up from src/rendering/icons.py to src, then to new_implementation, then to icons
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
    icon_path = os.path.join(project_root, "icons", "ship.png")

    # Load and process the icon
    icon_img = _load_and_process_icon(icon_path, fill_color, outline_color, size)

    if icon_img:
        # Get the underlying image from the draw object or use provided base_image
        try:
            if base_image is None:
                base_image = draw.im
                # Try to convert ImagingCore to Image if needed
                if not isinstance(base_image, Image.Image):
                    # For ImagingCore, we need to work with it differently
                    # Get the image from the draw's underlying object
                    try:
                        # Try accessing through the image that created the draw
                        base_image = getattr(draw, '_image', None) or draw.im
                    except Exception:
                        pass

            # Ensure base_image is a proper PIL Image
            if not isinstance(base_image, Image.Image):
                logger.warning(f"base_image is not a PIL Image: {type(base_image)}, falling back")
                draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
                return

            icon_width, icon_height = icon_img.size
            paste_x = int(round(x - icon_width // 2))
            paste_y = int(round(y - icon_height // 2))

            # Ensure coordinates are within image bounds
            img_width, img_height = base_image.size
            paste_x = max(0, min(paste_x, img_width - icon_width))
            paste_y = max(0, min(paste_y, img_height - icon_height))

            # Paste the icon with alpha compositing
            if icon_img.mode == 'RGBA':
                # Extract alpha channel for mask
                alpha = icon_img.split()[3]
                base_image.paste(icon_img, (paste_x, paste_y), alpha)
            else:
                base_image.paste(icon_img, (paste_x, paste_y))

        except (AttributeError, Exception) as e:
            logger.warning(f"Could not paste icon image: {e}, falling back to programmatic drawing")
            import traceback
            logger.debug(traceback.format_exc())
            # Fallback: draw a simple circle as placeholder
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
    else:
        # Fallback: draw a simple circle as placeholder
        logger.warning(f"Icon not loaded from {icon_path}")
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
