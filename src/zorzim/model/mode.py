'''
Classes for modes of transportation for commuters and their properties.
'''
import abc
from typing import List
from mesa.space import FloatCoordinate
from zorzim.space.road_network import RoadNetwork

class Mode(abc.ABC):
    '''
    Base abstract class for every mode of transportation.
    '''
    name: str

    @abc.abstractmethod
    def get_shortest_path(
        self,
        origin: FloatCoordinate,
        destination: FloatCoordinate
    ) -> List[FloatCoordinate]:
        pass

class SingleStageFreeMode(Mode):
    '''
    Base class for any mode of transportation that follows a network and has a single stage, i.e.
    walking, cycling, driving.
    '''
    max_speed: float
    network: RoadNetwork

    def __init__(self, name: str, max_speed: float, network: RoadNetwork):
        super().__init__()
        self.name = name
        self.max_speed = max_speed
        self.network = network

    def get_shortest_path(
            self,
            origin: FloatCoordinate,
            destination: FloatCoordinate
    ) -> List[FloatCoordinate]:
        return self.network.get_shortest_path(origin, destination)

class SingleStageNetworkMode(Mode):
    '''
    Base class for any mode of transportation that follows a network and has a single stage, i.e.
    walking, cycling, driving.
    '''
    max_speed: float
    network: RoadNetwork

    def __init__(self, max_speed, network):
        super().__init__()
        self.max_speed = max_speed
        self.network = network

    def get_shortest_path(
            self,
            origin: FloatCoordinate,
            destination: FloatCoordinate
    ) -> List[FloatCoordinate]:
        return self.network.get_shortest_path(origin, destination)
