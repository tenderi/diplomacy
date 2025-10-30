from pydantic import BaseModel
from typing import Dict, List, Optional, Any


class UnitOut(BaseModel):
    unit_type: str
    province: str
    power: str
    is_dislodged: Optional[bool] = False
    dislodged_by: Optional[str] = None
    can_retreat: Optional[bool] = True
    retreat_options: Optional[List[str]] = None
    coast: Optional[str] = None


class PowerStateOut(BaseModel):
    power_name: str
    user_id: Optional[int] = None
    is_active: bool = True
    is_eliminated: bool = False
    home_supply_centers: List[str] = []
    controlled_supply_centers: List[str] = []
    units: List[UnitOut] = []
    orders_submitted: bool = False
    last_order_time: Optional[str] = None
    retreat_options: Dict[str, List[str]] = {}
    build_options: List[str] = []
    destroy_options: List[str] = []


class MapSnapshotOut(BaseModel):
    turn_number: int
    phase_code: str
    units: Dict[str, List[UnitOut]]
    supply_centers: Dict[str, str]
    map_image_path: Optional[str] = None
    created_at: str


class TurnStateOut(BaseModel):
    turn_number: int
    year: int
    season: str
    phase: str
    phase_code: str
    orders: Dict[str, List[Dict[str, Any]]]  # serialized orders
    results: Dict[str, List[Dict[str, Any]]] = {}
    units_before: Dict[str, List[UnitOut]]
    units_after: Dict[str, List[UnitOut]]
    supply_centers_before: Dict[str, str]
    supply_centers_after: Dict[str, str]
    timestamp: str


class GameStateOut(BaseModel):
    game_id: str
    map_name: str
    current_turn: int
    current_year: int
    current_season: str
    current_phase: str
    phase_code: str
    status: str
    created_at: str
    updated_at: str

    powers: Dict[str, PowerStateOut]
    units: Dict[str, List[UnitOut]]
    supply_centers: Dict[str, str]
    orders: Dict[str, List[Dict[str, Any]]]
    pending_retreats: Dict[str, List[Dict[str, Any]]] = {}
    pending_builds: Dict[str, List[Dict[str, Any]]] = {}
    pending_destroys: Dict[str, List[Dict[str, Any]]] = {}

    turn_history: List[TurnStateOut] = []
    order_history: List[Dict[str, List[Dict[str, Any]]]] = []
    map_snapshots: List[MapSnapshotOut] = []


