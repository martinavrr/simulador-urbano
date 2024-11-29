from collections import OrderedDict
import random
from typing import List, Tuple
from shapely.geometry import Point, LineString
import mesa
import mesa_geo as mg
from zorzim.space.utils import redistribute_vertices
from pyproj import Transformer
from shapely.ops import transform

def calcular_distancia(coord1, coord2):
    """Calcula la distancia entre dos coordenadas usando Shapely."""
    punto1 = Point(coord1)
    punto2 = Point(coord2)
    return punto1.distance(punto2)

class Commuter(mg.GeoAgent):
    """Clase que representa a un viajero dentro de la simulación."""
    def __init__(self, unique_id, model, geometry, schedule, crs, speed, evacuation_centers=None, fire_focus=None):
        if geometry is None or not isinstance(geometry, Point):
            raise ValueError(f"Error al inicializar el agente {unique_id}: geometría inválida {geometry}.")
        
        super().__init__(unique_id, model, geometry, crs)
        self.speed = speed
        self.traveling = False
        self.schedule = schedule
        self.next_move = self.schedule.popitem(last=False) if self.schedule else None
        self.pos = (geometry.x, geometry.y)  # Establecer posición inicial correctamente
        self.destination = self.next_move[1][1] if self.next_move else None
        self.my_path = []
        self.step_in_path = 0
        self.color = "red"
        self.path_trail = []
        self.active = True
        self.has_reached_destination = False 
        self.progress = 0.0  # Progreso acumulado en el tramo actual

        # Parámetros adicionales
        self.evacuation_centers = evacuation_centers  # Centros posibles de evacuación
        self.fire_focus = fire_focus  # Foco de incendio
        self.should_evacuate = False  # Bandera que indica si el agente debe evacuar

        # Define el tiempo por paso en segundos
        self.time_per_step = model.time_per_step if hasattr(model, 'time_per_step') else 300

        # Calcular el tiempo de evacuación según las probabilidades
        self.evacuation_time = self._calculate_evacuation_time()

    def step(self):
        """Define el comportamiento del agente en cada paso."""
        print(f"Agente {self.unique_id}: posición actual = {self.pos}, foco de incendio = {self.fire_focus}")

        if not self.should_evacuate:
            # Verifica si el agente tiene un tiempo diferido
            if self.evacuation_time is not None:
                self.evacuation_time -= self.model.time_per_step / 60  # Reduce el tiempo en minutos
                if self.evacuation_time <= 0:
                    self.evacuation_time = None
                    self._check_proximity_to_fire()
                self.color = "yellow"  # En espera
            else:
                self.color = "gray"  # No evacúa
        elif self.should_evacuate:
            # Si debe evacuar, realiza el movimiento
            self._move()
            if self.traveling:
                self.color = "green"  # Evacuando
            elif self.has_reached_destination:
                self.color = "blue"  # Llegó al destino

    def _prepare_to_move(self) -> None:
        """Prepara al agente para moverse, asignándole una ruta."""
        self.model.space.move_commuter(self, pos=self.pos)
        self.traveling = True
        self._path_select()

    def _move(self):
        """Mueve al agente hacia su destino nodo a nodo."""
        if not self.should_evacuate or not self.traveling or not self.my_path:
            return

        # Verificar si el agente ha alcanzado el último nodo en la ruta
        if self.step_in_path >= len(self.my_path) - 1:
            self.pos = self.destination
            self.traveling = False
            self.color = "blue"  # Cambiar el color al llegar al destino
            self.has_reached_destination = True  # Marcar como llegado
            print(f"Agente {self.unique_id} llegó al destino final: {self.destination}")
            return

        # Avanzar al siguiente nodo en el camino
        self.step_in_path += 1
        next_node = self.my_path[self.step_in_path]
        self.model.space.move_commuter(self, next_node)
        self.pos = next_node
        print(f"Agente {self.unique_id} se movió al nodo: {next_node}")

    def _path_select(self):
        """Calcula la ruta más corta para el agente."""
        if not self.destination or not self.pos:
            print(f"Agente {self.unique_id}: posición o destino inválido. Pos: {self.pos}, Destino: {self.destination}")
            self.my_path = []
            return

        if self.pos == self.destination:
            print(f"Agente {self.unique_id} ya está en el destino: {self.destination}")
            self.my_path = []
            return

        shortest_path_vertices = self.model.get_shortest_path(self.pos, self.destination)
        if not shortest_path_vertices:
            print(f"Agente {self.unique_id}: no se pudo calcular una ruta desde {self.pos} a {self.destination}")
            self.my_path = []
            return

        # Convertir vértices a coordenadas
        self.my_path = [
            self.model.vertex_to_coord[vertex]
            for vertex in shortest_path_vertices
            if vertex in self.model.vertex_to_coord
        ]
        print(f"Agente {self.unique_id}: Ruta generada -> {self.my_path}")

    def _redistribute_path_vertices(self) -> None:
        """Distribuye puntos en la ruta para simular un movimiento más fluido."""
        if len(self.my_path) > 1:
            original_path = LineString([Point(p) for p in self.my_path])
            reduced_speed = self.speed * 10.0  # Ajusta velocidad
            redistributed_path = redistribute_vertices(original_path, reduced_speed)
            self.my_path = list(redistributed_path.coords)

    def _calculate_evacuation_time(self):
        """Calcula el tiempo de evacuación del agente basado en probabilidades."""
        rand = random.random()  # Genera un número entre 0 y 1
        if rand < 0.30:  # 30%: Tiempo promedio para empezar a evacuar (12 minutos)
            return 12
        elif rand < 0.52:  # 22%: Tiempo superior al promedio de evacuación (20 minutos)
            return 20
        elif rand < 0.63:  # 11%: Tiempo menor al promedio de evacuación (5 minutos)
            return 5
        else:  # 37%: No evacua
            return None  # Representa que no evacuará
        
    def _check_proximity_to_fire(self):
        if self.fire_focus is None:
            return

        fire_point = Point(self.fire_focus)
        agent_point = Point(self.pos)

        # Calcular distancia directamente en grados
        distance_to_fire = agent_point.distance(fire_point)

        # Usar el valor correcto del radio
        print(f"Agente {self.unique_id}: distancia al fuego = {distance_to_fire}, radio de evacuación = {self.model.fire_radius_value}")

        if distance_to_fire <= self.model.fire_radius_value:
            print(f"Agente {self.unique_id}: dentro del radio de evacuación.")
            if self.evacuation_time is None:
                self.should_evacuate = True
                self._assign_evacuation_center()
        else:
            print(f"Agente {self.unique_id}: fuera del radio de evacuación.")
            self.should_evacuate = False

    def _assign_evacuation_center(self):
        """Asigna un centro de evacuación y calcula la ruta."""
        if not self.evacuation_centers:
            print(f"Agente {self.unique_id}: No hay centros de evacuación disponibles.")
            return

        # Asignar un centro de evacuación aleatorio
        self.destination = random.choice(self.evacuation_centers)
        self.traveling = True
        self._path_select()
        print(f"Agente {self.unique_id} asignado al centro de evacuación: {self.destination}"
              )
        
class MarkerAgent(mg.GeoAgent):
    """Agente para representar puntos en el mapa (foco de incendio, centros de evacuación)."""
    def __init__(self, unique_id, model, geometry, crs, color="pink"):
        super().__init__(unique_id, model, geometry, crs)

class FireRadiusAgent(mg.GeoAgent):
    """Agente visual para representar el radio del fuego."""
    def __init__(self, unique_id, model, geometry, crs, radius):
        super().__init__(unique_id, model, geometry.buffer(radius), crs)
        self.radius = radius
