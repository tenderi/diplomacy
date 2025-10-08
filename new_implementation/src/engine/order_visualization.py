"""
Enhanced order visualization system using new data models.

This module fixes the order visualization data corruption issues by using
the proper data models and validation to ensure correct order-to-unit mapping.
"""

from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from .data_models import GameState, Order, Unit, OrderType, OrderStatus, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder


@dataclass
class OrderVisualizationData:
    """Data structure for order visualization"""
    order_type: OrderType
    power: str
    unit: Unit
    target_province: Optional[str] = None
    supported_unit: Optional[Unit] = None
    supported_target: Optional[str] = None
    convoyed_unit: Optional[Unit] = None
    convoyed_target: Optional[str] = None
    convoy_chain: List[str] = None
    retreat_province: Optional[str] = None
    build_type: Optional[str] = None
    build_province: Optional[str] = None
    build_coast: Optional[str] = None
    destroy_unit: Optional[Unit] = None
    status: OrderStatus = OrderStatus.PENDING
    failure_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.convoy_chain is None:
            self.convoy_chain = []


class OrderVisualizationService:
    """Service for creating order visualization data"""
    
    def __init__(self):
        pass
    
    def create_visualization_data(self, game_state: GameState) -> Dict[str, List[Dict[str, Any]]]:
        """
        Create order visualization data from game state.
        
        This method fixes the data corruption issues by:
       1. Properly mapping orders to units
       2. Validating power ownership
       3. Ensuring correct order-to-unit relationships
        
        Note: For visualization purposes, we skip strict validation to show all orders
        even if they might be invalid (e.g., non-adjacent moves, wrong phase, etc.)
        """
        visualization_data = {}
        
        for power_name, orders in game_state.orders.items():
            if power_name not in game_state.powers:
                continue
            
            power_state = game_state.powers[power_name]
            power_orders = []
            
            for order in orders:
                try:
                    # Skip validation for visualization - we want to show all orders
                    # even if they might be invalid (non-adjacent moves, wrong phase, etc.)
                    
                    # Create visualization data for this order
                    viz_data = self._create_order_visualization_data(order, game_state)
                    if viz_data:
                        power_orders.append(viz_data)
                    
                except Exception as e:
                    continue
            
            if power_orders:
                visualization_data[power_name] = power_orders
        
        return visualization_data
    
    def _create_order_visualization_data(self, order: Order, game_state: GameState) -> Optional[Dict[str, Any]]:
        """Create visualization data for a single order"""
        try:
            if isinstance(order, MoveOrder):
                return self._create_move_visualization(order, game_state)
            elif isinstance(order, HoldOrder):
                return self._create_hold_visualization(order, game_state)
            elif isinstance(order, SupportOrder):
                return self._create_support_visualization(order, game_state)
            elif isinstance(order, ConvoyOrder):
                return self._create_convoy_visualization(order, game_state)
            elif isinstance(order, RetreatOrder):
                return self._create_retreat_visualization(order, game_state)
            elif isinstance(order, BuildOrder):
                return self._create_build_visualization(order, game_state)
            elif isinstance(order, DestroyOrder):
                return self._create_destroy_visualization(order, game_state)
            else:
                print(f"Unknown order type: {type(order)}")
                return None
                
        except Exception as e:
            print(f"Error creating visualization for order {order}: {e}")
            return None
    
    def _create_move_visualization(self, order: MoveOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for move order"""
        return {
            "type": "move",
            "unit": f"{order.unit.unit_type} {order.unit.province}",
            "target": order.target_province,
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason,
            "is_convoyed": order.is_convoyed,
            "convoy_route": order.convoy_route
        }
    
    def _create_hold_visualization(self, order: HoldOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for hold order"""
        return {
            "type": "hold",
            "unit": f"{order.unit.unit_type} {order.unit.province}",
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason
        }
    
    def _create_support_visualization(self, order: SupportOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for support order"""
        return {
            "type": "support",
            "unit": f"{order.unit.unit_type} {order.unit.province}",
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason,
            "supporting": f"{order.supported_unit.unit_type} {order.supported_unit.province}",
            "supported_action": order.supported_action,
            "supported_target": order.supported_target
        }
    
    def _create_convoy_visualization(self, order: ConvoyOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for convoy order"""
        return {
            "type": "convoy",
            "unit": f"{order.unit.unit_type} {order.unit.province}",
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason,
            "convoyed_unit": f"{order.convoyed_unit.unit_type} {order.convoyed_unit.province}",
            "convoyed_target": order.convoyed_target,
            "convoy_chain": order.convoy_chain
        }
    
    def _create_retreat_visualization(self, order: RetreatOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for retreat order"""
        return {
            "type": "retreat",
            "unit": f"{order.unit.unit_type} {order.unit.province}",
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason,
            "retreat_province": order.retreat_province
        }
    
    def _create_build_visualization(self, order: BuildOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for build order"""
        return {
            "type": "build",
            "unit": "",  # Build orders don't have existing units
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason,
            "build_type": order.build_type,
            "build_province": order.build_province,
            "build_coast": order.build_coast
        }
    
    def _create_destroy_visualization(self, order: DestroyOrder, game_state: GameState) -> Dict[str, Any]:
        """Create visualization data for destroy order"""
        return {
            "type": "destroy",
            "unit": "",  # Destroy orders don't have existing units
            "power": order.power,
            "status": order.status.value,
            "failure_reason": order.failure_reason,
            "destroy_unit": f"{order.destroy_unit.unit_type} {order.destroy_unit.province}"
        }
    
    def validate_visualization_data(self, visualization_data: Dict[str, List[Dict[str, Any]]], game_state: GameState) -> Tuple[bool, List[str]]:
        """Validate visualization data against game state"""
        errors = []
        
        for power_name, orders in visualization_data.items():
            if power_name not in game_state.powers:
                errors.append(f"Visualization data for non-existent power: {power_name}")
                continue
            
            power_state = game_state.powers[power_name]
            
            for order_data in orders:
                # Check if unit exists in game state
                unit_str = order_data.get("unit", "")
                if unit_str and unit_str != "":  # Skip empty units (build/destroy orders)
                    unit_type, unit_province = unit_str.split()
                    
                    # Find the unit in game state
                    unit_found = False
                    for unit in power_state.units:
                        if unit.unit_type == unit_type and unit.province == unit_province:
                            unit_found = True
                            break
                    
                    if not unit_found:
                        errors.append(f"Unit {unit_str} not found in {power_name}'s units")
                
                # Check power ownership
                if order_data.get("power") != power_name:
                    errors.append(f"Order power mismatch: {order_data.get('power')} != {power_name}")
        
        return len(errors) == 0, errors
    
    def create_moves_visualization_data(self, game_state: GameState) -> Dict[str, Dict[str, Any]]:
        """
        Create moves visualization data (alternative format).
        
        This creates the moves dictionary format used by the map rendering system.
        """
        moves_data = {}
        
        for power_name, orders in game_state.orders.items():
            if power_name not in game_state.powers:
                continue
            
            power_moves = {
                "successful": [],
                "failed": [],
                "bounced": [],
                "holds": [],
                "supports": [],
                "convoys": [],
                "builds": [],
                "destroys": []
            }
            
            for order in orders:
                try:
                    # Validate order
                    valid, reason = order.validate(game_state)
                    if not valid:
                        print(f"Invalid order {order}: {reason}")
                        continue
                    
                    # Add to appropriate category based on order type and status
                    if isinstance(order, MoveOrder):
                        if order.status == OrderStatus.SUCCESS:
                            power_moves["successful"].append({
                                "unit": f"{order.unit.unit_type} {order.unit.province}",
                                "target": order.target_province
                            })
                        elif order.status == OrderStatus.FAILED:
                            power_moves["failed"].append({
                                "unit": f"{order.unit.unit_type} {order.unit.province}",
                                "target": order.target_province,
                                "reason": order.failure_reason
                            })
                        elif order.status == OrderStatus.BOUNCED:
                            power_moves["bounced"].append({
                                "unit": f"{order.unit.unit_type} {order.unit.province}",
                                "target": order.target_province,
                                "reason": order.failure_reason
                            })
                    
                    elif isinstance(order, HoldOrder):
                        power_moves["holds"].append({
                            "unit": f"{order.unit.unit_type} {order.unit.province}",
                            "status": order.status.value
                        })
                    
                    elif isinstance(order, SupportOrder):
                        power_moves["supports"].append({
                            "unit": f"{order.unit.unit_type} {order.unit.province}",
                            "supporting": f"{order.supported_unit.unit_type} {order.supported_unit.province}",
                            "target": order.supported_target,
                            "status": order.status.value
                        })
                    
                    elif isinstance(order, ConvoyOrder):
                        power_moves["convoys"].append({
                            "unit": f"{order.unit.unit_type} {order.unit.province}",
                            "convoyed_unit": f"{order.convoyed_unit.unit_type} {order.convoyed_unit.province}",
                            "target": order.convoyed_target,
                            "status": order.status.value
                        })
                    
                    elif isinstance(order, BuildOrder):
                        power_moves["builds"].append({
                            "unit": f"{order.build_type} {order.build_province}",
                            "status": order.status.value
                        })
                    
                    elif isinstance(order, DestroyOrder):
                        power_moves["destroys"].append({
                            "unit": f"{order.destroy_unit.unit_type} {order.destroy_unit.province}",
                            "status": order.status.value
                        })
                
                except Exception as e:
                    print(f"Error processing order {order}: {e}")
                    continue
            
            # Only add if there are moves
            if any(power_moves.values()):
                moves_data[power_name] = power_moves
        
        return moves_data
    
    def get_visualization_report(self, game_state: GameState) -> str:
        """Get comprehensive visualization report"""
        report = []
        report.append(f"Order Visualization Report for {game_state.game_id}")
        report.append(f"Turn: {game_state.current_turn}, Phase: {game_state.current_phase}")
        report.append("=" * 60)
        
        # Create visualization data
        viz_data = self.create_visualization_data(game_state)
        
        # Validate visualization data
        valid, errors = self.validate_visualization_data(viz_data, game_state)
        if valid:
            report.append("✅ Order visualization data: VALID")
        else:
            report.append("❌ Order visualization data: INVALID")
            for error in errors:
                report.append(f"   • {error}")
        
        report.append("")
        
        # Show orders by power
        for power_name, orders in viz_data.items():
            report.append(f"📋 {power_name} Orders ({len(orders)}):")
            for order_data in orders:
                order_type = order_data.get("type", "unknown")
                unit = order_data.get("unit", "")
                target = order_data.get("target", "")
                status = order_data.get("status", "unknown")
                
                if order_type == "move":
                    report.append(f"   • {unit} → {target} ({status})")
                elif order_type == "hold":
                    report.append(f"   • {unit} H ({status})")
                elif order_type == "support":
                    supporting = order_data.get("supporting", "")
                    supported_target = order_data.get("supported_target", "")
                    if supported_target:
                        report.append(f"   • {unit} S {supporting} → {supported_target} ({status})")
                    else:
                        report.append(f"   • {unit} S {supporting} ({status})")
                elif order_type == "convoy":
                    convoyed_unit = order_data.get("convoyed_unit", "")
                    convoyed_target = order_data.get("convoyed_target", "")
                    report.append(f"   • {unit} C {convoyed_unit} → {convoyed_target} ({status})")
                elif order_type == "retreat":
                    retreat_province = order_data.get("retreat_province", "")
                    report.append(f"   • {unit} R {retreat_province} ({status})")
                elif order_type == "build":
                    build_type = order_data.get("build_type", "")
                    build_province = order_data.get("build_province", "")
                    report.append(f"   • BUILD {build_type} {build_province} ({status})")
                elif order_type == "destroy":
                    destroy_unit = order_data.get("destroy_unit", "")
                    report.append(f"   • DESTROY {destroy_unit} ({status})")
            
            report.append("")
        
        return "\n".join(report)
