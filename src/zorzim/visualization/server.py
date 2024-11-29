import mesa
from zorzim.agent.commuter import Commuter, MarkerAgent, FireRadiusAgent
from mesa.visualization.modules import ChartModule

class ClockElement(mesa.visualization.TextElement):
    """Elemento de texto para mostrar el reloj del modelo."""
    def render(self, model):
        """Devuelve el día y la hora actual del modelo."""
        return f"Day {model.day}, {model.time // 60:02d}:{model.time % 60:02d}"

def agent_draw(agent):
    """Define cómo se representan los agentes en el mapa."""
    if isinstance(agent, FireRadiusAgent):
        # Representar el radio como un círculo transparente
        return {
            "color": "orange",
            "fillOpacity": 0.20,
            "layer": 0,  # Dibujar debajo de otros elementos
        }
    elif isinstance(agent, MarkerAgent):
        # Representación de MarkerAgent (foco de incendio o centros de evacuación)
        if "fire" in agent.unique_id:
            color = "orange"  # Foco de incendio
        elif "shelter" in agent.unique_id:
            color = "green"  # Centros de evacuación
        else:
            color = "pink"  # Color por defecto para otros casos

        return {
            "color": color,
            "radius": 7,
            "fillOpacity": 1,
        }
    
    elif isinstance(agent, Commuter):
        # Representación de los agentes Commuter
        if agent.has_reached_destination:
            color = "Green"  # Ha llegado al destino
        elif agent.traveling:
            color = "Blue"  # Está en movimiento
        elif agent.evacuation_time is not None:
            color = "Yellow"  # Tiene un tiempo de evacuación asignado pero aún no comienza
        else:
            color = "Red"  # No evacua

        return {
            "color": color,
            "radius": 4,
            "fillOpacity": 0.75,
        }
    return {}

# Elemento para mostrar el reloj
clock_element = ClockElement()

# Gráfica de estado de agentes en movimiento
status_chart = ChartModule(
    [{"Label": "Agentes en Movimiento", "Color": "Green"}],
    canvas_height=200,
    canvas_width=500
)

# Gráfica de agentes que han llegado a su destino
trip_chart = ChartModule(
    [{"Label": "Agentes en Destino", "Color": "Blue"}],
    canvas_height=200,
    canvas_width=500
)