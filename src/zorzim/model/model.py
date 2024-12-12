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
import pyproj
from shapely.ops import transform
import matplotlib.pyplot as plt
import contextily as ctx

from zorzim.agent.commuter import Commuter, MarkerAgent, FireRadiusAgent
from zorzim.model.demand_model import DemandGenerationModel, RandomDemandGenerationModel
from zorzim.model.mode_model import ModalSplitModel, WalkingAndCyclingModel
from zorzim.space.city import City
from zorzim.space.road_network import DrivingNetwork, WalkingNetwork


def get_time(model) -> pd.Timedelta:
    return pd.Timedelta(days=model.day, hours=model.time // 60, minutes=model.time % 60)

def get_num_commuters_by_status(model, traveling: bool) -> int:
    count = sum(1 for commuter in model.schedule.agents if commuter.traveling == traveling)
    print(f"Agentes {'en movimiento' if traveling else 'detenidos'}: {count}")
    return count

def get_got_to_destination(model) -> int:
    print(f"Agentes en destino: {model.got_to_destination}")
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
        time_per_step=300,
        evacuation_radius=500, # En metros
        step_interval=10,  # Número de pasos entre cambios potenciales
        change_probability=0.3,  # Probabilidad de cambio
        radius_change_amount=50,  # Magnitud del cambio (en metros)
        max_radius=1000,  # Nuevo: límite superior del radio
        min_radius=50     # Nuevo: límite inferior del radio
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
        self.evacuation_radius = evacuation_radius / 111000
        self.fire_radius_value = self.evacuation_radius  # Unifica los valores
        self.step_count = 0  # Contador de pasos
        self.step_interval = step_interval
        self.change_probability = change_probability
        self.radius_change_amount = radius_change_amount / 111000  # Convertir a grados
        self.max_radius = max_radius / 111000  # Límite superior en grados
        self.min_radius = min_radius / 111000  # Límite inferior en grados
        self.all_paths = []


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
        self._create_agent_gdf()
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

        #print(f"Foco de incendio: {self.fire_focus}")
        #print(f"Centros de evacuación: {self.evacuation_centers}")
        #if not self.validate_position_in_network(self.fire_focus):
            #print("Foco de incendio fuera del grafo de carreteras.")
        #if not all(self.validate_position_in_network(center) for center in self.evacuation_centers):
            #print("Uno o más centros de evacuación están fuera del grafo de carreteras.")

        # Crear el agente para el foco de incendio
        fire_agent = MarkerAgent(
            unique_id="fire",
            model=self,
            geometry=Point(self.fire_focus),
            crs=self.model_crs  # EPSG:4326
        )
        self.space.add_agent(fire_agent)

        # Usar un CRS proyectado temporalmente para el buffer
        transformer_to_projected = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        transformer_to_geographic = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

        # Transformar el foco de incendio a proyectado
        fire_focus_projected = transform(
            transformer_to_projected.transform,
            Point(self.fire_focus)
        )

        # Crear el buffer en coordenadas proyectadas
        fire_radius_projected = fire_focus_projected.buffer(self.fire_radius_value)

        # Transformar el buffer de regreso a EPSG:4326
        fire_radius_geographic = transform(
            transformer_to_geographic.transform,
            fire_radius_projected
        )

        # Crear el agente visual para el radio del fuego
        fire_radius_agent = FireRadiusAgent(
            unique_id="fire_radius",
            model=self,
            geometry=fire_radius_geographic,
            crs=self.model_crs,  # EPSG:4326
            radius=self.fire_radius_value
        )
        self.space.add_agent(fire_radius_agent)

        # Agregar los agentes para los centros de evacuación
        for i, center in enumerate(self.evacuation_centers):
            shelter_agent = MarkerAgent(
                unique_id=f"shelter_{i}",
                model=self,
                geometry=Point(center),  # EPSG:4326
                crs=self.model_crs
            )
            self.space.add_agent(shelter_agent)

    def _create_commuters(self) -> None:
        for i in range(self.num_commuters):
            start_position = self.demand_generation_model.get_random_building()

            # Asegurar que `start_position` sea válido
            if not start_position:
                #print(f"Error: No se encontró una posición inicial válida para el agente {i}.")
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

    def plot_agent_paths_with_map(model, output_file="agent_paths_with_map.png"):
        """
        Crea un gráfico de las rutas recorridas por los agentes sobre un mapa base.
        :param model: Instancia del modelo ZorZim.
        :param output_file: Nombre del archivo donde se guardará la imagen.
        """
        
        fig, ax = plt.subplots(figsize=(10, 10))

        # Dibujar las rutas de los agentes
        for path in model.all_paths:
            if len(path) > 1:
                x_coords, y_coords = zip(*path)
                ax.plot(x_coords, y_coords, linestyle="-", linewidth=1, alpha=0.7, color="blue")

        # Dibujar el foco de incendio
        if model.fire_focus:
            fire_x, fire_y = model.fire_focus
            ax.scatter(fire_x, fire_y, color="orange", s=100)

        # Dibujar los centros de evacuación
        for center in model.evacuation_centers:
            center_x, center_y = center
            ax.scatter(center_x, center_y, color="green", s=100)

        # Agregar el fondo del mapa
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        ctx.add_basemap(ax, crs="EPSG:4326", source=ctx.providers.OpenStreetMap.Mapnik, zoom=15)

        # Configuración del gráfico
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.axis("off")  # Eliminar ejes para una visualización más limpia
        plt.savefig(output_file, bbox_inches="tight", dpi=300)
        plt.close()

    def step(self):
        """Ejecución de un paso de simulación."""
        self.__update_clock()
        self.step_count += 1

        # Actualizar todos los agentes
        for agent in self.schedule.agents:
            if isinstance(agent, Commuter):
                agent.step()

        # Guardar rutas de todos los agentes
        self.all_paths = [
            agent.path_trail for agent in self.schedule.agents if isinstance(agent, Commuter)
        ]

        # Actualizar el radio de evacuación solo cada 'step_interval' pasos
        if self.step_count % self.step_interval == 0:
            self._maybe_change_fire_radius()

        # Verificar si todos los agentes que debían evacuar han terminado
        agents_to_evacuate = [
            agent for agent in self.schedule.agents
            if isinstance(agent, Commuter) and agent.should_evacuate
        ]

        all_done = all(agent.has_reached_destination for agent in agents_to_evacuate)

        if all_done:
            print("Todos los agentes que debían evacuar han llegado a su destino. Deteniendo simulación.")
            self.plot_agent_paths_with_map(output_file="agent_paths_with_map.png")
            self.running = False

        # Recolectar datos al final del paso
        self.datacollector.collect(self)

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

        #print(f"Número de nodos en el grafo: {G.num_vertices()}")
        #print(f"Número de conexiones en el grafo: {G.num_edges()}")

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
        """Calcula el camino más corto y evita rutas que pasen por el nodo de fuego."""
        if not self.validate_position_in_network(origin) or not self.validate_position_in_network(destination):
            return []

        try:
            origin_vertex = self._get_closest_vertex(origin)
            destination_vertex = self._get_closest_vertex(destination)

            # Calcular el camino más corto normal
            path = shortest_path(self.graph, source=origin_vertex, target=destination_vertex, weights=self.edge_weights)[0]

            # Si no hay foco de incendio, devuelve la ruta directamente
            if not self.fire_focus:
                return path

            # Verificar si el camino incluye el nodo del fuego
            fire_vertex = self._get_closest_vertex(self.fire_focus)
            if fire_vertex in path:
                #print(f"Evadiendo nodo de fuego para la ruta desde {origin} a {destination}.")
                # Crear un subgrafo excluyendo el nodo del fuego
                subgraph = Graph(self.graph, prune=True)  # Crea un subgrafo
                subgraph.remove_vertex(fire_vertex)       # Elimina el nodo del fuego

                # Recalcular la ruta en el subgrafo
                path = shortest_path(subgraph, source=origin_vertex, target=destination_vertex, weights=self.edge_weights)[0]

            return path
        except Exception as e:
            #print(f"Error calculando la ruta más corta: {e}")
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

    def _create_agent_gdf(self):
        """Crea un GeoDataFrame para los agentes con un índice espacial."""
        agent_data = [
            {"geometry": Point(agent.pos), "agent": agent}
            for agent in self.schedule.agents if isinstance(agent, Commuter)
        ]
        self.agent_gdf = gpd.GeoDataFrame(agent_data, crs="EPSG:4326")  # Ajusta el CRS según tu modelo
        self.agent_gdf.sindex  # Crea índice espacial

    def _maybe_change_fire_radius(self):
        """Decide si cambiar el radio de evacuación."""
        if random.random() < self.change_probability:
            # Define las probabilidades para disminuir, aumentar o quedarse igual
            changes = [-self.radius_change_amount, self.radius_change_amount, 0]
            probabilities = [0.2, 0.3, 0.5]  # reduce, aumenta, igual 
            
            # Selecciona el cambio basado en las probabilidades
            change = random.choices(changes, probabilities, k=1)[0]
            new_radius = self.fire_radius_value + change

            # Limitar el radio dentro del rango [min_radius, max_radius]
            new_radius = max(self.min_radius, min(self.max_radius, new_radius))

            if new_radius != self.fire_radius_value:  # Si hay un cambio en el radio
                #print(f"Radio de evacuación cambiado de {self.fire_radius_value} a {new_radius}.")
                was_smaller = new_radius > self.fire_radius_value  # Verificar si se agrandó
                self.fire_radius_value = new_radius
                self._update_fire_radius()

                if was_smaller:
                    # Notificar a los agentes solo si el radio se agrandó
                    self._notify_agents_in_radius()

    def _update_fire_radius(self):
        """Actualiza la geometría del agente del radio de evacuación."""
        for agent in self.space.agents:
            if isinstance(agent, FireRadiusAgent):
                # Crear un nuevo buffer con el radio actualizado
                agent.geometry = Point(self.fire_focus).buffer(self.fire_radius_value)
                print(f"Radio de evacuación actualizado a: {self.fire_radius_value} (grados)")
                break

    def _update_agent_gdf(self):
        """Actualiza el GeoDataFrame con las posiciones actuales de los agentes."""
        self.agent_gdf["geometry"] = [
            Point(agent.pos) for agent in self.schedule.agents if isinstance(agent, Commuter)
        ]
        self.agent_gdf.sindex  # Actualizar el índice espacial

    def _notify_agents_in_radius(self):
        """Notifica a los agentes dentro del nuevo radio de evacuación."""
        fire_point = Point(self.fire_focus)

        possible_matches_index = list(self.agent_gdf.sindex.intersection(fire_point.buffer(self.fire_radius_value).bounds))
        possible_matches = self.agent_gdf.iloc[possible_matches_index]

        for _, row in possible_matches.iterrows():
            agent = row["agent"]
            agent_point = Point(agent.pos)
            if agent_point.distance(fire_point) <= self.fire_radius_value:
                print(f"Agente {agent.unique_id} está dentro del nuevo radio de evacuación.")
                
                # Recalcular el tiempo de evacuación
                agent.evacuation_time = agent._calculate_evacuation_time()

                # Forzar al agente a reevaluar su decisión de evacuación
                agent._check_proximity_to_fire()
