from typing import Dict, List, Any
from .map import Map
from .power import Power
from .order import OrderParser, Order
import logging
from collections import deque

class Game:
    """Main class for managing the game state, phases, and turn processing."""
    def __init__(self, map_name: str = 'standard') -> None:
        self.map_name: str = map_name
        self.map: Map = Map(map_name)  # Use Map for board representation, pass map_name
        self.powers: Dict[str, Power] = {}
        self.orders: Dict[str, List[str]] = {}
        self.turn: int = 0
        self.done: bool = False
        self.phase: str = "movement"  # movement, retreat, adjustment
        self.pending_retreats: Dict[str, Any] = {}  # power -> list of dislodged units/retreat options
        self.pending_adjustments: Dict[str, Any] = {}  # power -> build/disband info
        self.winner: List[str] = []  # List of winning powers
        # --- Adjudication result history ---
        # {turn: {power: {"orders": [...], "results": {order: {"success": bool, "dest": str|None, "dislodged": bool}}}}}
        self.order_history: Dict[int, Dict[str, Any]] = {}

    def add_player(self, power_name: str) -> None:
        if power_name not in self.powers:
            # Assign all supply centers as home centers for demo (for variants)
            self.powers[power_name] = Power(power_name, list(self.map.get_supply_centers()))
            # Assign standard starting units if using the standard map
            if self.map_name == 'standard':
                starting_units = {
                    'ENGLAND': ['F LON', 'F EDI', 'A LVP'],
                    'FRANCE': ['A PAR', 'A MAR', 'F BRE'],
                    'GERMANY': ['A BER', 'A MUN', 'F KIE'],
                    'ITALY': ['A ROM', 'A VEN', 'F NAP'],
                    'AUSTRIA': ['A VIE', 'A BUD', 'F TRI'],
                    'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'F STP'],
                    'TURKEY': ['A CON', 'A SMY', 'F ANK'],
                }
                pname = power_name.upper()
                if pname in starting_units:
                    self.powers[power_name].units = set(starting_units[pname])

    def set_orders(self, power_name: str, orders: List[str]) -> None:
        self.orders[power_name] = orders

    def process_phase(self) -> None:
        """Process the current phase (movement, retreat, adjustment)."""
        if self.phase == "movement":
            self._process_movement_phase()
        elif self.phase == "retreat":
            self._process_retreat_phase()
        elif self.phase == "adjustment":
            self._process_adjustment_phase()
        else:
            raise ValueError(f"Unknown phase: {self.phase}")

    def _process_movement_phase(self) -> None:
        # Existing movement logic (from process_turn)
        # DEBUG: Print units before normalization
        print("DEBUG: UNITS BEFORE NORMALIZATION:")
        for power, p in self.powers.items():
            print(f"  {power}: {p.units}")
        # 1. Normalize all units to full format (e.g., "A PAR", "F LON") BEFORE order validation
        unit_positions: Dict[str, str] = {}
        unit_to_power: Dict[str, str] = {}
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
                    normalized_units.add(f"{inferred_type} {unit}")
                    unit_positions[f"{inferred_type} {unit}"] = unit
                    unit_to_power[f"{inferred_type} {unit}"] = power
            p.units = normalized_units
        # DEBUG: Print units after normalization
        print("DEBUG: UNITS AFTER NORMALIZATION:")
        for power, p in self.powers.items():
            print(f"  {power}: {p.units}")
        # 2. Parse and validate all orders
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
                    # DEBUG: Print units for this power before validation
                    print(f"DEBUG: VALIDATING ORDER {order} FOR {power}, UNITS: {self.powers[power].units}")
                    # Validate the order properly
                    valid, msg = OrderParser.validate(order, self.get_state())
                    print(f"DEBUG: VALIDATION RESULT: {valid}, {msg}")
                    if valid:
                        parsed_orders[power].append(order)
                    # If invalid, the order is simply ignored (skip)
                except Exception as e:
                    print(f"DEBUG: Exception parsing/validating order '{order_str}': {e}")
                    continue  # Skip invalid orders

        # 3. Collect current unit positions and map orders to actual units
        # unit_positions: Dict[str, str] = {}
        # unit_to_power: Dict[str, str] = {}

        # Normalize all units to full format (e.g., "A PAR", "F LON")
        # for power, p in self.powers.items():
        #     normalized_units: set[str] = set()
        #     for unit in p.units:
        #         if ' ' in unit:
        #             # Already in full format
        #             unit_type, province = unit.split(' ', 1)
        #             normalized_units.add(f"{unit_type} {province}")
        #             unit_positions[f"{unit_type} {province}"] = province
        #             unit_to_power[f"{unit_type} {province}"] = power
        #         else:
        #             # Province only - need to infer type from orders
        #             inferred_type = 'A'  # Default to Army
        #             for orders in parsed_orders.values():
        #                 for order in orders:
        #                     if order.unit.split()[-1] == unit:
        #                         inferred_type = order.unit.split()[0]
        #                         break
        #                 if inferred_type != 'A':
        #                     break
        #             normalized_units.add(f"{inferred_type} {unit}")
        #             unit_positions[f"{inferred_type} {unit}"] = unit
        #             unit_to_power[f"{inferred_type} {unit}"] = power
        # p.units = normalized_units

        # 4. Parse orders into structured data
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

        # 5. Detect convoy moves based on convoy orders
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

        # Detect dislodged units and valid retreat options
        pending_retreats: Dict[str, List[Dict[str, Any]]] = {}
        for unit in dislodged_units:
            power = unit_to_power.get(unit)
            if not power:
                continue
            # Find valid retreat options for this unit
            unit_type, current_location = unit.split()
            # Valid retreats: any adjacent province that is unoccupied and not the origin of an attack
            adjacents = self.map.get_adjacency(current_location)
            occupied = {u.split()[-1] for u in unit_positions}
            attack_origins = {move_unit.split()[-1] for move_unit in moves}
            valid_retreats = [prov for prov in adjacents if prov not in occupied and prov not in attack_origins]
            if power not in pending_retreats:
                pending_retreats[power] = []
            pending_retreats[power].append({
                "unit": unit,
                "from": current_location,
                "options": valid_retreats,
            })

        if any(pending_retreats.values()):
            self.phase = "retreat"
            self.pending_retreats = pending_retreats
        else:
            # No retreats needed, go to adjustment or next movement
            self.phase = "adjustment"
            self.pending_retreats = {}
            self.pending_adjustments = {}  # TODO: Fill with actual build/disband info

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

        # At the end of adjudication, record results for history
        turn_results: Dict[str, Any] = {}
        for power, order_strs in self.orders.items():
            power_results = {"orders": list(order_strs), "results": {}}
            for order_str in order_strs:
                try:
                    if not order_str.startswith(power):
                        full_order_str = f"{power} {order_str}"
                    else:
                        full_order_str = order_str
                    order = OrderParser.parse(full_order_str)
                    # Determine result for this order
                    result = {"success": False, "dest": None, "dislodged": False}
                    if order.action == '-' and order.unit in successful_moves and successful_moves[order.unit] == order.target:
                        result["success"] = True
                        result["dest"] = order.target
                    elif order.action == 'H' and order.unit in unit_positions and order.unit not in dislodged_units:
                        result["success"] = True
                        result["dest"] = unit_positions[order.unit]
                    elif order.action == 'S' or order.action == 'C':
                        # Support/Convoy: success if not dislodged
                        if order.unit in unit_positions and order.unit not in dislodged_units:
                            result["success"] = True
                            result["dest"] = unit_positions[order.unit]
                    if order.unit in dislodged_units:
                        result["dislodged"] = True
                    power_results["results"][order_str] = result
                except Exception:
                    power_results["results"][order_str] = {"success": False, "dest": None, "dislodged": False}
            turn_results[power] = power_results
        # Store adjudication results for the current turn BEFORE clearing orders
        self.order_history[self.turn] = turn_results
        # 4. Clear orders and increment turn
        self.orders = {}
        self.turn += 1
        if self.turn >= 10:
            self.done = True

        # for pname, power in self.powers.items():
        #     print(f"DEBUG: {pname} units after update:", power.units)

        # STUB: After movement, transition to retreat phase
        # self.phase = "retreat" # This line is now handled by the new_successful_moves check
        # self.pending_retreats = {} # This line is now handled by the new_successful_moves check

    def _process_retreat_phase(self) -> None:
        # Process retreat/disband orders for each dislodged unit
        # self.pending_retreats: Dict[power, List[{unit, from, options}]]
        for power, retreats in self.pending_retreats.items():
            orders = self.orders.get(power, [])
            handled_units = set()
            for retreat_info in retreats:
                unit = retreat_info["unit"]
                options = set(retreat_info["options"])
                # Find the submitted order for this unit
                order_found = False
                for order_str in orders:
                    # Retreat order: e.g., 'A PAR R BUR' or 'A PAR D'
                    tokens = order_str.split()
                    if len(tokens) < 3:
                        continue
                    if tokens[0] != unit.split()[0] or tokens[1] != unit.split()[1]:
                        continue
                    if tokens[2] == "R" and len(tokens) == 4:
                        # Retreat order
                        dest = tokens[3]
                        if dest in options:
                            # Move unit to retreat destination
                            self.powers[power].units.discard(unit)
                            self.powers[power].units.add(f"{unit.split()[0]} {dest}")
                            order_found = True
                            handled_units.add(unit)
                            break
                    elif tokens[2] == "D":
                        # Disband order
                        self.powers[power].units.discard(unit)
                        order_found = True
                        handled_units.add(unit)
                        break
                if not order_found:
                    # Forced disband if no valid retreat submitted
                    self.powers[power].units.discard(unit)
        # After all retreats, clear pending_retreats and orders, go to adjustment phase
        self.pending_retreats = {}
        self.orders = {}
        self.phase = "adjustment"
        self.pending_adjustments = {}  # TODO: Fill with actual build/disband info

    def _process_adjustment_phase(self) -> None:
        """
        Process build/disband orders for each power according to supply center control.
        - Calculate builds/disbands needed for each power.
        - Accept and process submitted build/disband orders.
        - Enforce build/disband rules.
        - Transition to movement phase and increment turn.
        """
        logger = logging.getLogger("diplomacy.engine.adjustment")
        # 1. Calculate supply center counts and unit counts
        supply_centers = self.map.get_supply_centers()
        province_to_power: Dict[str, str] = {}
        for power, p in self.powers.items():
            for prov in p.units:
                if prov.split()[-1] in supply_centers:
                    province_to_power[prov.split()[-1]] = power
        for power, p in self.powers.items():
            p.controlled_centers = set()
        for prov, power in province_to_power.items():
            self.powers[power].gain_center(prov)
        # 2. Determine builds/disbands needed
        pending_adjustments: Dict[str, Dict[str, Any]] = {}
        for power, p in self.powers.items():
            num_centers = len(p.controlled_centers)
            num_units = len(p.units)
            home_centers = set(p.home_centers)
            # Only allow builds in unoccupied, controlled home centers
            buildable = [prov for prov in home_centers if prov in p.controlled_centers and all(prov != u.split()[-1] for u in p.units)]
            if num_centers > num_units:
                pending_adjustments[power] = {"type": "build", "count": num_centers - num_units, "options": buildable}
            elif num_units > num_centers:
                # Disband: must remove units
                pending_adjustments[power] = {"type": "disband", "count": num_units - num_centers, "options": list(p.units)}
            else:
                # No adjustment needed
                continue
        self.pending_adjustments = pending_adjustments
        # 3. Process submitted build/disband orders
        for power, adj in pending_adjustments.items():
            orders = self.orders.get(power, [])
            handled = 0
            if adj["type"] == "build":
                for order_str in orders:
                    # Format: 'BUILD A PAR' or 'BUILD F LON'
                    tokens = order_str.strip().split()
                    if len(tokens) == 3 and tokens[0] == "BUILD" and tokens[2] in adj["options"]:
                        unit_type = tokens[1]
                        province = tokens[2]
                        if unit_type in {"A", "F"} and province in adj["options"]:
                            self.powers[power].units.add(f"{unit_type} {province}")
                            handled += 1
                            adj["options"].remove(province)
                            if handled >= adj["count"]:
                                break
                # If not enough builds submitted, skip remaining
            elif adj["type"] == "disband":
                # Format: 'DISBAND A PAR' or 'DISBAND F LON'
                disbanded = set()
                for order_str in orders:
                    tokens = order_str.strip().split()
                    if len(tokens) == 3 and tokens[0] == "DISBAND" and tokens[2] in [u.split()[-1] for u in adj["options"]]:
                        # Remove the specified unit
                        for u in list(self.powers[power].units):
                            if u.split()[-1] == tokens[2]:
                                self.powers[power].units.remove(u)
                                disbanded.add(u)
                                handled += 1
                                break
                        if handled >= adj["count"]:
                            break
                # If not enough disbands submitted, remove by rules: farthest from home, then alpha
                if handled < adj["count"]:
                    # Compute distances from home for remaining units
                    remaining = [u for u in self.powers[power].units if u not in disbanded]
                    # Farthest from home: use BFS or simple heuristic (not optimal, but sufficient for now)
                    def dist(prov):
                        # Minimal distance from prov to any home center
                        min_dist = float('inf')
                        for home in p.home_centers:
                            visited = set()
                            queue = deque([(prov, 0)])
                            while queue:
                                curr, d = queue.popleft()
                                if curr == home:
                                    min_dist = min(min_dist, d)
                                    break
                                for adj in self.map.get_adjacency(curr):
                                    if adj not in visited:
                                        visited.add(adj)
                                        queue.append((adj, d+1))
                        return min_dist
                    remaining.sort(key=lambda u: (-dist(u.split()[-1]), u.split()[-1]))
                    for u in remaining:
                        if handled >= adj["count"]:
                            break
                        self.powers[power].units.remove(u)
                        handled += 1
            # Log adjustment results
            logger.info(f"Adjustment for {power}: {adj['type']} x{adj['count']}, handled: {handled}")
        # 4. Check for victory conditions (standard map: 18 supply centers)
        victory_threshold = 18 if self.map_name == 'standard' else None  # TODO: support variants
        winners = []
        if victory_threshold is not None:
            for power, p in self.powers.items():
                if len(p.controlled_centers) >= victory_threshold:
                    winners.append(power)
        if winners:
            self.done = True
            self.winner = winners
            logger.info(f"Victory! Winner(s): {winners}")
        # 5. Clear orders and pending adjustments, transition to movement phase, increment turn (if not done)
        self.orders = {}
        self.pending_adjustments = {}
        if not self.done:
            self.phase = "movement"
            self.turn += 1

    def get_state(self) -> Dict[str, Any]:
        # Compose a richer state dictionary for server_spec compliance
        units = {power: list(p.units) for power, p in self.powers.items()}
        # Always return dict for orders, even if empty
        orders: Dict[str, List[str]] = dict(self.orders) if self.orders else {}
        # Include latest adjudication results for the last completed turn (if present)
        adjudication_results = self.order_history.get(self.turn - 1, {})
        return {
            "game_id": getattr(self, "game_id", None),
            "phase": self.phase,
            "players": list(self.powers.keys()),
            "units": units,
            "orders": orders,
            "status": "done" if self.done else "active",
            "turn": self.turn,  # add legacy key for test compatibility
            "turn_number": self.turn,
            "map": self.map_name,
            "powers": list(self.powers.keys()),  # always a list, but tests expect dict sometimes
            "done": self.done,
            "winner": self.winner,
            "map_obj": self.map,
            "pending_retreats": self.pending_retreats,
            "pending_adjustments": self.pending_adjustments,
            "adjudication_results": adjudication_results,
        }

    def is_game_done(self) -> bool:
        return self.done
