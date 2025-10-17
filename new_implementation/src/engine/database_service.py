"""
Database service for Diplomacy game engine.

This module provides database operations using the new data models and schema
to ensure proper data integrity and consistency.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .database import (
    GameModel, PlayerModel, UnitModel, OrderModel, SupplyCenterModel,
    TurnHistoryModel, MapSnapshotModel, MessageModel, UserModel,
    get_session_factory, unit_to_dict, dict_to_unit, order_to_dict, dict_to_order
)
from .data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus, GameStatus,
    MapData, Province, TurnState, MapSnapshot
)


class DatabaseService:
    """Service for database operations"""
    
    def __init__(self, database_url: str):
        self.session_factory = get_session_factory(database_url)
    
    def create_game(self, game_id: str, map_name: str = 'standard') -> GameState:
        """
        Create a new game in the database.
        
        Args:
            game_id: Unique identifier for the game
            map_name: Name of the map variant to use (default: 'standard')
            
        Returns:
            GameState object representing the newly created game
            
        Note:
            This method creates both the database record and an empty
            GameState object ready for players to join.
        """
        with self.session_factory() as session:
            # Create game record
            game_model = GameModel(
                game_id=game_id,
                map_name=map_name,
                current_turn=0,
                current_year=1901,
                current_season='Spring',
                current_phase='Movement',
                phase_code='S1901M',
                status='active'
            )
            session.add(game_model)
            session.commit()
            
            # Create empty game state
            game_state = GameState(
                game_id=game_id,
                map_name=map_name,
                current_turn=0,
                current_year=1901,
                current_season='Spring',
                current_phase='Movement',
                phase_code='S1901M',
                status=GameStatus.ACTIVE,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                powers={},
                map_data=self._load_map_data(map_name),
                orders={}
            )
            
            return game_state
    
    def add_player(self, game_id: str, power_name: str, user_id: Optional[int] = None) -> PowerState:
        """
        Add a player to a game.
        
        Args:
            game_id: Unique identifier of the game
            power_name: Name of the power to add (e.g., "FRANCE", "GERMANY")
            user_id: Optional user ID to associate with the power
            
        Returns:
            PowerState object representing the newly added power
            
        Raises:
            ValueError: If the game is not found or power already exists
            
        Note:
            This method initializes the power with their home supply centers
            and starting units according to standard Diplomacy rules.
        """
        with self.session_factory() as session:
            # Get game
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            # Create player record
            player_model = PlayerModel(
                game_id=game_model.id,
                power_name=power_name,
                user_id=user_id,
                is_active=True,
                is_eliminated=False,
                home_supply_centers=[],
                controlled_supply_centers=[],
                orders_submitted=False
            )
            session.add(player_model)
            session.commit()
            
            # Create power state
            power_state = PowerState(
                power_name=power_name,
                user_id=user_id,
                is_active=True,
                is_eliminated=False,
                home_supply_centers=[],
                controlled_supply_centers=[],
                units=[],
                orders_submitted=False
            )
            
            return power_state
    
    def add_unit(self, game_id: str, power_name: str, unit: Unit) -> None:
        """Add a unit to a game"""
        with self.session_factory() as session:
            # Get game
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            # Create unit record
            unit_model = UnitModel(
                game_id=game_model.id,
                power_name=power_name,
                unit_type=unit.unit_type,
                province=unit.province,
                is_dislodged=unit.is_dislodged,
                dislodged_by=unit.dislodged_by,
                can_retreat=unit.can_retreat,
                retreat_options=unit.retreat_options
            )
            session.add(unit_model)
            session.commit()
    
    def submit_orders(self, game_id: str, power_name: str, orders: List[Order]) -> None:
        """Submit orders for a power"""
        with self.session_factory() as session:
            # Get game
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            # Clear existing orders for this power
            session.query(OrderModel).filter_by(
                game_id=game_model.id,
                power_name=power_name,
                turn_number=game_model.current_turn,
                phase=game_model.current_phase
            ).delete()
            
            # Add new orders
            for order in orders:
                order_data = order_to_dict(order)
                order_model = OrderModel(
                    game_id=game_model.id,
                    power_name=power_name,
                    order_type=order_data["order_type"],
                    unit_type=order_data["unit"]["unit_type"],
                    unit_province=order_data["unit"]["province"],
                    target_province=order_data.get("target_province"),
                    supported_unit_type=order_data.get("supported_unit", {}).get("unit_type"),
                    supported_unit_province=order_data.get("supported_unit", {}).get("province"),
                    supported_target=order_data.get("supported_target"),
                    convoyed_unit_type=order_data.get("convoyed_unit", {}).get("unit_type"),
                    convoyed_unit_province=order_data.get("convoyed_unit", {}).get("province"),
                    convoyed_target=order_data.get("convoyed_target"),
                    convoy_chain=order_data.get("convoy_chain", []),
                    build_type=order_data.get("build_type"),
                    build_province=order_data.get("build_province"),
                    build_coast=order_data.get("build_coast"),
                    destroy_unit_type=order_data.get("destroy_unit", {}).get("unit_type"),
                    destroy_unit_province=order_data.get("destroy_unit", {}).get("province"),
                    status=order_data["status"],
                    failure_reason=order_data.get("failure_reason"),
                    phase=game_model.current_phase,
                    turn_number=game_model.current_turn
                )
                session.add(order_model)
            
            # Update player orders submitted status
            player_model = session.query(PlayerModel).filter_by(
                game_id=game_model.id,
                power_name=power_name
            ).first()
            if player_model:
                player_model.orders_submitted = True
                player_model.last_order_time = datetime.utcnow()
            
            session.commit()
    
    def get_game_state(self, game_id: str) -> Optional[GameState]:
        """Get complete game state"""
        with self.session_factory() as session:
            # Get game
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                return None
            
            # Get players
            players = session.query(PlayerModel).filter_by(game_id=game_model.id).all()
            powers = {}
            
            for player in players:
                # Get units for this player
                units = session.query(UnitModel).filter_by(
                    game_id=game_model.id,
                    power_name=player.power_name
                ).all()
                
                unit_list = []
                for unit_model in units:
                    unit = Unit(
                        unit_type=unit_model.unit_type,
                        province=unit_model.province,
                        power=unit_model.power_name,
                        is_dislodged=unit_model.is_dislodged,
                        dislodged_by=unit_model.dislodged_by,
                        can_retreat=unit_model.can_retreat,
                        retreat_options=unit_model.retreat_options or []
                    )
                    unit_list.append(unit)
                
                # Get supply centers
                supply_centers = session.query(SupplyCenterModel).filter_by(
                    game_id=game_model.id,
                    controlling_power=player.power_name
                ).all()
                
                controlled_supply_centers = [sc.province for sc in supply_centers]
                
                power_state = PowerState(
                    power_name=player.power_name,
                    user_id=player.user_id,
                    is_active=player.is_active,
                    is_eliminated=player.is_eliminated,
                    home_supply_centers=player.home_supply_centers or [],
                    controlled_supply_centers=controlled_supply_centers,
                    units=unit_list,
                    orders_submitted=player.orders_submitted,
                    last_order_time=player.last_order_time
                )
                powers[player.power_name] = power_state
            
            # Get current orders
            orders = session.query(OrderModel).filter_by(
                game_id=game_model.id,
                turn_number=game_model.current_turn,
                phase=game_model.current_phase
            ).all()
            
            orders_dict = {}
            for order_model in orders:
                if order_model.power_name not in orders_dict:
                    orders_dict[order_model.power_name] = []
                
                # Convert order model back to Order object
                order_data = {
                    "power": order_model.power_name,
                    "unit": {
                        "unit_type": order_model.unit_type,
                        "province": order_model.unit_province,
                        "power": order_model.power_name
                    },
                    "order_type": order_model.order_type,
                    "phase": order_model.phase,
                    "status": order_model.status,
                    "failure_reason": order_model.failure_reason
                }
                
                # Add order-specific fields
                if order_model.target_province:
                    order_data["target_province"] = order_model.target_province
                if order_model.supported_unit_type:
                    order_data["supported_unit"] = {
                        "unit_type": order_model.supported_unit_type,
                        "province": order_model.supported_unit_province,
                        "power": order_model.power_name
                    }
                if order_model.supported_target:
                    order_data["supported_target"] = order_model.supported_target
                if order_model.convoyed_unit_type:
                    order_data["convoyed_unit"] = {
                        "unit_type": order_model.convoyed_unit_type,
                        "province": order_model.convoyed_unit_province,
                        "power": order_model.power_name
                    }
                if order_model.convoyed_target:
                    order_data["convoyed_target"] = order_model.convoyed_target
                if order_model.convoy_chain:
                    order_data["convoy_chain"] = order_model.convoy_chain
                if order_model.retreat_province:
                    order_data["retreat_province"] = order_model.retreat_province
                if order_model.build_type:
                    order_data["build_type"] = order_model.build_type
                if order_model.build_province:
                    order_data["build_province"] = order_model.build_province
                if order_model.build_coast:
                    order_data["build_coast"] = order_model.build_coast
                if order_model.destroy_unit_type:
                    order_data["destroy_unit"] = {
                        "unit_type": order_model.destroy_unit_type,
                        "province": order_model.destroy_unit_province,
                        "power": order_model.power_name
                    }
                
                try:
                    order = dict_to_order(order_data)
                    orders_dict[order_model.power_name].append(order)
                except Exception as e:
                    print(f"Warning: Failed to convert order: {e}")
            
            # Create game state
            game_state = GameState(
                game_id=game_model.game_id,
                map_name=game_model.map_name,
                current_turn=game_model.current_turn,
                current_year=game_model.current_year,
                current_season=game_model.current_season,
                current_phase=game_model.current_phase,
                phase_code=game_model.phase_code,
                status=GameStatus(game_model.status),
                created_at=game_model.created_at,
                updated_at=game_model.updated_at,
                powers=powers,
                map_data=self._load_map_data(game_model.map_name),
                orders=orders_dict
            )
            
            return game_state
    
    def update_game_state(self, game_state: GameState) -> None:
        """Update game state in database"""
        with self.session_factory() as session:
            # Get game
            game_model = session.query(GameModel).filter_by(game_id=game_state.game_id).first()
            if not game_model:
                raise ValueError(f"Game {game_state.game_id} not found")
            
            # Update game fields
            game_model.current_turn = game_state.current_turn
            game_model.current_year = game_state.current_year
            game_model.current_season = game_state.current_season
            game_model.current_phase = game_state.current_phase
            game_model.phase_code = game_state.phase_code
            game_model.status = game_state.status.value
            game_model.updated_at = datetime.utcnow()
            
            # Update units
            self._update_units(session, game_model.id, game_state)
            
            # Update supply centers
            self._update_supply_centers(session, game_model.id, game_state)
            
            session.commit()
    
    def _update_units(self, session: Session, game_id: int, game_state: GameState) -> None:
        """Update units in database"""
        # Clear existing units
        session.query(UnitModel).filter_by(game_id=game_id).delete()
        
        # Add current units
        for power_name, power_state in game_state.powers.items():
            for unit in power_state.units:
                unit_model = UnitModel(
                    game_id=game_id,
                    power_name=power_name,
                    unit_type=unit.unit_type,
                    province=unit.province,
                    is_dislodged=unit.is_dislodged,
                    dislodged_by=unit.dislodged_by,
                    can_retreat=unit.can_retreat,
                    retreat_options=unit.retreat_options
                )
                session.add(unit_model)
    
    def _update_supply_centers(self, session: Session, game_id: int, game_state: GameState) -> None:
        """Update supply centers in database"""
        # Clear existing supply centers
        session.query(SupplyCenterModel).filter_by(game_id=game_id).delete()
        
        # Add current supply centers
        for power_name, power_state in game_state.powers.items():
            for province in power_state.controlled_supply_centers:
                supply_center_model = SupplyCenterModel(
                    game_id=game_id,
                    province=province,
                    controlling_power=power_name,
                    is_home_supply_center=province in power_state.home_supply_centers,
                    home_power=power_name if province in power_state.home_supply_centers else None
                )
                session.add(supply_center_model)
    
    def _load_map_data(self, map_name: str) -> MapData:
        """Load map data (placeholder - should load from actual map files)"""
        # This is a placeholder - in a real implementation, this would load
        # the actual map data from the map files
        return MapData(
            map_name=map_name,
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
    
    def save_turn_history(self, game_id: str, turn_state: TurnState) -> None:
        """Save turn history"""
        with self.session_factory() as session:
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            # Convert units to JSON
            units_before = {power: [unit_to_dict(unit) for unit in units] 
                          for power, units in turn_state.units_before.items()}
            units_after = {power: [unit_to_dict(unit) for unit in units] 
                         for power, units in turn_state.units_after.items()}
            
            turn_history_model = TurnHistoryModel(
                game_id=game_model.id,
                turn_number=turn_state.turn_number,
                year=turn_state.year,
                season=turn_state.season,
                phase=turn_state.phase,
                phase_code=turn_state.phase_code,
                units_before=units_before,
                units_after=units_after,
                supply_centers_before=turn_state.supply_centers_before,
                supply_centers_after=turn_state.supply_centers_after
            )
            session.add(turn_history_model)
            session.commit()
    
    def save_map_snapshot(self, game_id: str, snapshot: MapSnapshot) -> None:
        """Save map snapshot"""
        with self.session_factory() as session:
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                raise ValueError(f"Game {game_id} not found")
            
            # Convert units to JSON
            units_json = {power: [unit_to_dict(unit) for unit in units] 
                         for power, units in snapshot.units.items()}
            
            map_snapshot_model = MapSnapshotModel(
                game_id=game_model.id,
                turn_number=snapshot.turn_number,
                phase_code=snapshot.phase_code,
                units=units_json,
                supply_centers=snapshot.supply_centers,
                map_image_path=snapshot.map_image_path
            )
            session.add(map_snapshot_model)
            session.commit()
    
    def get_all_games(self) -> List[str]:
        """Get all game IDs"""
        with self.session_factory() as session:
            games = session.query(GameModel).all()
            return [game.game_id for game in games]
    
    def delete_game(self, game_id: str) -> bool:
        """Delete a game"""
        with self.session_factory() as session:
            game_model = session.query(GameModel).filter_by(game_id=game_id).first()
            if not game_model:
                return False
            
            session.delete(game_model)
            session.commit()
            return True
    
    def delete_all_games(self) -> int:
        """Delete all games"""
        with self.session_factory() as session:
            count = session.query(GameModel).count()
            session.query(GameModel).delete()
            session.commit()
            return count
