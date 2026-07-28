"""Order-visualization overlay: arrows, support/convoy lines, and status markers
drawn on top of the plain board, plus the two public render entry points that use
them (``render_board_png_orders`` for pre-adjudication orders,
``render_board_png_resolution`` for post-adjudication results).
"""
from __future__ import annotations

import hashlib
import json
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .arrows import (
    _draw_arrow,
    _draw_bounce_arrow,
    _draw_circle,
    _draw_circle_at_size,
    _draw_curved_arrow,
    _draw_failure_x,
    _draw_star,
    _draw_success_checkmark,
    _draw_support_cut_indicator,
)
from .board import (
    _convert_color_to_rgb,
    _get_power_colors_dict,
    get_dislodged_unit_coordinates,
    get_svg_province_coordinates,
    render_board_png,
)
from .cache import _map_cache
from .legend import _draw_legend
from .visualization_config import get_config

_viz_config = get_config()


def _draw_comprehensive_order_visualization(
    draw: ImageDraw.ImageDraw,
    orders: dict,
    coords: dict,
    power_colors: dict,
    units: dict | None = None,
    dislodged_coords: dict[str, tuple[float, float]] | None = None,
) -> None:
    """
    Draw comprehensive order visualization based on orders dictionary format.

    Draws in proper visual layer order: hold -> support -> convoy -> movement (primary actions on top)

    Args:
        draw: PIL ImageDraw object
        orders: Dictionary of power -> list of order dictionaries
        coords: Dictionary of province -> (x, y) coordinates
        power_colors: Dictionary of power -> color
        units: Dictionary of power -> list of units (for finding dislodged unit positions)
        dislodged_coords: Optional dict of province -> SVG DISLODGED_UNIT (x, y) coordinates
    """
    # Separate orders by type for proper layering
    hold_orders = []
    support_orders = []
    convoy_orders = []
    movement_orders = []
    other_orders = []

    for power, power_orders in orders.items():
        color = power_colors.get(power.upper(), "black")

        for order in power_orders:
            order_type = order.get("type", "")
            order_with_context = (order, power, color)

            if order_type == "hold":
                hold_orders.append(order_with_context)
            elif order_type == "support":
                support_orders.append(order_with_context)
            elif order_type == "convoy":
                convoy_orders.append(order_with_context)
            elif order_type == "move":
                movement_orders.append(order_with_context)
            else:
                other_orders.append(order_with_context)

    # Draw in layer order per spec section 3.4.11:
    # 3. Hold indicators
    # 4. Support lines and circles
    # 5. Convoy routes
    # 6. Movement arrows
    # 7. Retreat arrows (in other_orders)
    # Note: Units, Build/Destroy, Conflict markers, Status indicators drawn separately
    for order_list in [hold_orders, support_orders, convoy_orders, movement_orders, other_orders]:
        for order, power, color in order_list:
            order_type = order.get("type", "")
            unit = order.get("unit", "")
            target = order.get("target", "")
            status = order.get("status", "success")

            # Extract province from unit (e.g., "A PAR" -> "PAR")
            unit_province = unit.split()[-1] if unit else ""

            if order_type == "move":
                _draw_movement_order(draw, unit_province, target, color, status, coords)
            elif order_type == "hold":
                _draw_hold_order(draw, unit_province, color, status, coords)
            elif order_type == "support":
                # Extract support order parameters
                supported_action = order.get("supported_action", "hold")
                supported_unit_province = order.get("supported_unit_province", "")
                if not supported_unit_province:
                    # Fallback: try to parse from "supporting" field
                    supporting = order.get("supporting", "")
                    if supporting:
                        supported_unit_province = supporting.split()[-1] if " " in supporting else supporting
                supported_target = order.get("supported_target")
                supporting_power_color = color
                _draw_support_order(draw, unit_province, supported_unit_province,
                                       supported_action, supported_target,
                                       supporting_power_color, status, coords)
            elif order_type == "convoy":
                # Extract convoy order parameters
                convoyed_army_province = order.get("convoyed_army_province", "")
                if not convoyed_army_province:
                    # Fallback: try to parse from "convoyed_unit" field
                    convoyed_unit = order.get("convoyed_unit", "")
                    if convoyed_unit:
                        convoyed_army_province = convoyed_unit.split()[-1] if " " in convoyed_unit else convoyed_unit
                convoy_chain = order.get("convoy_chain", [])
                if not convoy_chain:
                    # Fallback: try to use "via" field
                    convoy_chain = order.get("via", [])
                convoy_color = _viz_config.get_color("convoy")
                _draw_convoy_order(draw, convoyed_army_province, target,
                                     convoy_chain, convoy_color, status, coords)
            elif order_type == "retreat":
                dislodged_unit_position = None
                if dislodged_coords and unit_province in dislodged_coords:
                    dislodged_unit_position = dislodged_coords[unit_province]
                elif unit_province in coords:
                    # Fallback for maps without DISLODGED_UNIT (e.g. v2 map)
                    base_x, base_y = coords[unit_province]
                    unit_specs = _viz_config.get_unit_specs()
                    offset = unit_specs.get("dislodged_offset", [20, 20])
                    dislodged_unit_position = (base_x + offset[0], base_y + offset[1])

                _draw_retreat_order(draw, unit_province, target, color, status, coords, dislodged_unit_position)
            elif order_type == "build":
                _draw_build_order(draw, target, color, status, coords)
            elif order_type == "destroy":
                _draw_destroy_order(draw, unit_province, color, coords)


def _draw_movement_order(draw: ImageDraw.ImageDraw, from_province: str, to_province: str, color: str, status: str, coords: dict) -> None:
    """Draw movement order arrow with status indicators"""
    if from_province not in coords or to_province not in coords:
        return

    from_coord = coords[from_province]
    to_coord = coords[to_province]

    # Get config values
    arrow_specs = _viz_config.get_arrow_specs()
    primary_width = arrow_specs["line_width_primary"]
    secondary_width = arrow_specs["line_width_secondary"]

    # Choose arrow style based on status
    if status == "success" or status == "pending":
        _draw_arrow(draw, from_coord, to_coord, color, width=primary_width, style="solid")
        # Add success checkmark at arrow tip
        if status == "success":
            _draw_success_checkmark(draw, to_coord, "green")
    elif status == "failed":
        _draw_arrow(draw, from_coord, to_coord, "red", width=secondary_width, style="dashed")
        # Add failure X at arrow tip
        _draw_failure_x(draw, to_coord, "red")
    elif status == "bounced":
        # Draw curved return arrow for bounce
        _draw_bounce_arrow(draw, from_coord, to_coord, "orange", width=secondary_width)
        # Add bounce indicator at destination
        _draw_failure_x(draw, to_coord, "orange")


def _draw_hold_order(draw: ImageDraw.ImageDraw, province: str, color: str, status: str, coords: dict) -> None:
    """Draw hold order circle"""
    if province not in coords:
        return

    coord = coords[province]

    # Choose circle style based on status
    if status == "success":
        _draw_circle(draw, coord, color, width=2, style="solid")
    else:
        _draw_circle(draw, coord, "red", width=2, style="dashed")


def _draw_support_order(
    draw: ImageDraw.ImageDraw,
    supporter_province: str,
    supported_unit_province: str,
    supported_action: str,
    supported_target: str | None,
    supporting_power_color: str,
    status: str,
    coords: dict,
) -> None:
    """
    Draw support order with distinct colors for defensive vs offensive support.

    Args:
        draw: PIL ImageDraw object
        supporter_province: Province of the unit providing support
        supported_unit_province: Province of the unit being supported
        supported_action: "hold" for defensive support, "move" for offensive support
        supported_target: Target province (for offensive support only)
        supporting_power_color: Power color of supporting unit (for defender circle)
        status: Order status ("success", "failed", etc.)
        coords: Dictionary mapping province names to (x, y) coordinates
    """
    if supporter_province not in coords or supported_unit_province not in coords:
        return

    supporter_coord = coords[supporter_province]
    supported_coord = coords[supported_unit_province]

    if supported_action == "hold":
        # Defensive Support (Hold Support) - spec section 3.4.4
        arrow_specs = _viz_config.get_arrow_specs()
        marker_specs = _viz_config.get_marker_specs()
        support_color = _viz_config.get_color("support_defensive") if status == "success" else _viz_config.get_color("failure")

        # Draw dashed line from supporter to defending unit (light green)
        _draw_arrow(draw, supporter_coord, supported_coord, support_color,
                      width=arrow_specs["line_width_secondary"], style="dashed")

        # Draw circle around defending unit in supporting unit's power color
        if status == "success":
            circle_diameter = marker_specs["support_circle_diameter"]
            circle_border_width = marker_specs["support_circle_border_width"]
            _draw_circle_at_size(draw, supported_coord, supporting_power_color,
                                   circle_diameter, circle_border_width, style="solid")

        # Add red X through support line if cut
        if status != "success":
            _draw_support_cut_indicator(draw, supporter_coord, supported_coord)

    elif supported_action == "move" and supported_target:
        # Offensive Support (Move Support) - spec section 3.4.4
        arrow_specs = _viz_config.get_arrow_specs()
        support_color = _viz_config.get_color("support_offensive") if status == "success" else _viz_config.get_color("failure")

        if supported_target in coords:
            target_coord = coords[supported_target]

            # Draw dashed arrow path: supporter -> supported unit -> attack target
            # First segment: supporter to supported unit
            _draw_arrow(draw, supporter_coord, supported_coord, support_color,
                         width=arrow_specs["line_width_secondary"], style="dashed")
            # Second segment: supported unit to target
            _draw_arrow(draw, supported_coord, target_coord, support_color,
                         width=arrow_specs["line_width_secondary"], style="dashed")

            # Add red X through support line if cut
            if status != "success":
                _draw_support_cut_indicator(draw, supporter_coord, supported_coord)
                if supported_target in coords:
                    _draw_support_cut_indicator(draw, supported_coord, target_coord)


def _draw_convoy_order(
    draw: ImageDraw.ImageDraw,
    convoyed_army_province: str,
    convoyed_to: str,
    convoy_chain: list[str],
    convoy_color: str,
    status: str,
    coords: dict,
) -> None:
    """
    Draw convoy order per spec section 3.4.5.

    Curved path (bezier) from army through all fleets to destination.
    Gold/orange color, solid line, circles around convoying fleets, arrowhead at destination.
    """
    if convoyed_army_province not in coords or convoyed_to not in coords:
        return

    arrow_specs = _viz_config.get_arrow_specs()
    marker_specs = _viz_config.get_marker_specs()
    convoy_color_actual = convoy_color if status == "success" else _viz_config.get_color("failure")

    # Build complete path: army -> fleet1 -> fleet2 -> ... -> destination
    path = [convoyed_army_province]
    path.extend(convoy_chain)
    path.append(convoyed_to)

    # Draw curved arrows connecting each segment of the path
    for i in range(len(path) - 1):
        from_prov = path[i]
        to_prov = path[i + 1]

        if from_prov not in coords or to_prov not in coords:
            continue

        from_coord = coords[from_prov]
        to_coord = coords[to_prov]

        # Draw curved arrow segment using config line width
        _draw_curved_arrow(draw, from_coord, to_coord, convoy_color_actual,
                              width=arrow_specs["line_width_secondary"],
                              style="solid" if status == "success" else "dashed")

    # Draw circles/markers around convoying fleets in convoy color (per spec)
    fleet_marker_diameter = marker_specs["convoy_fleet_marker_diameter"]
    fleet_marker_border_width = marker_specs["convoy_fleet_marker_border_width"]
    for fleet_prov in convoy_chain:
        if fleet_prov in coords:
            fleet_coord = coords[fleet_prov]
            _draw_circle_at_size(draw, fleet_coord, convoy_color_actual,
                                   fleet_marker_diameter, fleet_marker_border_width, style="solid")


def _draw_build_order(draw: ImageDraw.ImageDraw, province: str, color: str, status: str, coords: dict) -> None:
    """
    Draw build marker per spec section 3.4.7.

    Green circle with plus sign or "A"/"F" label, power-colored border.
    """
    if province not in coords:
        return

    marker_specs = _viz_config.get_marker_specs()
    marker_diameter = marker_specs["build_marker_diameter"]
    border_width = marker_specs["build_marker_border_width"]
    r = marker_diameter // 2

    x, y = coords[province]
    build_color = _viz_config.get_color("success")
    rgb_build_color = _convert_color_to_rgb(build_color)
    rgb_border_color = _convert_color_to_rgb(color)

    # Draw green circle with power-colored border
    draw.ellipse((x - r, y - r, x + r, y + r), fill=rgb_build_color,
                outline=rgb_border_color, width=border_width)

    # Draw plus sign or unit type label (for now, use plus sign)
    plus_size = marker_diameter // 2
    # Horizontal line
    draw.line([x - plus_size//2, y, x + plus_size//2, y],
             fill="white", width=border_width)
    # Vertical line
    draw.line([x, y - plus_size//2, x, y + plus_size//2],
             fill="white", width=border_width)


def _draw_destroy_order(draw: ImageDraw.ImageDraw, province: str, color: str, coords: dict) -> None:
    """
    Draw destroy marker per spec section 3.4.8.

    Red circle with X symbol, power-colored border.
    """
    if province not in coords:
        return

    marker_specs = _viz_config.get_marker_specs()
    marker_diameter = marker_specs["destroy_marker_diameter"]
    border_width = marker_specs["destroy_marker_border_width"]
    r = marker_diameter // 2

    x, y = coords[province]
    destroy_color = _viz_config.get_color("failure")
    rgb_destroy_color = _convert_color_to_rgb(destroy_color)
    rgb_border_color = _convert_color_to_rgb(color)

    # Draw red circle with power-colored border
    draw.ellipse((x - r, y - r, x + r, y + r), fill=rgb_destroy_color,
                outline=rgb_border_color, width=border_width)

    # Draw X symbol
    x_size = marker_diameter // 2
    x_line_width = border_width
    rgb_white = (255, 255, 255)
    draw.line([x - x_size, y - x_size, x + x_size, y + x_size],
             fill=rgb_white, width=x_line_width)
    draw.line([x - x_size, y + x_size, x + x_size, y - x_size],
             fill=rgb_white, width=x_line_width)


def _draw_retreat_order(
    draw: ImageDraw.ImageDraw,
    from_province: str,
    to_province: str,
    color: str,
    status: str,
    coords: dict,
    dislodged_unit_position: tuple | None = None,
) -> None:
    """
    Draw retreat order per spec section 3.4.6.

    Dotted arrow, red if invalid retreat. Uses unified arrow function.
    Retreat orders ALWAYS start from dislodged unit position (offset from province center).
    """
    if to_province not in coords:
        return

    # Retreat orders are always for dislodged units, so always use offset position
    if dislodged_unit_position:
        from_coord = dislodged_unit_position
    elif from_province in coords:
        # Fallback: calculate offset position if not provided
        base_x, base_y = coords[from_province]
        unit_specs = _viz_config.get_unit_specs()
        dislodged_offset = unit_specs.get("dislodged_offset", [20, 20])
        from_coord = (base_x + dislodged_offset[0], base_y + dislodged_offset[1])
    else:
        return  # Can't draw without starting position

    to_coord = coords[to_province]

    # Use dotted line style for retreat, red if invalid
    arrow_specs = _viz_config.get_arrow_specs()
    retreat_color = _viz_config.get_color("failure") if status == "failed" else color
    arrow_status = "failure" if status == "failed" else None

    # Use unified arrow function with dotted style
    _draw_arrow(draw, from_coord, to_coord, retreat_color,
               width=arrow_specs["line_width_secondary"],
               style="dotted", status=arrow_status)


def _draw_conflict_marker(draw: ImageDraw.ImageDraw, province: str, strengths: dict, result: str, coords: dict) -> None:
    """
    Draw battle indicator per spec section 3.4.9.

    Star/shield symbol, red/orange color, optional strength label.
    """
    if province not in coords:
        return

    coord = coords[province]
    x, y = coord

    marker_specs = _viz_config.get_marker_specs()
    marker_size = marker_specs["battle_indicator_size"]
    battle_color = _viz_config.get_color("failure")  # Red for battles

    # Draw conflict marker (star or special symbol)
    _draw_star(draw, (x, y), marker_size, battle_color, "yellow")

    # Add strength indicator if available
    if strengths:
        max_strength = max(strengths.values())
        font_specs = _viz_config.get_font_specs()
        font_size = font_specs["conflict_label_size"]
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        draw.text((x + marker_size + 5, y - 10), str(max_strength), fill="black", font=font)


def _draw_standoff_indicator(draw: ImageDraw.ImageDraw, province: str, coords: dict) -> None:
    """
    Draw standoff indicator per spec section 3.4.9.

    Equal sign or balanced scales symbol, yellow/orange color.
    """
    if province not in coords:
        return

    coord = coords[province]
    x, y = coord

    marker_specs = _viz_config.get_marker_specs()
    marker_size = marker_specs["standoff_indicator_size"]
    border_width = marker_specs["standoff_indicator_border_width"]
    standoff_color = _viz_config.get_color("convoy")  # Use convoy color (gold/yellow) for standoff
    rgb_standoff_color = _convert_color_to_rgb(standoff_color)

    # Draw special standoff marker (circle with equal sign)
    radius = marker_size // 2
    draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                outline=rgb_standoff_color, width=border_width)
    # Draw equal sign
    line_length = radius - 2
    draw.line([x - line_length, y - 3, x + line_length, y - 3],
             fill=rgb_standoff_color, width=border_width)
    draw.line([x - line_length, y + 3, x + line_length, y + 3],
             fill=rgb_standoff_color, width=border_width)



def render_board_png_orders(
    svg_path: str,
    units: dict,
    orders: dict,
    phase_info: dict | None = None,
    output_path: str | None = None,
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> bytes:
    """
    Render orders map PNG showing all submitted orders before adjudication.

    All orders are drawn with status "pending" regardless of what's passed in
    ``orders``, since this map type shows orders before adjudication.

    Merged during the V3 rendering split: this used to be a thin wrapper that
    forced ``status="pending"`` and then delegated to a separate
    ``render_board_png_with_orders`` (the function that did the actual caching,
    base render, and overlay drawing). That split served no purpose once both
    lived in the same module, so the two are now one function under this name --
    the one every caller (the orders-map API route) already used.

    Args:
        svg_path: Path to SVG map file
        units: Dictionary of power -> list of units
        orders: Dictionary of power -> list of order dictionaries (with status="pending")
        phase_info: Dictionary with turn/season/phase information
        output_path: Optional output file path
        supply_center_control: Dictionary of province -> power controlling supply center
        color_only_supply_centers: If True, only color supply center provinces

    Returns:
        PNG image bytes
    """
    if svg_path is None:
        raise ValueError("svg_path must not be None")

    # Ensure all orders have status="pending" for orders map
    pending_orders: dict[str, list] = {}
    for power, power_orders in orders.items():
        pending_orders[power] = []
        for order in power_orders:
            order_copy = order.copy()
            order_copy["status"] = "pending"  # Orders map shows pending status
            pending_orders[power].append(order_copy)

    # Generate cache key for this map configuration with orders
    cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info, orders=pending_orders)

    # Try to get from cache first
    cached_img = _map_cache.get(cache_key)
    if cached_img is not None:
        # Cache hit - return cached image
        if isinstance(output_path, str) and output_path:
            with open(output_path, 'wb') as f:
                f.write(cached_img)
        return cached_img

    # Cache miss - generate new map
    # First render the base map
    base_img_bytes = render_board_png(svg_path, units, output_path, phase_info=phase_info, supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers)
    bg = Image.open(BytesIO(base_img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # Get province coordinates for order visualization
    coords = get_svg_province_coordinates(svg_path)
    dislodged_coords = get_dislodged_unit_coordinates(svg_path)

    # Get power colors from config
    power_colors = _get_power_colors_dict()

    # Draw order visualizations
    _draw_comprehensive_order_visualization(draw, pending_orders, coords, power_colors, units, dislodged_coords)

    # Add orders legend
    active_powers = list(units.keys())
    _draw_legend(bg, "orders", active_powers)

    # Save or return PNG
    if isinstance(output_path, str) and output_path:
        bg.save(output_path, format="PNG")
    output = BytesIO()
    bg.save(output, format="PNG")
    img_bytes = output.getvalue()

    # Cache the generated image
    _map_cache.put(cache_key, img_bytes)

    return img_bytes


def render_board_png_resolution(
    svg_path: str,
    units: dict,
    orders: dict,
    resolution_data: dict,
    phase_info: dict | None = None,
    output_path: str | None = None,
    supply_center_control: dict | None = None,
    color_only_supply_centers: bool = False,
) -> bytes:
    """
    Render resolution map PNG showing order results, conflicts, and dislodgements after adjudication.

    Args:
        svg_path: Path to SVG map file
        units: Dictionary of power -> list of units (after adjudication, includes dislodged units)
        orders: Dictionary of power -> list of order dictionaries (with final status)
        resolution_data: Dictionary containing conflict and resolution information:
            {
                "conflicts": [
                    {
                        "province": "BUR",
                        "attackers": ["FRANCE", "GERMANY"],
                        "defender": "AUSTRIA",
                        "strengths": {"FRANCE": 2, "GERMANY": 1, "AUSTRIA": 1},
                        "result": "standoff|victory|bounce"
                    }
                ],
                "dislodgements": [
                    {
                        "unit": "A BUR",
                        "dislodged_by": "A PAR",
                        "retreat_options": ["BEL", "PIC"]
                    }
                ]
            }
        phase_info: Dictionary with turn/season/phase information
        output_path: Optional output file path
        supply_center_control: Dictionary of province -> power controlling supply center

    Returns:
        PNG image bytes
    """
    if svg_path is None:
        raise ValueError("svg_path must not be None")

    # Generate cache key including resolution data
    cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info, orders=orders)
    cache_key += hashlib.md5(json.dumps(resolution_data, sort_keys=True).encode()).hexdigest()[:8]

    # Try to get from cache first
    cached_img = _map_cache.get(cache_key)
    if cached_img is not None:
        if isinstance(output_path, str) and output_path:
            with open(output_path, 'wb') as f:
                f.write(cached_img)
        return cached_img

    # Cache miss - generate new map
    # First render the base map with final unit positions (including dislodged units)
    base_img_bytes = render_board_png(svg_path, units, output_path, phase_info=phase_info, supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers)
    bg = Image.open(BytesIO(base_img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # Get province coordinates
    coords = get_svg_province_coordinates(svg_path)
    dislodged_coords = get_dislodged_unit_coordinates(svg_path)

    # Get power colors from config
    power_colors = _get_power_colors_dict()

    # Draw order visualizations with status indicators
    _draw_comprehensive_order_visualization(draw, orders, coords, power_colors, units, dislodged_coords)

    # Draw conflict markers
    conflicts = resolution_data.get("conflicts", [])
    for conflict in conflicts:
        province = conflict.get("province")
        strengths = conflict.get("strengths", {})
        result = conflict.get("result", "")

        if result == "standoff":
            _draw_standoff_indicator(draw, province, coords)
        else:
            _draw_conflict_marker(draw, province, strengths, result, coords)

    # Note: Dislodged units are already drawn by render_board_png with offset and D marker

    # Add resolution legend
    active_powers = list(units.keys())
    _draw_legend(bg, "resolution", active_powers)

    # Save or return PNG
    if isinstance(output_path, str) and output_path:
        bg.save(output_path, format="PNG")
    output = BytesIO()
    bg.save(output, format="PNG")
    img_bytes = output.getvalue()

    # Cache the generated image
    _map_cache.put(cache_key, img_bytes)

    return img_bytes
