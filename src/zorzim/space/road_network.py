from __future__ import annotations
from cytoolz import keymap, valmap

import pickle
from typing import Dict, List, Tuple, Optional
from pathlib import Path

import geopandas as gpd
import pyproj
import graph_tool as gt
import mesa
import numpy as np
from pyrosm import OSM
from sklearn.neighbors import KDTree
from aves.models.network import Network


class RoadNetwork:
    _gt_graph: gt.Graph
    _kd_tree: KDTree
    _data_crs: pyproj.CRS
    _model_crs: pyproj.CRS

    def __init__(self, osm_object: OSM, data_crs: str , model_crs: str , network_type):
        self._data_crs = data_crs
        self._model_crs = model_crs

        nodes, edges = osm_object.get_network(nodes=True, network_type=network_type)

        nodes = nodes.set_crs(data_crs, allow_override=True).to_crs(model_crs)
        edges = edges.set_crs(data_crs, allow_override=True).to_crs(model_crs)

        network = Network.from_edgelist(
            edges,
            source="u",
            target="v",
            weight="length",
        )

        lista_ids = network.node_map.keys()
        indexed_nodes = nodes.set_index('id').loc[lista_ids]

        vprop_x = network.network.new_vp("double", vals=list(indexed_nodes.geometry.x))
        vprop_y = network.network.new_vp("double", vals=list(indexed_nodes.geometry.y))
        network.network.vp["x"] = vprop_x
        network.network.vp["y"] = vprop_y

        self.gt_graph = network.network

    @property
    def gt_graph(self) -> gt.Graph:
        return self._gt_graph

    @gt_graph.setter
    def gt_graph(self, gt_graph) -> None:
        self._gt_graph = gt_graph
        self._kd_tree = KDTree(np.vstack((list(self.gt_graph.vp["x"]), list(self.gt_graph.vp["y"]))).T)

    @property
    def crs(self) -> pyproj.CRS:
        return self._model_crs

    @crs.setter
    def crs(self, crs) -> None:
        self._model_crs = crs

    def node_to_pos(
            self, node: gt.Vertex
    ) -> mesa.space.FloatCoordinate:
        return (self.gt_graph.vp["x"][node], self.gt_graph.vp["y"][node])
    
    def pos_to_node(
            self, pos: mesa.space.FloatCoordinate
    ) -> gt.Vertex:
        v_index = self._kd_tree.query([pos], k=1, return_distance=False)[0][0]
        return self.gt_graph.vertex(v_index)

    def get_nearest_node(
        self, float_pos: mesa.space.FloatCoordinate
    ) -> mesa.space.FloatCoordinate:
        v_index = self._kd_tree.query([float_pos], k=1, return_distance=False)[0][0]
        return (self.gt_graph.vp["x"][v_index], self.gt_graph.vp["y"][v_index])

    def get_shortest_path(
        self, source: mesa.space.FloatCoordinate, target: mesa.space.FloatCoordinate
    ) -> List[mesa.space.FloatCoordinate]:
        source_node = self.pos_to_node(source)
        target_node = self.pos_to_node(target)
        shortest_path = gt.topology.shortest_path(
            self.gt_graph, source_node, target_node, self._gt_graph.ep["edge_weight"])
        path = list(map(self.node_to_pos, shortest_path[0]))
        return path

class CyclingNetwork(RoadNetwork):
    city: str
    _path_select_cache: Dict[
        Tuple[mesa.space.FloatCoordinate, mesa.space.FloatCoordinate],
        List[mesa.space.FloatCoordinate],
    ]

    def __init__(self, city: str, data_crs: str, model_crs: str, osm_object: OSM) -> None:
        super().__init__(osm_object=osm_object, data_crs=data_crs , model_crs=model_crs, network_type="cycling")
        self.city = city
        CACHE_PATH = Path(__file__).parent.parent.parent.parent / "outputs"
        self._path_cache_result = CACHE_PATH / f"{city}_cycling_cache_result.pkl"
        try:
            with open(self._path_cache_result, "rb") as cached_result:
                self._path_select_cache = pickle.load(cached_result)
        except FileNotFoundError:
            self._path_select_cache = dict()

    def cache_path(
        self,
        source: mesa.space.FloatCoordinate,
        target: mesa.space.FloatCoordinate,
        path: List[mesa.space.FloatCoordinate],
    ) -> None:
        print(f"caching path... current number of cached paths: {len(self._path_select_cache)}")
        self._path_select_cache[(source, target)] = path
        # self._path_select_cache[(target, source)] = list(reversed(path))
        with open(self._path_cache_result, "wb") as cached_result:
            pickle.dump(self._path_select_cache, cached_result)


class DrivingNetwork(RoadNetwork):
    city: str
    _path_select_cache: Dict[
        Tuple[mesa.space.FloatCoordinate, mesa.space.FloatCoordinate],
        List[mesa.space.FloatCoordinate],
    ]

    def __init__(self, city: str, data_crs: str, model_crs: str, osm_object: OSM) -> None:
        super().__init__(osm_object=osm_object, data_crs=data_crs , model_crs=model_crs, network_type="driving")
        self.city = city
        CACHE_PATH = Path(__file__).parent.parent.parent.parent / "outputs"
        self._path_cache_result = CACHE_PATH / f"{city}_driving_cache_result.pkl"
        try:
            with open(self._path_cache_result, "rb") as cached_result:
                self._path_select_cache = pickle.load(cached_result)
        except FileNotFoundError:
            self._path_select_cache = dict()

    def cache_path(
        self,
        source: mesa.space.FloatCoordinate,
        target: mesa.space.FloatCoordinate,
        path: List[mesa.space.FloatCoordinate],
    ) -> None:
        print(f"caching path... current number of cached paths: {len(self._path_select_cache)}")
        self._path_select_cache[(source, target)] = path
        # self._path_select_cache[(target, source)] = list(reversed(path))
        with open(self._path_cache_result, "wb") as cached_result:
            pickle.dump(self._path_select_cache, cached_result)

    def get_cached_path(
        self, source: mesa.space.FloatCoordinate, target: mesa.space.FloatCoordinate
    ) -> Optional[List[mesa.space.FloatCoordinate]]:
        return self._path_select_cache.get((source, target), None)

class WalkingNetwork(RoadNetwork):
    city: str
    _path_select_cache: Dict[
        Tuple[mesa.space.FloatCoordinate, mesa.space.FloatCoordinate],
        List[mesa.space.FloatCoordinate],
    ]

    def __init__(self, city: str, data_crs: str, model_crs: str, osm_object: OSM) -> None:
        super().__init__(osm_object=osm_object, data_crs=data_crs , model_crs=model_crs, network_type="walking")
        self.city = city
        CACHE_PATH = Path(__file__).parent.parent.parent.parent / "outputs"
        self._path_cache_result = CACHE_PATH / f"{city}_walking_cache_result.pkl"
        try:
            with open(self._path_cache_result, "rb") as cached_result:
                self._path_select_cache = pickle.load(cached_result)
        except FileNotFoundError:
            self._path_select_cache = dict()

    def cache_path(
        self,
        source: mesa.space.FloatCoordinate,
        target: mesa.space.FloatCoordinate,
        path: List[mesa.space.FloatCoordinate],
    ) -> None:
        print(f"caching path... current number of cached paths: {len(self._path_select_cache)}")
        self._path_select_cache[(source, target)] = path
        self._path_select_cache[(target, source)] = list(reversed(path))
        with open(self._path_cache_result, "wb") as cached_result:
            pickle.dump(self._path_select_cache, cached_result)

    def get_cached_path(
        self, source: mesa.space.FloatCoordinate, target: mesa.space.FloatCoordinate
    ) -> Optional[List[mesa.space.FloatCoordinate]]:
        return self._path_select_cache.get((source, target), None)