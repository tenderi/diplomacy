"""
Map generation API routes.

This module contains all endpoints related to map image generation for game states.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
from datetime import datetime

from ..shared import db_service, server
from engine.map import Map
from engine.data_models import MoveOrder, SupportOrder

router = APIRouter()

@router.post("/games/{game_id}/generate_map")
def generate_map_for_snapshot(game_id: str) -> Dict[str, Any]:
    """Generate and save a map image for the current game state"""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    try:
        # Resolve SVG path based on game's map_name
        map_name = getattr(game, 'map_name', 'standard')
        if map_name == 'standard-v2':
            base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
            base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"
            svg_path = os.path.join(base_dir, "v2.svg")
            if not os.path.exists(svg_path):
                svg_path = base_path
        else:
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        render_warnings: list[str] = []
        # Create units dictionary safely
        units = {}
        try:
            for power_name, power in game.game_state.powers.items():
                for unit in power.units:
                    units[f"{unit.unit_type} {unit.province}"] = power_name
        except Exception as e:
            render_warnings.append(f"units_build_failed: {e}")
            units = {}
        # Get phase information
        phase_info = {
            "turn": game.turn,
            "year": game.year,
            "season": game.season,
            "phase": game.phase,
            "phase_code": game.phase_code
        }
        
        # Get supply center control (includes both occupied and unoccupied controlled supply centers)
        supply_center_control = {}
        for power_name, power in game.game_state.powers.items():
            for sc in power.controlled_supply_centers:
                supply_center_control[sc] = power_name
        
        # Try rendering; on failure, fallback to empty-orders map
        try:
            img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info, supply_center_control=supply_center_control)
        except Exception as e:
            render_warnings.append(f"render_failed_primary: {e}")
            img_bytes = Map.render_board_png(svg_path, {}, phase_info={"year": None, "season": None, "phase": None, "phase_code": None}, supply_center_control=None)
        
        # Save map image
        os.makedirs("/tmp/diplomacy_maps", exist_ok=True)
        map_filename = f"game_{game_id}_{game.phase_code}_{int(datetime.now().timestamp())}.png"
        map_path = f"/tmp/diplomacy_maps/{map_filename}"
        
        with open(map_path, 'wb') as f:
            f.write(img_bytes)
        
        # Update the latest snapshot with map path
        latest_snapshot = db_service.get_latest_game_snapshot_by_game_id_and_phase_code(
            game_id=int(game_id),
            phase_code=game.phase_code
        )
        
        if latest_snapshot:
            latest_snapshot.map_image_path = map_path  # type: ignore
            db_service.update_game_snapshot_map_image_path(int(latest_snapshot.id), map_path)  # type: ignore
            db_service.commit()
        
        response: Dict[str, Any] = {
            "status": "ok",
            "map_path": map_path,
            "phase_code": game.phase_code,
            "message": f"Map generated for {game.phase_code}"
        }
        if render_warnings:
            response["render_warnings"] = list(render_warnings)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/generate_map/orders")
def generate_orders_map(game_id: str) -> Dict[str, Any]:
    """Generate and return an orders map showing all submitted orders before adjudication."""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    try:
        # Resolve SVG path based on game's map_name
        map_name = getattr(game, 'map_name', 'standard')
        if map_name == 'standard-v2':
            base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
            base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"
            svg_path = os.path.join(base_dir, "v2.svg")
            if not os.path.exists(svg_path):
                svg_path = base_path
        else:
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        
        # Get units
        units = {}
        for power_name, power in game.game_state.powers.items():
            power_units = []
            for unit in power.units:
                power_units.append(f"{unit.unit_type} {unit.province}")
            if power_units:
                units[power_name] = power_units
        
        # Get orders in visualization format
        orders = {}
        for power_name, order_list in game.game_state.orders.items():
            if order_list:
                orders[power_name] = []
                for order in order_list:
                    # Convert Order object to visualization dict format
                    order_dict = {
                        "type": order.order_type.value.lower() if hasattr(order.order_type, 'value') else str(order.order_type).lower(),
                        "unit": f"{order.unit.unit_type} {order.unit.province}",
                        "status": "pending"
                    }
                    
                    # Add order-specific fields
                    if isinstance(order, MoveOrder) and hasattr(order, 'target_province') and order.target_province:
                        order_dict["target"] = order.target_province
                    if isinstance(order, SupportOrder):
                        if hasattr(order, 'supported_unit') and order.supported_unit:
                            order_dict["supporting"] = f"{order.supported_unit.unit_type} {order.supported_unit.province}"
                            if hasattr(order, 'supported_target') and order.supported_target:
                                order_dict["supporting"] += f" - {order.supported_target}"
                    
                    orders[power_name].append(order_dict)
        
        # Get phase information
        phase_info = {
            "turn": game.turn,
            "year": game.year,
            "season": game.season,
            "phase": game.phase,
            "phase_code": game.phase_code
        }
        
        # Get supply center control
        supply_center_control = {}
        for power_name, power in game.game_state.powers.items():
            for sc in power.controlled_supply_centers:
                supply_center_control[sc] = power_name
        
        # Generate orders map
        img_bytes = Map.render_board_png_orders(
            svg_path, 
            units, 
            orders, 
            phase_info=phase_info, 
            supply_center_control=supply_center_control
        )
        
        # Save to temp location
        os.makedirs("/tmp/diplomacy_maps", exist_ok=True)
        map_filename = f"game_{game_id}_orders_{game.phase_code}_{int(datetime.now().timestamp())}.png"
        map_path = f"/tmp/diplomacy_maps/{map_filename}"
        
        with open(map_path, 'wb') as f:
            f.write(img_bytes)
        
        return {
            "status": "ok",
            "map_path": map_path,
            "phase_code": game.phase_code,
            "message": f"Orders map generated for {game.phase_code}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/generate_map/resolution")
def generate_resolution_map(game_id: str) -> Dict[str, Any]:
    """Generate and return a resolution map showing order results, conflicts, and dislodgements."""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    try:
        # Resolve SVG path based on game's map_name
        map_name = getattr(game, 'map_name', 'standard')
        if map_name == 'standard-v2':
            base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
            base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"
            svg_path = os.path.join(base_dir, "v2.svg")
            if not os.path.exists(svg_path):
                svg_path = base_path
        else:
            svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        
        # Get units
        units = {}
        for power_name, power in game.game_state.powers.items():
            power_units = []
            for unit in power.units:
                power_units.append(f"{unit.unit_type} {unit.province}")
            if power_units:
                units[power_name] = power_units
        
        # Get moves (adjudication results) from order history
        moves = {}
        if hasattr(game, "game_state") and hasattr(game.game_state, "order_history"):
            # Get moves from the last turn's order history
            if game.game_state.order_history:
                last_turn_orders = game.game_state.order_history[-1]
                for power_name, order_list in last_turn_orders.items():
                    if order_list:
                        moves[power_name] = []
                        for order in order_list:
                            if hasattr(order, 'target_province') and order.target_province:
                                moves[power_name].append({
                                    "from": order.unit.province,
                                    "to": order.target_province,
                                    "status": "success" if hasattr(order, 'status') else "pending"
                                })
        
        # Get phase information
        phase_info = {
            "turn": game.turn,
            "year": game.year,
            "season": game.season,
            "phase": game.phase,
            "phase_code": game.phase_code
        }
        
        # Get supply center control
        supply_center_control = {}
        for power_name, power in game.game_state.powers.items():
            for sc in power.controlled_supply_centers:
                supply_center_control[sc] = power_name
        
        # Get orders for resolution visualization
        orders = {}
        for power_name, move_list in moves.items():
            if move_list:
                orders[power_name] = []
                for move in move_list:
                    orders[power_name].append({
                        "type": "move",
                        "unit": f"{move.get('unit_type', 'A')} {move.get('from', '')}",
                        "target": move.get('to', ''),
                        "status": move.get('status', 'success')
                    })
        
        # Create resolution data (simplified - would need proper extraction)
        resolution_data = {
            "conflicts": [],
            "dislodgements": [],
            "order_results": {}
        }
        
        # Generate resolution map
        img_bytes = Map.render_board_png_resolution(
            svg_path,
            units,
            orders,
            resolution_data,
            phase_info=phase_info,
            supply_center_control=supply_center_control
        )
        
        # Save to temp location
        os.makedirs("/tmp/diplomacy_maps", exist_ok=True)
        map_filename = f"game_{game_id}_resolution_{game.phase_code}_{int(datetime.now().timestamp())}.png"
        map_path = f"/tmp/diplomacy_maps/{map_filename}"
        
        with open(map_path, 'wb') as f:
            f.write(img_bytes)
        
        return {
            "status": "ok",
            "map_path": map_path,
            "phase_code": game.phase_code,
            "message": f"Resolution map generated for {game.phase_code}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

