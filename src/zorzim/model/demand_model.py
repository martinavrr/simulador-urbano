'''
Classes for demand generation models and their algorithms and properties.
'''
import abc
import random
from collections import OrderedDict
from pathlib import Path
import pandas as pd
from aves.data import eod
from pyrosm import OSM
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString

class DemandGenerationModel(abc.ABC):
    '''
    Base abstract class for every demand generation model.
    '''
    @abc.abstractmethod
    def get_agent_schedule(self, unique_id: int) -> OrderedDict:
        return OrderedDict()

class RandomDemandGenerationModel(DemandGenerationModel):
    '''
    Basic demand generation model for random trips.
    '''
    def __init__(self, comuna=None) -> None:
        pass

    def get_agent_schedule(self, unique_id: int) -> OrderedDict:
        return OrderedDict()

class EODDemandGenerationModel(DemandGenerationModel):
    '''
    Simple model where each agent takes on the role of an interviewee from the EOD and replicates
    their schedule.
    '''
    schedules_df: pd.DataFrame

    def __init__(self, comuna=None) -> None:
        zorzim_root = Path(__file__).parent.parent.parent.parent
        eod_path = zorzim_root / "aves" / "data" / "external" / "EOD_STGO"

        viajes = eod.read_trips(eod_path)

        if comuna is not None:
            viajes = viajes.loc[viajes["ComunaOrigen"] == comuna].loc[viajes["ComunaDestino"] == comuna]

        viajes_por_persona = viajes[["Persona", "OrigenCoordX", "OrigenCoordY", "DestinoCoordX",
                                     "DestinoCoordY", "HoraIni"]].set_index(["Persona"]).dropna()

        viajes_por_persona.loc[:, "HoraIni"] = viajes_por_persona["HoraIni"].apply(
            lambda x:pd.to_timedelta(x)/pd.offsets.Minute(1))

        self.schedules_df = viajes_por_persona

    def get_agent_schedule(self, unique_id: int) -> OrderedDict:

        trips = OrderedDict()

        index_list = self.schedules_df.index.unique()
        person = unique_id % len(index_list)

        sched = self.schedules_df.loc[[index_list[person]]].sort_values(by="HoraIni")

        for index, row in sched.iterrows():
            trips[row["HoraIni"]] = ((row["OrigenCoordX"], row["OrigenCoordY"]), (row["DestinoCoordX"], row["DestinoCoordY"]))

        return trips

class RandomValparaisoDemandModel(DemandGenerationModel):
    """
    Modelo de generación de demanda aleatoria para Valparaíso.
    Usa los edificios como posiciones de origen y puntos en las carreteras como posiciones de destino.
    """
    def __init__(self, osm_file_path: str, num_trips=2) -> None:
        # Cargar el archivo OSM
        self.osm = OSM(osm_file_path)
        self.num_trips = num_trips  # Número de viajes que cada agente realizará

        # Calcular y almacenar las coordenadas de los edificios
        self.building_coords = self._get_building_coords()

        # Obtener las coordenadas de las carreteras para destinos
        self.road_coords = self._get_road_coords()

    def _get_building_coords(self):
        """Obtiene las coordenadas de los edificios a partir del archivo OSM."""
        #print("Extrayendo coordenadas de edificios...")
        buildings = self.osm.get_buildings()
        building_coords = []

        # Recorrer cada edificio en el GeoDataFrame
        for _, row in buildings.iterrows():
            geometry = row['geometry']
            
            # Verificar si la geometría es un polígono o un multipolígono
            if isinstance(geometry, Polygon):
                # Extraer las coordenadas del polígono (centroide del edificio)
                coords = geometry.centroid.coords[0]
                building_coords.append(coords)
            elif isinstance(geometry, MultiPolygon):
                # Extraer las coordenadas de cada polígono en el multipolígono
                for polygon in geometry.geoms:
                    coords = polygon.centroid.coords[0]
                    building_coords.append(coords)

        #print(f"{len(building_coords)} edificios encontrados.")
        return building_coords

    def _get_road_coords(self):
        """Obtiene coordenadas a lo largo de las carreteras para usarlas como destinos."""
        #print("Extrayendo coordenadas de carreteras...")
        roads = self.osm.get_network(network_type="driving")  # Puedes ajustar el tipo de red
        road_coords = []

        # Recorrer cada carretera en el GeoDataFrame
        for _, row in roads.iterrows():
            geometry = row['geometry']
            
            # Verificar si la geometría es una línea o multilínea
            if isinstance(geometry, LineString):
                # Extraer puntos a lo largo de la línea
                for coord in geometry.coords:
                    road_coords.append(coord)
            elif isinstance(geometry, MultiLineString):
                # Extraer puntos de cada línea en el multilínea
                for line in geometry.geoms:
                    for coord in line.coords:
                        road_coords.append(coord)

        #print(f"{len(road_coords)} puntos de carretera encontrados.")
        return road_coords

    def get_random_building(self):
        """Selecciona una coordenada aleatoria de entre los edificios."""
        if not self.building_coords:
            raise ValueError("No hay edificios disponibles para seleccionar.")
        return random.choice(self.building_coords)

    def get_random_road_destination(self):
        """Selecciona una coordenada aleatoria de entre las carreteras."""
        return random.choice(self.road_coords)

    def get_agent_schedule(self, unique_id: int) -> OrderedDict:
        """
        Genera un horario aleatorio para un agente, con un número específico de viajes.
        Las posiciones de origen son los edificios y las posiciones de destino son puntos en las carreteras.
        """
        trips = OrderedDict()
        
        # Crear un horario con `num_trips` viajes
        for i in range(self.num_trips):
            # Generar tiempos de inicio aleatorios en el día (en minutos desde la medianoche)
            start_time = random.randint(0, 1440)  # 1440 minutos = 24 horas
            
            # Seleccionar un edificio como origen y una carretera como destino
            origin = self.get_random_building()
            destination = self.get_random_road_destination()
            
            trips[start_time] = (origin, destination)

        # Ordenar los viajes por el tiempo de inicio
        trips = OrderedDict(sorted(trips.items()))
        #print(f"Horario generado para agente {unique_id}: {trips}")
        return trips

