from typing import Dict, List, Any
from engine.map import Map
from engine.power import Power
from engine.order import OrderParser, Order

class Game:
    """Main class for managing the game state, phases, and turn processing."""
    def __init__(self, map_name: str = 'standard') -> None:
        self.map_name: str = map_name
        self.map: Map = Map(map_name)  # Use Map for board representation, pass map_name
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
                    # Prepend power name if not already present
                    if not order_str.startswith(power):
                        full_order_str = f"{power} {order_str}"
                    else:
                        full_order_str = order_str
                    
                    order = OrderParser.parse(full_order_str)
                    # Validate the order properly
                    valid, _ = OrderParser.validate(order, self.get_state())
                    if valid:
                        parsed_orders[power].append(order)
                    # If invalid, the order is simply ignored (skip)
                except Exception:
                    continue  # Skip invalid orders

        # 2. Collect current unit positions and map orders to actual units
        unit_positions: Dict[str, str] = {}
        unit_to_power: Dict[str, str] = {}
        
        # Normalize all units to full format (e.g., "A PAR", "F LON")
        for power, p in self.powers.items():
            normalized_units: set[str] = set()
            for unit in p.units:
                if ' ' in unit:
                    # Already in full format
                    unit_type, province = unit.split(' ', 1)
                    normalized_units.add(f"{unit_type} {province}")
                    unit_positions[f"{unit_type} {province}"] = province
                    unit_to_power[f"{unit_type} {province}"] = power
                else:
                    # Province only - need to infer type from orders
                    inferred_type = 'A'  # Default to Army
                    for orders in parsed_orders.values():
                        for order in orders:
                            if order.unit.split()[-1] == unit:
                                inferred_type = order.unit.split()[0]
                                break
                        if inferred_type != 'A':
                            break
                    normalized_units.add(f"{inferred_type} {unit}")
                    unit_positions[f"{inferred_type} {unit}"] = unit
                    unit_to_power[f"{inferred_type} {unit}"] = power
            p.units = normalized_units

        # 3. Parse orders into structured data
        moves: Dict[str, str] = {}  # unit -> destination
        supports: Dict[str, List[str]] = {}  # supported move -> list of supporting units
        convoys: Dict[str, str] = {}  # convoyed unit -> convoy path
        convoy_orders: Dict[str, str] = {}  # fleet -> move being convoyed

        print("DEBUG: parsed_orders:", parsed_orders)
        for power, orders in parsed_orders.items():
            print(f"DEBUG: Processing {power} orders: {orders}")
            for order in orders:
                print(f"DEBUG: Processing order: {order}")
                if order.action == '-' and order.target is not None:
                    # Move order
                    target = order.target.replace(' VIA CONVOY', '')
                    moves[order.unit] = target
                    print(f"DEBUG: Added move: {order.unit} -> {target}")
                    
                    # Check if this is a convoyed move
                    if 'VIA CONVOY' in order.target:
                        convoys[order.unit] = target
                        
                elif order.action == 'S' and order.target:
                    # Support order
                    if order.target not in supports:
                        supports[order.target] = []
                    supports[order.target].append(order.unit)
                    print(f"DEBUG: Added support: {order.unit} supports {order.target}")
                    
                elif order.action == 'C' and order.target:
                    # Convoy order
                    convoy_orders[order.unit] = order.target

        # 4. Detect convoy moves based on convoy orders
        # If there's a convoy order for a move, mark it as a convoy move
        for fleet, convoy_target in convoy_orders.items():
            # Parse convoy target to find the unit and destination
            if convoy_target and ' - ' in convoy_target:
                convoyed_unit = convoy_target.split(' - ')[0]
                destination = convoy_target.split(' - ')[1]
                # Check if there's a matching move order
                if convoyed_unit in moves and moves[convoyed_unit] == destination:
                    convoys[convoyed_unit] = destination

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
                    # Find all fleets that are convoying this move
                    convoying_fleets: List[str] = []
                    for fleet, convoyed_move in convoy_orders.items():
                        if convoyed_move == f"{move_unit} - {destination}":
                            convoying_fleets.append(fleet)
                    
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
        
        # --- SELF-DISLODGEMENT PROHIBITED (Diplomacy rule) ---
        # Remove any move that would dislodge a unit of the same power
        prohibited_moves: set[tuple[str, str]] = set()
        for move_unit, destination in list(successful_moves.items()):
            for unit, location in unit_positions.items():
                if location == destination and unit != move_unit and unit not in moves:
                    # Check if both units belong to the same power
                    if unit_to_power.get(unit) == unit_to_power.get(move_unit):
                        # Prohibit self-dislodgement
                        del successful_moves[move_unit]
                        failed_moves.add(move_unit)
                        prohibited_moves.add((move_unit, unit))
                        break

        # Calculate final dislodged units
        dislodged_units: set[str] = set()
        for move_unit, destination in successful_moves.items():
            for unit, location in unit_positions.items():
                if location == destination and unit != move_unit and unit not in moves:
                    dislodged_units.add(unit)

        # Remove moves from successful_moves if the convoy was disrupted (robustly, after adjudication)
        disrupted: set[str] = set()
        for unit, dest in list(successful_moves.items()):
            # Only check for convoyed moves
            if unit in convoys:
                # Find all fleets that are convoying this move (multi-fleet convoys supported)
                convoy_route = f"{unit} - {dest}"
                convoying_fleets = [fleet for fleet, convoyed in convoy_orders.items() if convoyed == convoy_route]
                # If any fleet in the convoy chain is dislodged, the convoy is disrupted
                if any(fleet in dislodged_units for fleet in convoying_fleets):
                    disrupted.add(unit)
        for unit in disrupted:
            if unit in successful_moves:
                del successful_moves[unit]
                failed_moves.add(unit)
                # Ensure disrupted unit is not considered dislodged and is preserved in place
                # (handled by the next block that preserves units not in successful_moves or dislodged_units)

        # 6. Update unit positions
        preserve_units: set[tuple[str, str]] = set()
        for move_unit, defend_unit in prohibited_moves:
            preserve_units.add((unit_to_power[move_unit], unit_positions[move_unit]))
            preserve_units.add((unit_to_power[defend_unit], unit_positions[defend_unit]))
        all_units = set(unit_positions.items())
        # Build new unit sets for each power
        new_units: Dict[str, set[str]] = {power: set() for power in self.powers}
        # For every successful move, add the attacker's unit at the destination
        for unit, dest in successful_moves.items():
            unit_type = unit.split()[0]
            new_unit_id = f"{unit_type} {dest}"
            power = unit_to_power.get(unit)
            if power is None:
                power = unit_to_power.get(dest)
            if power is not None:
                # Remove any unit with the same province as the destination
                new_units[power] = set(u for u in new_units[power] if u.split()[-1] != dest)
                new_units[power].add(new_unit_id)
        # Assign destinations before processing remaining units
        destinations = set(successful_moves.values())
        all_units = set(unit_positions.items())
        # For all units that did not move or failed to move and were not dislodged, keep them in place (only as full identifier)
        for unit, current_location in all_units:
            power = unit_to_power[unit]
            if (power, current_location) in preserve_units:
                new_units[power].add(unit)
                continue
            # Only preserve if unit did not move successfully, was not dislodged, and no other unit moved into its province
            if unit not in successful_moves and unit not in dislodged_units and current_location not in destinations:
                if len(unit.split()) == 2 and unit.split()[0] in {'A', 'F'}:
                    new_units[power].add(unit)
        # Assign new unit sets to each power
        for power in self.powers:
            # Only keep full identifiers (e.g., 'A BEL', 'F NTH')
            self.powers[power].units = set(u for u in new_units[power] if len(u.split()) == 2 and u.split()[0] in {'A', 'F'})
        # Remove any plain province names from the original units as well
        for power in self.powers:
            self.powers[power].units = set(u for u in self.powers[power].units if len(u.split()) == 2 and u.split()[0] in {'A', 'F'})

        # DEBUG: Print adjudication results for troubleshooting
        # print("DEBUG: moves:", moves)
        # print("DEBUG: convoys:", convoys)
        # print("DEBUG: convoy_orders:", convoy_orders)
        # print("DEBUG: supports:", supports)
        # print("DEBUG: successful_moves:", successful_moves)
        # print("DEBUG: dislodged_units:", dislodged_units)
        # for pname, power in self.powers.items():
        #     print(f"DEBUG: {pname} units before update:", power.units)

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

        # for pname, power in self.powers.items():
        #     print(f"DEBUG: {pname} units after update:", power.units)

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
            "done": self.done,
            "map_obj": self.map,
        }

    def is_game_done(self) -> bool:
        return self.done
