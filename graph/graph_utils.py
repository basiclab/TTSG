import argparse
import glob
import os
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, Tuple

import networkx as nx


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="maps")
    return parser.parse_args()


def parse_opendrive(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    return root


def create_graph(opendrive_root, in_graph=None, town_name=""):
    """
    Creating a graph from the OpenDrive file with the package: `networkx`

    The node of the graph is the {town_name}_{road id}, and the edge of the graph is the connection between the roads.

    For each node, the following information is stored:
    - length: The length of the road
    - lane_sections: The lane sections of the road
    - lane_center_indices: The indices of the center lane in the lane sections
    - signals: The signals of the road
    - objects: The objects of the road

    Signal and object information is stored as a list of dictionaries.

    The signal and object dictionaries have the following keys:
    - name: The name of the signal or object
    - type: The type of the signal or object
    - id: The id of the signal or object
    - orientation: The orientation of the signal or object. "+" means the signal is on the right side of the road, and "-" means the signal is on the left side of the road.

    Objects are items that influence a road by expanding, delimiting, or supplementing its course. The most common examples are parking spaces, crosswalks, and traffic barriers.
    Signals are traffic signs, traffic lights, and specific road marking for the control and regulation of road traffic.

    For each edge, the following information is stored:
    - junction_id: The id of the junction
    """
    if in_graph is None:
        graph = nx.DiGraph()
    else:
        graph = in_graph
    road_elements = opendrive_root.findall("road")
    available_signal_names = set()
    available_object_names = set()

    signal_mapping_dict = {}
    process_later = []
    road_id_to_idx = {}
    count_node = len(graph.nodes)
    for road_idx, road in enumerate(road_elements):
        road_id = road.get("id")
        length = road.get("length")
        predecessor = road.find("link/predecessor")
        successor = road.find("link/successor")
        signals = []
        for signal in road.findall("signals/signal"):
            if signal.get("type") != "1000001":
                signals.append(
                    {
                        "name": signal.get("name"),
                        "type": signal.get("type"),
                        "t": float(signal.get("t")),
                    }
                )
            signal_mapping_dict[signal.get("id")] = {
                "name": signal.get("name"),
                "type": signal.get("type"),
            }

        for signal in road.findall("signals/signalReference"):
            signal_id = signal.get("id")
            if signal_id not in signal_mapping_dict:
                process_later.append((signal, road_id))
                continue
            if signal_mapping_dict[signal_id]["type"] != "1000001":
                signals.append(
                    {
                        "name": signal_mapping_dict[signal_id]["name"],
                        "type": signal_mapping_dict[signal_id]["type"],
                        "t": float(signal.get("t")),
                    }
                )

        for signal in signals:
            available_signal_names.add(signal.get("type"))
        objects = []
        for object_ in road.findall("objects/object"):
            if road.get("junction") == "-1" or object_.get("type") != "crosswalk":
                objects.append(
                    {
                        "name": object_.get("name"),
                        "type": object_.get("type"),
                        "t": -1 if float(object_.get("s")) > 10 else 1,
                    }
                )
            else:  # Junction with cross road
                s = float(object_.get("s"))
                if s > 10:  # successor
                    contact_point = successor.get("contactPoint")
                    real_road_id = successor.get("elementId")
                else:  # predecessor
                    contact_point = predecessor.get("contactPoint")
                    real_road_id = predecessor.get("elementId")

                if int(real_road_id) in road_id_to_idx:
                    node = graph.nodes[road_id_to_idx[int(real_road_id)]]
                    node["objects"].append(
                        {
                            "name": object_.get("name"),
                            "type": object_.get("type"),
                            "t": 1 if contact_point == "start" else -1,
                        }
                    )

        for object_ in objects:
            available_object_names.add(object_.get("name"))
        left_lane_sections = []
        right_lane_sections = []
        number_of_left_lane = []
        number_of_right_lane = []
        lane_sections = road.findall("lanes/laneSection")
        right_extra = []
        left_extra = []
        for lane_section in lane_sections:
            # left lane
            left_lanes = lane_section.findall("left/lane")
            left_lanes.sort(key=lambda x: int(x.get("id")), reverse=True)
            left_lane_sections.append(
                [
                    {
                        "type": left_lane.get("type"),
                        "id": int(left_lane.get("id")),
                    }
                    for left_lane in left_lanes
                ]
            )
            number_of_left_lane.append(
                len([lane for lane in left_lanes if lane.get("type") == "driving"])
            )
            left_extra.append(
                {
                    "have_shoulder": any(
                        [lane["type"] == "shoulder" for lane in left_lane_sections[-1]]
                    ),
                    "have_sidewalk": any(
                        [lane["type"] == "sidewalk" for lane in left_lane_sections[-1]]
                    ),
                    "can_turn_left": False,
                    "can_turn_right": False,
                    "can_go_straight": False,
                    "have_left_from": False,
                    "have_right_from": False,
                    "have_straight_from": False,
                    "have_opposite": False,
                    "num_of_waypoints": 0,
                }
            )

            # right lane
            right_lanes = lane_section.findall("right/lane")
            right_lanes.sort(key=lambda x: int(x.get("id")))
            right_lane_sections.append(
                [
                    {
                        "type": right_lane.get("type"),
                        "id": int(right_lane.get("id")),
                    }
                    for right_lane in right_lanes
                ]
            )
            number_of_right_lane.append(
                len([lane for lane in right_lanes if lane.get("type") == "driving"])
            )
            right_extra.append(
                {
                    "have_shoulder": any(
                        [lane["type"] == "shoulder" for lane in right_lane_sections[-1]]
                    ),
                    "have_sidewalk": any(
                        [lane["type"] == "sidewalk" for lane in right_lane_sections[-1]]
                    ),
                    "can_turn_left": False,
                    "can_turn_right": False,
                    "can_go_straight": False,
                    "have_left_from": False,
                    "have_right_from": False,
                    "have_straight_from": False,
                    "have_opposite": False,
                    "num_of_waypoints": 0,
                }
            )

        min_left_val = min(number_of_left_lane)
        min_idx = number_of_left_lane.index(min_left_val) if min_left_val != 0 else None
        left_lane_sections = left_lane_sections[min_idx] if min_idx is not None else []
        left_extra = left_extra[min_idx] if min_idx is not None else None
        min_right_val = min(number_of_right_lane)
        min_idx = number_of_right_lane.index(min_right_val) if min_right_val != 0 else None
        right_lane_sections = right_lane_sections[min_idx] if min_idx is not None else []
        right_extra = right_extra[min_idx] if min_idx is not None else None

        road_id_to_idx[int(road_id)] = count_node + road_idx
        graph.add_node(
            count_node + road_idx,
            town_name=town_name,
            road_id=road_id,
            length=length,
            signals=signals,
            objects=objects,
            junction_list=[],
            right_lane_sections=right_lane_sections,
            number_of_right_lane=min_right_val,
            right_extra=right_extra,
            left_lane_sections=left_lane_sections,
            number_of_left_lane=min_left_val,
            left_extra=left_extra,
            is_junction=road.get("junction") != "-1",
            predecessor=(
                count_node + int(predecessor.get("elementId"))
                if predecessor is not None and predecessor.get("elementType") != "junction"
                else None
            ),
            successor=(
                count_node + int(successor.get("elementId"))
                if successor is not None and successor.get("elementType") != "junction"
                else None
            ),
        )

    for signal, road_id in process_later:
        signal_id = signal.get("id")
        node_idx = road_id_to_idx[int(road_id)]
        if signal_mapping_dict[signal_id]["type"] != "1000001":
            graph.nodes[node_idx]["signals"].append(
                {
                    "name": signal_mapping_dict[signal_id]["name"],
                    "type": signal_mapping_dict[signal_id]["type"],
                    "id": signal_id,
                    "orientation": signal.get("orientation"),
                    "t": float(signal.get("t")),
                }
            )

    controller_mapping = defaultdict(set)
    controllers = opendrive_root.findall("controller")
    for controller in controllers:
        get_all_control = controller.findall("control")
        for control in get_all_control:
            controller_mapping[controller.get("id")].add(control.get("signalId"))

    junction_dict = {}
    junction_elements = opendrive_root.findall("junction")
    for junction in junction_elements:
        connections = junction.findall("connection")
        junction_dict[junction.get("id")] = {}
        added_road = set()

        # Process for traffic light
        have_traffic = False
        controllers = junction.findall("controller")
        for controller in controllers:
            controller_id = controller.get("id")
            signal_ids = controller_mapping[controller_id]
            for signal_id in signal_ids:
                signal_type = signal_mapping_dict[signal_id]["type"]
                if signal_type == "1000001":
                    have_traffic = True
                    break
            if have_traffic:
                break

        for connection in connections:
            incoming_road = road_id_to_idx[int(connection.get("incomingRoad"))]
            connecting_road = road_id_to_idx[int(connection.get("connectingRoad"))]
            contact_point = connection.get("contactPoint")
            lane = connection.findall("laneLink")[0]
            check_lane_id = lane.get("from" if contact_point == "end" else "to")
            if have_traffic:
                graph.nodes[incoming_road]["signals"].append(
                    {
                        "name": "Signal_3Light_Post01",
                        "type": "1000001",
                        "t": 1 if int(check_lane_id) > 0 else -1,
                    }
                )

            # Get signals and objects from the connecting road
            objects = graph.nodes[connecting_road]["objects"]
            signals = graph.nodes[connecting_road]["signals"]
            for signal in signals:
                graph.nodes[incoming_road]["signals"].append(
                    {
                        "name": signal.get("name"),
                        "type": signal.get("type"),
                        "t": 1 if int(check_lane_id) > 0 else -1,
                    }
                )
            for object_ in objects:
                if object_.get("type") != "crosswalk":
                    graph.nodes[incoming_road]["objects"].append(
                        {
                            "name": object_.get("name"),
                            "type": object_.get("type"),
                            "t": 1 if int(check_lane_id) > 0 else -1,
                        }
                    )

            from_ = incoming_road if contact_point == "start" else connecting_road
            to_ = connecting_road if contact_point == "start" else incoming_road
            graph.add_edge(
                from_,
                to_,
                junction_id=junction.get("id"),
            )
            junction_dict[junction.get("id")][connection.get("id")] = (
                incoming_road,
                connecting_road,
                contact_point,
            )
            if from_ not in added_road:
                graph.nodes[from_]["junction_list"].append(junction.get("id"))
                added_road.add(from_)
            if to_ not in added_road:
                graph.nodes[to_]["junction_list"].append(junction.get("id"))
                added_road.add(to_)

    return graph, junction_dict, available_signal_names, available_object_names


def create_graph_from_files(opendrive_files, verbose=False) -> Tuple[nx.DiGraph, Dict[str, dict]]:
    large_junction_dict = {}
    road_graph = None
    all_available_signal_names, all_available_object_names = set(), set()
    for opendrive_file in sorted(opendrive_files):
        opendrive_root = parse_opendrive(opendrive_file)
        town_name = os.path.basename(opendrive_file).split(".")[0]
        out_graph, junction_dict, available_signal_names_in_map, available_object_names_in_map = (
            create_graph(opendrive_root, in_graph=road_graph, town_name=town_name)
        )
        large_junction_dict[town_name] = junction_dict

        if road_graph is None:
            road_graph = out_graph

        all_available_signal_names |= available_signal_names_in_map
        all_available_object_names |= available_object_names_in_map
    if verbose:
        print(all_available_signal_names)
        print(all_available_object_names)
    return road_graph, large_junction_dict


if __name__ == "__main__":
    args = parse_args()
    opendrive_files = glob.glob(os.path.join(args.input, "*.xodr"))
    create_graph_from_files(opendrive_files)
