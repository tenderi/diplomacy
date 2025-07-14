from typing import Dict, List, Any
from engine.map import Map
from engine.power import Power
from engine.order import OrderParser, Order

class Game:
    """Main class for managing the game state, phases, and turn processing."""
    def __init__(self, map_name: str = 'standard') -> None:
        self.map_name: str = map_name
        self.map: Map = Map()  # Use Map for board representation
        self.powers: Dict[str, Power] = {}
        self.orders: Dict[str, List[str]] = {}
        self.turn: int = 0
        self.done: bool = False

    def add_player(self, power_name: str) -> None:
        if power_name not in self.powers:
            # For now, assign all supply centers as home centers for demo
            self.powers[power_name] = Power(power_name, list(self.map.get_supply_centers()))

    def set_orders(self, power_name: str, orders: List[str]) -> None:
        self.orders[power_name] = orders

    def process_turn(self) -> None:
        """Process all orders for the current turn using Diplomacy rules (move/hold/support + supply center control)."""
        # 1. Parse and validate all orders
        parsed_orders: Dict[str, List[Order]] = {}
        for power, order_strs in self.orders.items():
            parsed_orders[power] = []
            for order_str in order_strs:
                try:
                    order = OrderParser.parse(order_str)
                    if not OrderParser.validate(order, self.get_state()):
                        continue  # Skip invalid orders
                    parsed_orders[power].append(order)
                except Exception:
                    continue  # Skip invalid orders

        # 2. Collect current unit positions and map orders to actual units
        unit_positions: Dict[str, str] = {}  # full unit identifier -> location
        unit_to_power: Dict[str, str] = {}   # full unit identifier -> power
        
        # Build a mapping from order unit identifiers to actual units
        for power, p in self.powers.items():
            for location in p.units:
                # For each location, find matching orders to determine unit type
                for orders in parsed_orders.values():
                    for order in orders:
                        unit_parts = order.unit.split()
                        if len(unit_parts) == 2 and unit_parts[1] == location:
                            # This order references a unit at this location
                            unit_positions[order.unit] = location
                            unit_to_power[order.unit] = power

        # 3. Parse orders into structured data
        moves: Dict[str, str] = {}  # unit -> destination
        supports: Dict[str, List[str]] = {}  # supported move -> list of supporting units
        convoys: Dict[str, str] = {}  # convoyed unit -> convoy path
        convoy_orders: Dict[str, str] = {}  # fleet -> move being convoyed

        for power, orders in parsed_orders.items():
            for order in orders:
                if order.action == '-' and order.target is not None:
                    # Move order
                    target = order.target.replace(' VIA CONVOY', '')
                    moves[order.unit] = target
                    
                    # Check if this is a convoyed move
                    if 'VIA CONVOY' in order.target:
                        convoys[order.unit] = target
                        
                elif order.action == 'S' and order.target:
                    # Support order
                    if order.target not in supports:
                        supports[order.target] = []
                    supports[order.target].append(order.unit)
                    
                elif order.action == 'C' and order.target:
                    # Convoy order
                    convoy_orders[order.unit] = order.target

        # --- ITERATIVE ADJUDICATION FOR SUPPORT CUT BY DISLODGEMENT ---
        # We need to iteratively resolve orders until no more changes occur
        # This handles support cut by dislodgement correctly
        
        # Initialize with empty state
        successful_moves: Dict[str, str] = {}
        failed_moves: set[str] = set()
        move_strength: Dict[str, int] = {}
        
        max_iterations = 10  # Prevent infinite loops
        for _ in range(max_iterations):
            # Calculate move strengths based on current state
            new_move_strength: Dict[str, int] = {}
            
            # Calculate which units would be dislodged with current move resolutions
            would_be_dislodged: set[str] = set()
            for move_unit, destination in moves.items():
                # Check if this move would be successful
                competitors = [u for u, d in moves.items() if d == destination and u != move_unit]
                unit_strength = move_strength.get(move_unit, 1)
                
                # Check against competitors
                beats_all_competitors = True
                for competitor in competitors:
                    competitor_strength = move_strength.get(competitor, 1)
                    if competitor_strength >= unit_strength:
                        beats_all_competitors = False
                        break
                
                # Check against defender
                defending_unit = None
                for unit, location in unit_positions.items():
                    if location == destination and unit != move_unit:
                        defending_unit = unit
                        break
                
                if defending_unit and defending_unit not in moves:
                    # Calculate defensive strength (will be recalculated below)
                    defend_strength = 1
                    if unit_strength <= defend_strength:
                        beats_all_competitors = False
                
                # If this move would succeed, mark defender as dislodged
                if beats_all_competitors and defending_unit and defending_unit not in moves:
                    would_be_dislodged.add(defending_unit)
            
            # Now calculate strengths, excluding support from units that would be dislodged
            for move_unit, destination in moves.items():
                strength = 1
                move_string = f"{move_unit} - {destination}"
                if move_string in supports:
                    for supporting_unit in supports[move_string]:
                        # Don't count support from units that would be dislodged
                        if supporting_unit in would_be_dislodged:
                            continue
                        
                        # Check if support is cut by attack on supporting unit
                        support_cut = False
                        supporting_location = unit_positions.get(supporting_unit)
                        if supporting_location:
                            for other_unit, other_dest in moves.items():
                                if other_dest == supporting_location and other_unit != move_unit:
                                    support_cut = True
                                    break
                        
                        if not support_cut:
                            strength += 1
                new_move_strength[move_unit] = strength
            
            # Now recalculate defensive strengths with updated move strengths
            for move_unit, destination in moves.items():
                defending_unit = None
                for unit, location in unit_positions.items():
                    if location == destination and unit != move_unit:
                        defending_unit = unit
                        break
                
                if defending_unit and defending_unit not in moves:
                    defend_string = f"{defending_unit} H"
                    defend_strength = 1
                    if defend_string in supports:
                        for supporting_unit in supports[defend_string]:
                            # Don't count support from units that would be dislodged
                            if supporting_unit in would_be_dislodged:
                                continue
                            
                            # Check if defensive support is cut
                            support_cut = False
                            supporting_location = unit_positions.get(supporting_unit)
                            if supporting_location:
                                for other_unit, other_dest in moves.items():
                                    if other_dest == supporting_location and other_unit != defending_unit:
                                        support_cut = True
                                        break
                            if not support_cut:
                                defend_strength += 1
                    
                    # Update move strength if it can't beat the defender
                    unit_strength = new_move_strength.get(move_unit, 1)
                    if unit_strength <= defend_strength:
                        # This move would fail, so don't count it as successful
                        if defending_unit in would_be_dislodged:
                            would_be_dislodged.remove(defending_unit)
            
            # Resolve moves based on calculated strengths
            new_successful_moves: Dict[str, str] = {}
            new_failed_moves: set[str] = set()
            
            for move_unit, destination in moves.items():
                # Check for convoy disruption
                if move_unit in convoys:
                    convoying_fleets = [fleet for fleet, convoyed in convoy_orders.items() if convoyed == f"{move_unit} - {destination}"]
                    convoy_disrupted = False
                    for fleet in convoying_fleets:
                        if fleet in would_be_dislodged:
                            convoy_disrupted = True
                            break
                    if convoy_disrupted:
                        new_failed_moves.add(move_unit)
                        continue
                
                # Check against other moves to same destination
                competitors = [u for u, d in moves.items() if d == destination and u != move_unit]
                unit_strength = new_move_strength.get(move_unit, 1)
                beats_all = True
                
                for competitor in competitors:
                    competitor_strength = new_move_strength.get(competitor, 1)
                    if competitor_strength >= unit_strength:
                        beats_all = False
                        break
                
                # Check against defending unit
                defending_unit = None
                for unit, location in unit_positions.items():
                    if location == destination and unit != move_unit:
                        defending_unit = unit
                        break
                
                if defending_unit and defending_unit not in moves:
                    defend_string = f"{defending_unit} H"
                    defend_strength = 1
                    if defend_string in supports:
                        for supporting_unit in supports[defend_string]:
                            # Don't count support from units that would be dislodged
                            if supporting_unit in would_be_dislodged:
                                continue
                            
                            # Check if defensive support is cut
                            support_cut = False
                            supporting_location = unit_positions.get(supporting_unit)
                            if supporting_location:
                                for other_unit, other_dest in moves.items():
                                    if other_dest == supporting_location and other_unit != defending_unit:
                                        support_cut = True
                                        break
                            if not support_cut:
                                defend_strength += 1
                    if unit_strength <= defend_strength:
                        beats_all = False
                
                if beats_all:
                    new_successful_moves[move_unit] = destination
                else:
                    new_failed_moves.add(move_unit)
            
            # Check if we've reached a stable state
            if new_successful_moves == successful_moves and new_failed_moves == failed_moves and new_move_strength == move_strength:
                break
            
            successful_moves = new_successful_moves
            failed_moves = new_failed_moves
            move_strength = new_move_strength
        
        # Calculate final dislodged units
        dislodged_units: set[str] = set()
        for move_unit, destination in successful_moves.items():
            for unit, location in unit_positions.items():
                if location == destination and unit != move_unit and unit not in moves:
                    dislodged_units.add(unit)

        # 6. Update unit positions
        for power in self.powers.values():
            power.units = set()
        for unit, current_location in unit_positions.items():
            power = unit_to_power[unit]
            if unit in successful_moves:
                new_location = successful_moves[unit]
                self.powers[power].units.add(new_location)
            elif unit not in failed_moves:
                # Unit stayed in place (hold or no order)
                # Check if it was dislodged
                dislodged = False
                for attack_dest in successful_moves.values():
                    if attack_dest == current_location:
                        dislodged = True
                        break
                if not dislodged:
                    self.powers[power].units.add(current_location)
            else:
                # Unit failed to move, stays in original location
                # Check if it was dislodged
                dislodged = False
                for attack_dest in successful_moves.values():
                    if attack_dest == current_location:
                        dislodged = True
                        break
                if not dislodged:
                    self.powers[power].units.add(current_location)

        # 3. Update supply center control
        supply_centers = self.map.get_supply_centers()
        province_to_power: Dict[str, str] = {}
        for power, p in self.powers.items():
            for prov in p.units:
                if prov in supply_centers:
                    province_to_power[prov] = power
        for power, p in self.powers.items():
            p.controlled_centers = set()
        for prov, power in province_to_power.items():
            self.powers[power].gain_center(prov)
        for power, p in self.powers.items():
            if not p.controlled_centers:
                p.is_alive = False

        # 4. Clear orders and increment turn
        self.orders = {}
        self.turn += 1
        if self.turn >= 10:
            self.done = True

    def get_state(self) -> Dict[str, Any]:
        # Compose a richer state dictionary for server_spec compliance
        units = {power: list(p.units) for power, p in self.powers.items()}
        # Always return dict for orders, even if empty
        orders: Dict[str, List[str]] = dict(self.orders) if self.orders else {}
        return {
            "game_id": getattr(self, "game_id", None),
            "phase": f"Turn {self.turn}",
            "players": list(self.powers.keys()),
            "units": units,
            "orders": orders,
            "status": "done" if self.done else "active",
            "turn": self.turn,  # add legacy key for test compatibility
            "turn_number": self.turn,
            "map": self.map_name,
            "powers": list(self.powers.keys()),  # always a list, but tests expect dict sometimes
            "done": self.done
        }

    def is_game_done(self) -> bool:
        return self.done
