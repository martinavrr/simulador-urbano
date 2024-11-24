'''
Classes for modal split models and their algorithms and properties.
'''
import abc
from mesa.space import FloatCoordinate
from pyrosm import OSM
from zorzim.model.mode import Mode, SingleStageNetworkMode
from zorzim.space.city import get_distance
from zorzim.space.road_network import RoadNetwork, CyclingNetwork, DrivingNetwork, WalkingNetwork
from zorzim.space.utils import Mode, SingleStageNetworkMode, get_distance

class ModalSplitModel(abc.ABC):
    '''
    Base abstract class for every modal split model.
    '''
    data_crs: str
    model_crs: str


    @abc.abstractmethod
    def fit(self, city: str, data_crs: str, model_crs: str, osm_object: OSM) -> None:
        pass

    @abc.abstractmethod
    def predict(
        self,
        origin: FloatCoordinate,
        destination: FloatCoordinate,
        time: int
    ) -> Mode:
        pass


    def predict_proba(
        self,
        origin: FloatCoordinate,
        destination: FloatCoordinate,
        time: int
    ) -> Mode:
        pass


class WalkingAndCyclingModel(ModalSplitModel):
    '''
    Simple model where people either walk or ride a bicycle depending on the distance between
    the origin and destination points, according to an arbitrary threshold value.
    '''
    threshold: float
    walking_speed: float
    cycling_speed: float
    walking_mode: SingleStageNetworkMode
    cycling_mode: SingleStageNetworkMode

    def __init__(
            self,
            threshold = 1000.0,
            walking_speed = 1.4,
            cycling_speed = 6.0
        ) -> None:
        self.threshold = threshold
        self.walking_speed = walking_speed
        self.cycling_speed = cycling_speed


    def fit(self, city: str, data_crs: str, model_crs: str, osm_object: OSM) -> None:
        self.data_crs = data_crs
        self.model_crs = model_crs
        self.walking_mode = SingleStageNetworkMode(
            self.walking_speed,
            WalkingNetwork(
                city=city,
                data_crs=self.data_crs,
                model_crs=self.model_crs,
                osm_object=osm_object
            )
        )
        self.cycling_mode = SingleStageNetworkMode(
            self.cycling_speed,
            CyclingNetwork(
                city=city,
                data_crs=self.data_crs,
                model_crs=self.model_crs,
                osm_object=osm_object
            )
        )


    def predict(self, origin: FloatCoordinate, destination: FloatCoordinate, time: int) -> Mode:
        from zorzim.space.city import get_distance  #Importación 

        if get_distance(origin, destination) >= self.threshold:
            return self.cycling_mode

        return self.walking_mode

