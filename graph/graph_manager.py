import glob
import os
import pickle
import random
from typing import List

from .graph_utils import create_graph_from_files

REMOVE_NODE_WITH_LESS_POINTS = 6


def format_town_name(town_name):
    town_num = town_name[4:]
    return f"Town{town_num.zfill(2)}"


class GraphManager:
    def __init__(self, input_folder, use_cache=False, cache_dir=None):

        if (
            use_cache
            and cache_dir is not None
            and os.path.exists(os.path.join(cache_dir, "graph.pkl"))
        ):
            with open(os.path.join(cache_dir, "graph.pkl"), "rb") as f:
                self.graph, self.large_junction_dict = pickle.load(f)
            self.road_compute = False
        else:
            self.graph, self.large_junction_dict = create_graph_from_files(
                glob.glob(os.path.join(input_folder, "*.xodr"))
            )
            self.road_compute = True
        self.use_cache = use_cache
        self.cache_dir = cache_dir
        self.town_name = None

    def get_node_info(self, town_name, road_id):
        for _, node in self.graph.nodes(data=True):
            if node["town_name"] == town_name and node["road_id"] == road_id:
                return node
        return None

    def get_intersection_info(self, client, vehicle_manager):
        if not self.road_compute:
            return
        town_name_to_road_indices = {}
        node_idx_to_remove = []
        for node_idx, node in self.graph.nodes(data=True):
            if node["is_junction"]:
                node_idx_to_remove.append(node_idx)
                continue
            town_name = node["town_name"]
            if town_name not in town_name_to_road_indices:
                town_name_to_road_indices[town_name] = []
            if node["number_of_right_lane"] > 0:
                town_name_to_road_indices[town_name].append(
                    (int(node["road_id"]), node_idx, "right")
                )
            if node["number_of_left_lane"] > 0:
                town_name_to_road_indices[town_name].append(
                    (int(node["road_id"]), node_idx, "left")
                )

        for town in town_name_to_road_indices:
            client.load_map(format_town_name(town))
            for road_id, node_idx, direction in town_name_to_road_indices[town]:
                # Sample point from the road with road id
                right_waypoints, left_waypoints = (
                    vehicle_manager.world_manager.get_left_right_driving_points(road_id)
                )
                if direction == "left" and len(left_waypoints) == 0:
                    print(f"{road_id} {town} {direction}")
                    self.graph.nodes[node_idx]["number_of_left_lane"] = 0
                    continue
                elif direction == "right" and len(right_waypoints) == 0:
                    print(f"{road_id} {town} {direction}")
                    self.graph.nodes[node_idx]["number_of_right_lane"] = 0
                    continue

                if (direction == "right" and len(left_waypoints) > 0) or (
                    direction == "left" and len(right_waypoints) > 0
                ):
                    self.graph.nodes[node_idx][f"{direction}_extra"]["have_opposite"] = True

                search_waypoints = right_waypoints if direction == "right" else left_waypoints
                unique_lane_id = set()
                for waypoint in search_waypoints:
                    unique_lane_id.add(waypoint.lane_id)
                unique_lane_id = list(sorted(unique_lane_id))
                lane_id = unique_lane_id[1] if len(unique_lane_id) > 1 else unique_lane_id[0]

                num_of_waypoints = len(
                    [waypoint for waypoint in search_waypoints if waypoint.lane_id == lane_id]
                )

                if num_of_waypoints < REMOVE_NODE_WITH_LESS_POINTS:
                    self.graph.nodes[node_idx][f"number_of_{direction}_lane"] = 0
                    if (
                        self.graph.nodes[node_idx]["number_of_right_lane"] == 0
                        and self.graph.nodes[node_idx]["number_of_left_lane"] == 0
                    ):
                        node_idx_to_remove.append(node_idx)
                    continue

                search_waypoints.sort(key=lambda x: x.s)
                direction_dict = vehicle_manager.get_left_straight_right(
                    search_waypoints[len(search_waypoints) // 2]
                )
                if direction_dict is None:
                    continue
                self.graph.nodes[node_idx][f"{direction}_extra"]["can_turn_left"] = (
                    "can_left" in direction_dict
                )
                self.graph.nodes[node_idx][f"{direction}_extra"]["can_turn_right"] = (
                    "can_right" in direction_dict
                )
                self.graph.nodes[node_idx][f"{direction}_extra"]["can_go_straight"] = (
                    "can_straight" in direction_dict
                )
                self.graph.nodes[node_idx][f"{direction}_extra"]["have_left_from"] = (
                    "have_left" in direction_dict
                )
                self.graph.nodes[node_idx][f"{direction}_extra"]["have_right_from"] = (
                    "have_right" in direction_dict
                )
                self.graph.nodes[node_idx][f"{direction}_extra"]["have_straight_from"] = (
                    "have_straight" in direction_dict
                )
                self.graph.nodes[node_idx][f"{direction}_extra"][
                    "num_of_waypoints"
                ] = num_of_waypoints

        # self.graph.remove_nodes_from(node_idx_to_remove)
        if self.use_cache and self.cache_dir is not None:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(os.path.join(self.cache_dir, "graph.pkl"), "wb") as f:
                pickle.dump((self.graph, self.large_junction_dict), f)
        self.road_compute = False

    def set_town_name(self, town_name):
        self.town_name = town_name

    def town_road_id_to_node_id(self, road_id):
        if not isinstance(road_id, str):
            road_id = str(road_id)
        for node_id, node in self.graph.nodes(data=True):
            if node["town_name"] == self.town_name and node["road_id"] == road_id:
                return node_id
        return None

    def node_id_to_town_road_id(self, node_id, allow_junction=False):
        node = self.graph.nodes[node_id]
        town_name, road_id = node["town_name"], node["road_id"]
        return town_name, int(road_id), node

    def find_predecessor(self, road_id, node, max_depth=3):
        road_indices = [int(road_id)]
        depth = 0
        while (
            node["predecessor"] is not None
            and node["predecessor"] in self.graph.nodes
            and depth < max_depth
        ):
            node = self.graph.nodes[node["predecessor"]]
            if int(node["road_id"]) in road_indices:
                break
            road_indices.append(int(node["road_id"]))
            depth += 1
        return road_indices

    def get_intersection(self, node_id, from_road_id=False, junction_id_list=None) -> List[set]:
        if from_road_id:
            node_id = self.town_road_id_to_node_id(node_id)
        node = self.graph.nodes[node_id]
        junction_indices = list(node["junction_list"])

        intersection_list = []

        for junction_id in junction_indices:
            town_name = node["town_name"]
            if junction_id_list is not None and junction_id not in junction_id_list:
                continue

            target_junction = self.large_junction_dict[town_name][junction_id]
            road_id_set = set()
            for _, connection_info in target_junction.items():
                incoming_road, *_ = connection_info
                if (
                    incoming_road in self.graph.nodes
                    and not self.graph.nodes[incoming_road]["is_junction"]
                ):
                    road_id_set.add(int(self.graph.nodes[incoming_road]["road_id"]))
            intersection_list.append(road_id_set)

        return intersection_list
