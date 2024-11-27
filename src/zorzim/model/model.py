import uuid
import time
import random
from functools import partial
import os

import pandas as pd
import geopandas as gpd
import mesa
import mesa_geo as mg
from pyrosm import OSM
from shapely.geometry import Point, LineString, MultiLineString
from graph_tool.all import Graph, shortest_path

from zorzim.agent.commuter import Commuter, MarkerAgent, FireRadiusAgent
from zorzim.model.demand_model import DemandGenerationModel, RandomDemandGenerationModel
from zorzim.model.mode_model import ModalSplitModel, WalkingAndCyclingModel
from zorzim.space.city import City
from zorzim.space.road_network import DrivingNetwork, WalkingNetwork


def get_time(model) -> pd.Timedelta:
    return pd.Timedelta(days=model.day, hours=model.time // 60, minutes=model.time % 60)

def get_num_commuters_by_status(model, traveling: bool) -> int:
    return sum(1 for commuter in model.schedule.agents if commuter.traveling == traveling)

def get_got_to_destination(model) -> int:
    return model.got_to_destination

def get_time_in_hours(model):
    # Convierte pasos a horas (asumiendo 1 paso = 5 minutos)
    return model.time // 60

class ZorZim(mesa.Model):
    def __init__(
        self,
        osm_object: OSM,
        data_crs: str,
        model_crs: str,
        num_commuters,
        commuter_speed=1.4,
        demand_generation_model=RandomDemandGenerationModel(),
        modal_split_model=WalkingAndCyclingModel(),
        time_per_step=300
    ) -> None:
        super().__init__()
        self.osm = osm_object
        self.schedule = mesa.time.RandomActivation(self)
        self.commuter_speed = commuter_speed
        self.data_crs = data_crs
        self.model_crs = model_crs
        self.space = City(crs=model_crs)
        self.num_commuters = num_commuters
        self.demand_generation_model = demand_generation_model
        self.modal_split_model = modal_split_model
        self.time_per_step = time_per_step
        self.fire_focus = None
        self.evacuation_centers = []

        # Inicializar caché de rutas
        self.route_cache = {}  # Aquí inicializamos el caché para las rutas calculadas

        Commuter.SPEED = commuter_speed * 300.0  # meters per tick (5 minutes)

        self._load_road_vertices_from_file(osm_object, city="scl")

        self.got_to_destination = 0
        self.day = 0
        self.time = 0

        # Crear grafo de carreteras y asignar el destino común
        self.graph, self.edge_weights = self.create_road_graph()
        self.space.set_road_graph(self.graph)  # Asignar el grafo a la ciudad
        self._select_random_points()
        self.common_destination = self.get_random_road_point()
        if not self.common_destination:
            raise ValueError("No se pudo asignar un destino común. Verifica la red vial.")
        self._create_commuters()
        for agent in self.schedule.agents:
            if isinstance(agent, Commuter):
                agent.state = "waiting"
                # Asignar nuevos destinos o actividades
                agent.new_destination = self.get_random_road_point()

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "Horas": lambda m: m.time // 60,  # De minutos a horas
                "Agentes en Movimiento": lambda m: get_num_commuters_by_status(m, traveling=True),
                "Agentes en Destino": get_got_to_destination,
            },
        )
        self.datacollector.collect(self)

    def _select_random_points(self):
        # Lista de vértices disponibles en el grafo
        nodes = list(self.space.road_graph.vertices())

        # Convertir vértices a coordenadas
        nodes_coords = [self.vertex_to_coord[node] for node in nodes]

        # Seleccionar un nodo aleatorio como foco de incendio
        self.fire_focus = random.choice(nodes_coords)

        # Filtrar nodos que estén a cierta distancia del foco de incendio
        nodes_coords = [
            coord for coord in nodes_coords
            if Point(coord).distance(Point(self.fire_focus)) > 0.01  # Ajusta la distancia mínima
        ]

        # Seleccionar dos nodos diferentes como centros de evacuación
        self.evacuation_centers = random.sample(nodes_coords, 2)

        print(f"Foco de incendio: {self.fire_focus}")
        print(f"Centros de evacuación: {self.evacuation_centers}")

        # Agregar el agente para el foco de incendio
        fire_icon = MarkerAgent(
            unique_id="fire",
            model=self,
            geometry=Point(self.fire_focus),
            crs=self.model_crs,
            icon_path="assets/icons/fire.png",
        )
        self.space.add_agent(fire_icon)

        # Agregar el agente visual para el radio del fuego
        fire_radius = FireRadiusAgent(
            unique_id="fire_radius",
            model=self,
            geometry=Point(self.fire_focus).buffer(0.02),  # Crea un círculo alrededor del foco
            crs=self.model_crs,
            radius=0.02,  # Radio del círculo (en unidades de longitud/latitud)
        )
        self.space.add_agent(fire_radius)

        # Agregar íconos para los centros de evacuación
        for i, center in enumerate(self.evacuation_centers):
            shelter_icon = MarkerAgent(
                unique_id=f"shelter_{i}",
                model=self,
                geometry=Point(center),
                crs=self.model_crs,
                icon_path="assets/icons/shelter.png",
            )
            self.space.add_agent(shelter_icon)

    def _create_commuters(self) -> None:
        for i in range(self.num_commuters):
            start_position = self.demand_generation_model.get_random_building()

            # Asegurar que `start_position` sea válido
            if not start_position:
                print(f"Error: No se encontró una posición inicial válida para el agente {i}.")
                continue

            commuter_id = uuid.uuid4().int
            
            # Crear el agente commuter
            commuter = Commuter(
                unique_id=commuter_id,
                model=self,
                geometry=Point(start_position),
                crs=self.model_crs,
                schedule=None,
                speed=self.commuter_speed,
                evacuation_centers=self.evacuation_centers,
                fire_focus=self.fire_focus  # Pasar el foco de incendio
            )

            # Validar `common_destination`
            if not self.common_destination:
                raise ValueError("Error: El destino común no está definido.")

            # Asignar destino y agregar al espacio
            commuter.destination = self.common_destination
            self.space.add_commuter(commuter)
            self.schedule.add(commuter)

    def _load_road_vertices_from_file(self, osm_object: OSM, city=None) -> None:
        self.modal_split_model.fit(city=city, data_crs=self.data_crs, model_crs=self.model_crs, osm_object=osm_object)
        self.walkway = WalkingNetwork(city=city, data_crs=self.data_crs, model_crs=self.model_crs, osm_object=osm_object)
        self.driveway = DrivingNetwork(city=city, data_crs=self.data_crs, model_crs=self.model_crs, osm_object=osm_object)

    def step(self):
        """Ejecución de un paso de simulación."""
        self.__update_clock()

        # Actualizar todos los agentes
        for agent in self.schedule.agents:
            if isinstance(agent, Commuter):
                agent.step()  # Actualizar el estado del agente

        # Recolectar datos
        self.datacollector.collect(self)

        # Verificar si todos los agentes que debían evacuar han terminado
        agents_to_evacuate = [
            agent for agent in self.schedule.agents
            if isinstance(agent, Commuter) and agent.should_evacuate
        ]

        all_done = all(agent.has_reached_destination for agent in agents_to_evacuate)

        if all_done:
            print("Todos los agentes que debían evacuar han llegado a su destino. Deteniendo simulación.")
            self.running = False
        else:
            print(f"Aún hay {len(agents_to_evacuate)} agentes evacuando o en movimiento.")

    def __update_clock(self):
        self.time += 5  # Incrementa en 5 minutos por step
        if self.time >= 1440:  # 1440 minutos = 1 día
            self.day += 1
            self.time = 0

    def get_random_road_point(self):
        """Selecciona un punto aleatorio en la red vial."""
        if not self.coord_to_vertex:
            raise ValueError("Error: El grafo de la red vial no tiene nodos disponibles.")
        
        random_vertex = random.choice(list(self.coord_to_vertex.values()))
        for coord, vertex in self.coord_to_vertex.items():
            if vertex == random_vertex:
                return coord

        raise ValueError("Error: No se pudo mapear el nodo aleatorio a coordenadas.")

    def create_road_graph(self):
        roads = self.osm.get_network(network_type="all")
        G = Graph(directed=False)
        edge_weights = G.new_edge_property("double")
        self.coord_to_vertex = {}
        self.vertex_to_coord = {}

        for _, road in roads.iterrows():
            geometry = road["geometry"]
            if isinstance(geometry, MultiLineString):
                for line in geometry.geoms:
                    if len(line.coords) > 1:
                        self._add_edges_to_graph(G, edge_weights, line.coords)
            elif isinstance(geometry, LineString) and len(geometry.coords) > 1:
                self._add_edges_to_graph(G, edge_weights, geometry.coords)

        print(f"Número de nodos en el grafo: {G.num_vertices()}")
        print(f"Número de conexiones en el grafo: {G.num_edges()}")

        self.vertex_to_coord = {v: coord for coord, v in self.coord_to_vertex.items()}
        return G, edge_weights

    def _add_edges_to_graph(self, G, edge_weights, coords):
        for i in range(len(coords) - 1):
            start, end = coords[i], coords[i + 1]
            if start not in self.coord_to_vertex:
                self.coord_to_vertex[start] = G.add_vertex()
            if end not in self.coord_to_vertex:
                self.coord_to_vertex[end] = G.add_vertex()
            v_start = self.coord_to_vertex[start]
            v_end = self.coord_to_vertex[end]
            edge = G.add_edge(v_start, v_end)
            edge_weights[edge] = Point(start).distance(Point(end))

    def get_shortest_path(self, origin, destination):
        if not self.validate_position_in_network(origin) or not self.validate_position_in_network(destination):
            return []
        try:
            origin_vertex = self._get_closest_vertex(origin)
            destination_vertex = self._get_closest_vertex(destination)
            path = shortest_path(self.graph, source=origin_vertex, target=destination_vertex, weights=self.edge_weights)[0]
            return path
        except Exception:
            return []

    def validate_position_in_network(self, position):
        if not self.coord_to_vertex:
            raise ValueError("El diccionario coord_to_vertex está vacío.")
        closest_vertex = self._get_closest_vertex(position)
        closest_coord = [coord for coord, vertex in self.coord_to_vertex.items() if vertex == closest_vertex]
        return closest_coord and Point(position).distance(Point(closest_coord[0])) <= 100

    def _get_closest_vertex(self, position):
        return min(
            self.coord_to_vertex.values(),
            key=lambda v: Point(position).distance(
                Point(list(self.coord_to_vertex.keys())[list(self.coord_to_vertex.values()).index(v)])
            ),
        )
    
    def get_random_building(self):
        if not self.building_coords:
            raise ValueError("Error: No hay coordenadas de edificios disponibles.")
        return random.choice(self.building_coords)
