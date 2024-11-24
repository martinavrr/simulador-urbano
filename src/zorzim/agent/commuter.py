from collections import OrderedDict
from typing import List, Tuple
from shapely.geometry import Point, LineString
import mesa
import mesa_geo as mg
from zorzim.space.utils import redistribute_vertices


class Commuter(mg.GeoAgent):
    """Clase que representa a un viajero dentro de la simulación."""
    def __init__(self, unique_id, model, geometry, schedule, crs, speed):
        if geometry is None or not isinstance(geometry, Point):
            raise ValueError(f"Error al inicializar el agente {unique_id}: geometría inválida {geometry}.")
        
        super().__init__(unique_id, model, geometry, crs)
        self.speed = speed
        self.traveling = False
        self.schedule = schedule
        self.next_move = self.schedule.popitem(last=False) if self.schedule else None
        self.pos = self.next_move[1][0] if self.next_move else (geometry.x, geometry.y)
        self.destination = self.next_move[1][1] if self.next_move else None
        self.my_path = []
        self.step_in_path = 0
        self.color = "red"
        self.path_trail = []
        self.active = True

    def step(self) -> None:
        if not self.active:
            return  # No hacer nada si el agente ya no está activo

        if not self.traveling:
            self._prepare_to_move()
        self._move()

    def _prepare_to_move(self) -> None:
        """Prepara al agente para moverse, asignándole una ruta."""
        self.model.space.move_commuter(self, pos=self.pos)
        self.traveling = True
        self._path_select()

    def _move(self) -> None:
        if self.traveling:
            if self.step_in_path < len(self.my_path):
                next_position = self.my_path[self.step_in_path]
                self.model.space.move_commuter(self, next_position)
                self.pos = next_position
                self.step_in_path += 1
            else:
                # El agente ha llegado al destino final
                self.model.space.move_commuter(self, self.destination)
                self.pos = self.destination
                self.traveling = False
                self.active = False  # Marcar al agente como inactivo
                self.model.got_to_destination += 1
                print(f"Agente {self.unique_id} llegó al destino: {self.destination}")

    def _path_select(self) -> None:
        """Calcula la ruta más corta para el agente."""
        self.step_in_path = 0  # Reinicia al inicio de la ruta
        
        if self.pos == self.destination:
            print(f"Agente {self.unique_id} ya está en el destino: {self.destination}")
            self.my_path = []  # No hay ruta que calcular
            return

        shortest_path_vertices = self.model.get_shortest_path(self.pos, self.destination)
        if not shortest_path_vertices:
            print(f"Agente {self.unique_id}: no se pudo calcular una ruta desde {self.pos} a {self.destination}")
            self.my_path = []  # Ruta vacía
        else:
            self.my_path = [
                self.model.vertex_to_coord[vertex]
                for vertex in shortest_path_vertices
                if vertex in self.model.vertex_to_coord
            ]

    def _redistribute_path_vertices(self) -> None:
        """Distribuye puntos en la ruta para simular un movimiento más fluido."""
        if len(self.my_path) > 1:
            original_path = LineString([Point(p) for p in self.my_path])
            reduced_speed = self.speed * 10.0  # Ajusta velocidad
            redistributed_path = redistribute_vertices(original_path, reduced_speed)
            self.my_path = list(redistributed_path.coords)
