import mesa
from zorzim.agent.commuter import Commuter

class ClockElement(mesa.visualization.TextElement):
    """Elemento de texto para mostrar el reloj del modelo."""
    def render(self, model):
        """Devuelve el día y la hora actual del modelo."""
        return f"Day {model.day}, {model.time // 60:02d}:{model.time % 60:02d}"

def agent_draw(agent):
    """Define cómo se representan los agentes y sus rastros en el mapa."""
    portrayal = {
        "color": "Red" if agent.traveling else "Blue",  # Color según el estado del agente
        "radius": 5,  # Radio del agente
        "fillOpacity": 0.75,  # Opacidad del círculo
    }

    # Añadir rastro si existe
    if agent.path_trail:
        portrayal["line"] = {
            "coordinates": agent.path_trail,  # Coordenadas del rastro
            "color": "Red",  # Color de la línea del rastro
            "weight": 2,  # Ancho de la línea
            "opacity": 0.6,  # Opacidad de la línea
        }

    return portrayal

# Elemento para mostrar el reloj
clock_element = ClockElement()

# Gráfica de estado de agentes en movimiento
status_chart = mesa.visualization.ChartModule(
    [{"Label": "status_traveling", "Color": "Red"}],
    data_collector_name="datacollector",
)

# Gráfica de agentes que han llegado a su destino
trip_chart = mesa.visualization.ChartModule(
    [{"Label": "got_to_destination", "Color": "Blue"}],
    data_collector_name="datacollector",
)
