import argparse
from pathlib import Path
import mesa
from mesa_geo.visualization import MapModule
import mesa_geo as mg
from pyrosm import OSM
from zorzim.model.demand_model import RandomValparaisoDemandModel  
from zorzim.model.model import ZorZim
from zorzim.visualization.server import agent_draw, clock_element, status_chart, trip_chart
from zorzim.agent.commuter import Commuter, MarkerAgent

def make_parser():
    """Configura los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Agents and Networks in Python")
    parser.add_argument("-b", "--batch", action="store_true", help="Ejecutar en modo batch (sin visualización)")
    parser.add_argument("--pbf", type=str, required=True, help="Archivo PBF para cargar datos OSM")
    return parser

def load_osm_file(pbf_file_path):
    """Carga un archivo OSM PBF."""
    if not pbf_file_path.is_file():
        raise ValueError(f"Archivo no encontrado: {pbf_file_path}")
    return OSM(str(pbf_file_path))

def create_model(osm, num_commuters=10, commuter_speed=1.4, dgmodel=None):
    """Crea el modelo ZorZim con parámetros dados."""
    return ZorZim(
        osm_object=osm,
        data_crs="epsg:4326",
        model_crs="epsg:4326",
        num_commuters=num_commuters,
        commuter_speed=commuter_speed,
        demand_generation_model=dgmodel,
    )

def agent_portrayal(agent):
    if isinstance(agent, MarkerAgent):
        print(f"Renderizando MarkerAgent: {agent.unique_id} con color {agent.color}")
        return {
            "Shape": "circle",
            "Color": agent.color,  # Forzado para confirmar la representación
            "Filled": "true",
            "r": 5,
            "Layer": 1
        }
    elif isinstance(agent, Commuter):
        print(f"Renderizando Commuter: {agent.unique_id} con color {agent.color}")
        return {
            "Shape": "circle",
            "Color": agent.color,
            "Filled": "true",
            "r": 3,
            "Layer": 1
        }
    return {}
if __name__ == "__main__":
    args = make_parser().parse_args()

    # Define la ruta del archivo OSM
    OSM_PATH = Path("/home/paula/zorzim/data/external/OSM/")
    pbf_file_path = OSM_PATH / f"{args.pbf}.osm.pbf"

    try:
        osm = load_osm_file(pbf_file_path)

        # Modelo de demanda aleatoria
        dgmodel = RandomValparaisoDemandModel(osm_file_path=str(pbf_file_path), num_trips=3)

        # Configuración de parámetros del modelo
        # Aquí se cambian el número de commuters
        model_params = {
            "osm_object": osm,
            "data_crs": "epsg:4326",
            "model_crs": "epsg:4326",
            "num_commuters": 100,
            "commuter_speed": 1.4,
            "demand_generation_model": dgmodel,
        }

        if args.batch:
            # Ejecución en modo batch
            model = create_model(osm, num_commuters=100, commuter_speed=1.4, dgmodel=dgmodel)
            for _ in range(10):
                model.step()
            print("Simulación completada en modo batch.")
        else:
            # Configuración del servidor de visualización
            map_element = MapModule(
                portrayal_method=agent_draw,  # Vincular con la función agent_draw
                map_height=600,              # Ajustar tamaño del mapa
                map_width=800,
                zoom=15                      # Nivel de zoom inicial
            )

            server = mesa.visualization.ModularServer(
                ZorZim,
                [map_element, clock_element, status_chart, trip_chart],
                "Simulación de Evacuación ZorZim",
                model_params,
            )

            server.launch()

    except ValueError as e:
        print(f"Error: {e}")
