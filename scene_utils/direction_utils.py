import random

import carla
import numpy as np

from manager.world_manager import WorldManager
from misc.constant import DISTANCE_FOR_ROUTE

from .vector_utils import is_counter_clockwise, make_vector


def check_direction(point_vector, previos_vec, start_point):
    start_point_next = start_point.next(DISTANCE_FOR_ROUTE)[0]
    vector = make_vector(start_point, start_point_next)
    dot_product = np.dot(
        vector / np.linalg.norm(vector),
        previos_vec / np.linalg.norm(previos_vec),
    )

    if is_counter_clockwise(previos_vec, point_vector) and abs(dot_product) < 0.1:
        return "left"
    elif is_counter_clockwise(point_vector, previos_vec) and abs(dot_product) < 0.1:
        return "right"
    else:
        return "straight"


def sample_correct_point(relative_to_base, previous_vector, cur_waypoint):
    next_waypoint = cur_waypoint.next(DISTANCE_FOR_ROUTE)
    if next_waypoint is None:
        previous_waypoint = cur_waypoint.previous(DISTANCE_FOR_ROUTE)[0]
        diff_vec = make_vector(previous_waypoint, cur_waypoint)
    else:
        next_waypoint = next_waypoint[0]
        diff_vec = make_vector(cur_waypoint, next_waypoint)

    if relative_to_base == "straight":
        return np.dot(diff_vec, previous_vector) > 0
    elif relative_to_base == "left":
        return is_counter_clockwise(previous_vector, diff_vec)
    elif relative_to_base == "right":
        return is_counter_clockwise(diff_vec, previous_vector)


def check_direction_relative_to_ego_and_sample_all(
    waypoint_manager: WorldManager, previous_vec, road_id, direction
):
    right_driving_points, left_driving_points = waypoint_manager.get_left_right_driving_points(
        road_id
    )

    if len(right_driving_points) == 0 and len(left_driving_points) == 0:
        return []
    random_spawn_point = random.choice(
        right_driving_points if len(right_driving_points) > 0 else left_driving_points
    )
    next_point = random_spawn_point.next(DISTANCE_FOR_ROUTE)[0]
    point_vector = make_vector(random_spawn_point, next_point)

    if direction == "left":
        is_correct = is_counter_clockwise(point_vector, previous_vec)
    elif direction == "right":
        is_correct = is_counter_clockwise(previous_vec, point_vector)
    elif direction == "straight":
        is_correct = np.dot(point_vector, previous_vec) < 0

    return (
        right_driving_points
        if is_correct and len(right_driving_points) > 0
        else left_driving_points
    )


def get_correct_lane_driving(driving_points, choose_from_direction, action):
    if action == "straight":
        return random.choice(driving_points)
    lane_id = set()
    for driving_point in driving_points:
        lane_id.add(driving_point.lane_id)
    if choose_from_direction == "right":
        left_most, right_most = max(lane_id), min(lane_id)
    elif choose_from_direction == "left":
        left_most, right_most = min(lane_id), max(lane_id)

    if action == "left":
        return random.choice(
            [
                driving_point
                for driving_point in driving_points
                if driving_point.lane_id == left_most
            ]
        )
    elif action == "right":
        return random.choice(
            [
                driving_point
                for driving_point in driving_points
                if driving_point.lane_id == right_most
            ]
        )


def check_direction_and_sample_correct_point(
    waypoint_manager: WorldManager,
    base_waypoint,
    previous_vec,
    road_id,
    direction=None,
):
    right_driving_points, left_driving_points = waypoint_manager.get_left_right_driving_points(
        road_id
    )

    if len(right_driving_points) == 0 and len(left_driving_points) == 0:
        return {}
    choose_right = len(right_driving_points) > 0
    random_spawn_road = right_driving_points if choose_right else left_driving_points

    lane_id_set = set()
    for driving_point in random_spawn_road:
        lane_id_set.add(driving_point.lane_id)
    lane_id = sorted(list(lane_id_set))
    lane_id = lane_id[0] if len(lane_id) == 1 else lane_id[1]  # Choose middle

    random_spawn_point = random.choice(
        [driving_point for driving_point in random_spawn_road if driving_point.lane_id == lane_id]
    )
    end_point = get_points_to_front(random_spawn_point)[-1]
    start_point = get_points_to_end(random_spawn_point)[0]
    point_vector = make_vector(base_waypoint, end_point)
    if direction is None:
        direction = check_direction(point_vector, previous_vec, start_point)

    return_dict = {}
    is_correct = sample_correct_point(direction, previous_vec, end_point)
    if is_correct:
        return_dict[f"can_{direction}"] = get_correct_lane_driving(
            right_driving_points if choose_right else left_driving_points,
            "right" if choose_right else "left",
            direction,
        )
        if (choose_right and len(left_driving_points) > 0) or (
            not choose_right and len(right_driving_points) > 0
        ):
            return_dict[f"have_{direction}"] = get_correct_lane_driving(
                left_driving_points if choose_right else right_driving_points,
                "left" if choose_right else "right",
                direction,
            )
    else:
        return_dict[f"have_{direction}"] = get_correct_lane_driving(
            right_driving_points if choose_right else left_driving_points,
            "right" if choose_right else "left",
            direction,
        )
        choose_left = choose_right
        if (choose_left and len(left_driving_points) > 0) or (
            not choose_left and len(right_driving_points) > 0
        ):
            return_dict[f"can_{direction}"] = get_correct_lane_driving(
                left_driving_points if choose_right else right_driving_points,
                "left" if choose_right else "right",
                direction,
            )

    return return_dict

    # if is_correct:
    #     return direction, get_correct_lane_driving(
    #         right_driving_points if choose_right else left_driving_points,
    #         "right" if choose_right else "left",
    #         direction,
    #     )
    # else:
    #     choose_left = choose_right
    #     if (choose_left and len(left_driving_points) == 0) or (
    #         not choose_left and len(right_driving_points) == 0
    #     ):
    #         return direction, None
    #     return direction, get_correct_lane_driving(
    #         left_driving_points if choose_left else right_driving_points,
    #         "left" if choose_left else "right",
    #         direction,
    #     )


def get_points_to_front(waypoint: carla.Waypoint, distance: float = DISTANCE_FOR_ROUTE):
    return waypoint.next_until_lane_end(distance)


def get_points_to_end(waypoint: carla.Waypoint, distance: float = DISTANCE_FOR_ROUTE):
    return waypoint.previous_until_lane_start(distance)


def get_different_lane(waypoint):
    lane_id = waypoint.lane_id
    scale = abs(lane_id * 2)
    left_lane_waypoint = waypoint.get_left_lane()
    vector = None
    if left_lane_waypoint is None:
        right_lane_waypoint = waypoint.get_right_lane()
        if right_lane_waypoint is not None:
            vector = np.array(make_vector(right_lane_waypoint, waypoint))
    else:
        vector = np.array(make_vector(waypoint, left_lane_waypoint))

    if vector is None:
        prev_waypoint = waypoint.previous(DISTANCE_FOR_ROUTE)[0]
        if prev_waypoint is None:
            next_waypoint = waypoint.next(DISTANCE_FOR_ROUTE)[0]
            vector = make_vector(waypoint, next_waypoint)
        else:
            vector = make_vector(prev_waypoint, waypoint)
        vector = np.array([-vector[1], vector[0]]) * 5

    approx_location = waypoint.transform.location + carla.Location(
        x=vector[0] * scale, y=vector[1] * scale
    )
    return approx_location
