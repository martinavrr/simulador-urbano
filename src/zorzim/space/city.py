from collections import defaultdict
from typing import Dict, DefaultDict, Set

import math
import mesa
import mesa_geo as mg
from shapely.geometry import Point

def get_distance(pos_1: mesa.space.FloatCoordinate, pos_2: mesa.space.FloatCoordinate) -> float:
    x1, y1 = pos_1
    x2, y2 = pos_2

    dx = abs(x1 - x2)
    dy = abs(y1 - y2)

    return math.sqrt(dx * dx + dy * dy)

class City(mg.GeoSpace):
    _commuters_pos_map: DefaultDict[mesa.space.FloatCoordinate, Set["Commuter"]]
    _commuter_id_map: Dict[int, "Commuter"]

    def __init__(self, crs: str) -> None:
        super().__init__(crs=crs)
        self._commuters_pos_map = defaultdict(set)
        self._commuter_id_map = dict()

    def get_commuters_by_pos(
        self, float_pos: mesa.space.FloatCoordinate
    ) -> Set["Commuter"]:
        from zorzim.agent.commuter import Commuter  # Importación diferida
        return self._commuters_pos_map[float_pos]

    def get_commuter_by_id(self, commuter_id: int) -> "Commuter":
        from zorzim.agent.commuter import Commuter  # Importación diferida
        return self._commuter_id_map[commuter_id]

    def add_commuter(self, agent: "Commuter") -> None:
        from zorzim.agent.commuter import Commuter  # Importación diferida
        super().add_agents([agent])
        self._commuters_pos_map[(agent.geometry.x, agent.geometry.y)].add(agent)
        self._commuter_id_map[agent.unique_id] = agent

    def move_commuter(self, commuter: "Commuter", pos: mesa.space.FloatCoordinate) -> None:
        if pos is None or not isinstance(pos, tuple) or len(pos) != 2:
            raise ValueError(
                f"Error: No se puede mover al commuter {commuter.unique_id} porque la posición es inválida: {pos}. "
                f"Posición previa: {commuter.geometry}."
            )
        self.__remove_commuter(commuter)
        commuter.geometry = Point(pos)
        self.add_commuter(commuter)

    def __remove_commuter(self, commuter: "Commuter") -> None:
        from zorzim.agent.commuter import Commuter  # Importación diferida
        super().remove_agent(commuter)
        del self._commuter_id_map[commuter.unique_id]
        self._commuters_pos_map[(commuter.geometry.x, commuter.geometry.y)].remove(
            commuter
        )
