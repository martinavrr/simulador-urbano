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
            "Shape": "circle",
            "Color": "rgba(255, 0, 0, 0.3)",  # Color rojo translúcido
            "Filled": "true",
            "r": agent.radius * 50000,  # Ajustar el tamaño del círculo según el radio
            "Layer": 0,  # Dibujar debajo de otros elementos
        }
    elif isinstance(agent, MarkerAgent):
        # Representación de MarkerAgent (foco de incendio o centros de evacuación)
        return {
            "shape": "icon",
            "icon": agent.icon_path,  # Ruta al icono
            "scale": 1.5,            # Tamaño del icono
            "layer": 1,              # Capa superior
        }
    elif isinstance(agent, Commuter):
        # Representación de los agentes Commuter
        if agent.evacuation_time is None:
            color = "Red"  # No evacua
        elif not agent.traveling:
            color = "Yellow"  # Todavía no comienza a evacuar
        else:
            color = "Green" if agent.traveling else "Blue"  # En movimiento o llegó al destino

        return {
            "color": color,
            "radius": 3,
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