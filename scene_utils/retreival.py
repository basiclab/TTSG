from typing import Any, Dict

import networkx as nx

from misc.constant import OBJECT_SEARCH_DICT, SIGNAL_SEARCH_DICT


def check_one_inside_list(from_list, target_list):
    left_road, right_road = False, False
    for from_ in from_list:
        for target in target_list:
            if from_ == target["name"]:
                if target["t"] < 0:
                    right_road = True
                else:
                    left_road = True
    return left_road, right_road


def retrieve_roads(graph: nx.DiGraph, road_condition: Dict[str, Any]):
    """Retrieve the roads that match the road conditions
    Args:
        graph (nx.Graph): The graph database.
        road_condition (Dict[str, Any]): Road conditions for retreival.
    Returns:
        List[List]: The list of node that match the road conditions.
    """
    valid_node_id = []
    number_of_required_lane = road_condition["number_of_lanes"]
    required_objects = road_condition.get("required_objects", [])
    required_signals = road_condition.get("required_signals", [])
    without_objects = road_condition.get("without_objects", [])
    without_signals = road_condition.get("without_signals", [])

    for node_id, node_info in graph.nodes(data=True):
        if node_info["is_junction"]:
            continue
        objects_road_have = node_info["objects"]
        signals_road_have = node_info["signals"]

        if len(required_objects) > 0:
            left_matched_object, right_matched_object = zip(
                *[
                    check_one_inside_list(OBJECT_SEARCH_DICT.get(obj, [obj]), objects_road_have)
                    for obj in required_objects
                ]
            )
        else:
            left_matched_object, right_matched_object = [True], [True]

        if len(required_signals) > 0:
            left_matched_signal, right_matched_signal = zip(
                *[
                    check_one_inside_list(
                        SIGNAL_SEARCH_DICT.get(signal, [signal]), signals_road_have
                    )
                    for signal in required_signals
                ]
            )
        else:
            left_matched_signal, right_matched_signal = [True], [True]

        left_have_match_object = (len(required_objects) == 0) or all(left_matched_object)
        right_have_match_object = (len(required_objects) == 0) or all(right_matched_object)
        left_have_match_signal = (len(required_signals) == 0) or all(left_matched_signal)
        right_have_match_signal = (len(required_signals) == 0) or all(right_matched_signal)

        if len(without_objects) > 0:
            left_unmatched_object, right_unmatched_object = zip(
                *[
                    check_one_inside_list(OBJECT_SEARCH_DICT.get(obj, [obj]), objects_road_have)
                    for obj in without_objects
                ]
            )
        else:
            left_unmatched_object, right_unmatched_object = [False], [False]

        if len(without_signals) > 0:
            left_unmatched_signal, right_unmatched_signal = zip(
                *[
                    check_one_inside_list(
                        SIGNAL_SEARCH_DICT.get(signal, [signal]), signals_road_have
                    )
                    for signal in without_signals
                ]
            )
        else:
            left_unmatched_signal, right_unmatched_signal = [False], [False]
        left_have_no_unmatch_object = (len(without_objects) == 0) or (
            not any(left_unmatched_object)
        )
        right_have_no_unmatch_object = (len(without_objects) == 0) or (
            not any(right_unmatched_object)
        )
        left_have_no_unmatch_signal = (len(without_signals) == 0) or (
            not any(left_unmatched_signal)
        )
        right_have_no_unmatch_signal = (len(without_signals) == 0) or (
            not any(right_unmatched_signal)
        )

        if (
            left_have_match_object
            and left_have_match_signal
            and left_have_no_unmatch_object
            and left_have_no_unmatch_signal
            and node_info["number_of_left_lane"] >= number_of_required_lane
        ):
            valid_node_id.append(
                [
                    node_id,
                    "left",
                    {
                        "have_shoulder": node_info["left_extra"]["have_shoulder"],
                        "have_sidewalk": node_info["left_extra"]["have_sidewalk"],
                        "number_of_lane": node_info["number_of_left_lane"],
                        "can_turn_left": node_info["left_extra"]["can_turn_left"],
                        "can_turn_right": node_info["left_extra"]["can_turn_right"],
                        "can_go_straight": node_info["left_extra"]["can_go_straight"],
                        "have_left_from": node_info["left_extra"]["have_left_from"],
                        "have_right_from": node_info["left_extra"]["have_right_from"],
                        "have_straight_from": node_info["left_extra"]["have_straight_from"],
                        "have_opposite": node_info["left_extra"]["have_opposite"],
                        "num_of_waypoints": node_info["left_extra"]["num_of_waypoints"],
                    },
                ]
            )
        if (
            right_have_match_object
            and right_have_match_signal
            and right_have_no_unmatch_object
            and right_have_no_unmatch_signal
            and node_info["number_of_right_lane"] >= number_of_required_lane
        ):
            valid_node_id.append(
                [
                    node_id,
                    "right",
                    {
                        "have_shoulder": node_info["right_extra"]["have_shoulder"],
                        "have_sidewalk": node_info["right_extra"]["have_sidewalk"],
                        "number_of_lane": node_info["number_of_right_lane"],
                        "can_turn_left": node_info["right_extra"]["can_turn_left"],
                        "can_turn_right": node_info["right_extra"]["can_turn_right"],
                        "can_go_straight": node_info["right_extra"]["can_go_straight"],
                        "have_left_from": node_info["right_extra"]["have_left_from"],
                        "have_right_from": node_info["right_extra"]["have_right_from"],
                        "have_straight_from": node_info["right_extra"]["have_straight_from"],
                        "have_opposite": node_info["right_extra"]["have_opposite"],
                        "num_of_waypoints": node_info["right_extra"]["num_of_waypoints"],
                    },
                ]
            )
    return valid_node_id
