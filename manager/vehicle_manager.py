import random
from collections import defaultdict
from typing import List, Optional

import carla
import numpy as np

from agents.navigation.behavior_agent import BehaviorAgent
from agents.navigation.local_planner import RoadOption
from graph.graph_manager import GraphManager
from misc.constant import CAR_TYPE, DISTANCE_FOR_ROUTE, NULL_SPACE, NUM_POINT_PER_CAR
from scene_utils.direction_utils import (
    check_direction_and_sample_correct_point,
    check_direction_relative_to_ego_and_sample_all,
    get_different_lane,
    get_points_to_front,
)
from scene_utils.vector_utils import make_vector

from .agent_manager import AgentModelManager
from .world_manager import WorldManager

CLIP_NUM_POINTS = 12
AGENT_TYPE_TO_SIZE = {
    "ambulance": 3,
    "police": 3,
    "firetruck": 5,
    "bus": 5,
    "truck": 4,
    "motorcycle": 3,
    "car": 3,
    "pedestrian": 2,
    "cyclist": 2,
}

POS_TO_INTERFERE_DISTANCE = {
    "front": 13.0,
    "back": 13.0,
    "left": 13.0,
    "right": 13.0,
    "front_left": 13.0,
    "front_right": 13.0,
    "back_left": 13.0,
    "back_right": 13.0,
    "road_of_left_turn": 13.0,
    "road_of_right_turn": 13.0,
    "road_of_straight": 13.0,
}


class VehicleManager:
    def __init__(
        self,
        graph_manager: GraphManager,
        agent_model_manager: Optional[AgentModelManager] = None,
        world_manager: Optional[WorldManager] = None,
    ):
        self.graph_manager = graph_manager
        self.agent_model_manager = agent_model_manager
        self.world_manager = world_manager
        self.vehicles = []
        self.vehicle_agent: List[BehaviorAgent] = []

        self.points_to_front = []
        self.points_to_back = []

        self.front_required = 0
        self.back_required = 0
        self.front_pos_id_to_waypoint = {}
        self.back_pos_id_to_waypoint = {}

    def set_new_manager(self, agent_model_manager: AgentModelManager, world_manager: WorldManager):
        self.agent_model_manager = agent_model_manager
        self.world_manager = world_manager

    def compute_approximate_num_points(self, agent_type_list, number_of_lane):
        required_num_of_points = 0
        for agent in agent_type_list:
            required_num_of_points += AGENT_TYPE_TO_SIZE.get(agent, 3)
        return required_num_of_points // number_of_lane

    def get_left_straight_right(self, waypoint, get_road_id_only=False, debug=False):
        waypoint = get_points_to_front(waypoint)[-1]
        move_one_more_forward = waypoint.next(DISTANCE_FOR_ROUTE)
        if move_one_more_forward is None or len(move_one_more_forward) == 0:
            return None
        move_one_more_forward = self.world_manager.map.get_waypoint(
            move_one_more_forward[0].transform.location
        )
        previous_vector = make_vector(waypoint, move_one_more_forward)
        if not move_one_more_forward.is_junction:
            return check_direction_and_sample_correct_point(
                self.world_manager,
                waypoint,
                previous_vector,
                move_one_more_forward.road_id,
                direction="straight",
            )

        junction_id = move_one_more_forward.junction_id
        original_road_id = waypoint.road_id
        intersection = self.graph_manager.get_intersection(
            original_road_id, from_road_id=True, junction_id_list=[str(junction_id)]
        )
        if len(intersection) == 0:
            return check_direction_and_sample_correct_point(
                self.world_manager,
                waypoint,
                previous_vector,
                move_one_more_forward.road_id,
                direction="straight",
            )
        intersection = intersection[0]
        intersection.remove(original_road_id)  # Remove self road id
        direction_to_point = {}
        direction_to_road_id = {}
        for road_id in intersection:
            direction_dict = check_direction_and_sample_correct_point(
                self.world_manager,
                waypoint,
                previous_vector,
                road_id,
            )
            if len(direction_dict) == 0:
                continue
            direction_to_point.update(direction_dict)
            direction_to_road_id.update({direction: road_id for direction in direction_dict})

        return direction_to_road_id if get_road_id_only else direction_to_point

    def set_vehicle_agent_action(self, agent: BehaviorAgent, action, info, num_interpolate=10):
        go_left_straight_right = self.get_left_straight_right(
            self.world_manager.get_waypoint_from_location(
                location=agent._vehicle.get_location(),
                lane_type=carla.LaneType.Driving,
            ),
        )

        if action == "change_lane_to_left":
            agent.lane_change("left")
        elif action == "change_lane_to_right":
            agent.lane_change("right")
        elif action == "go_straight" and "can_straight" in go_left_straight_right:
            agent.set_destination(go_left_straight_right["can_straight"].transform.location)
        elif action == "turn_left":
            if "can_left" in go_left_straight_right:
                agent.set_destination(go_left_straight_right["can_left"].transform.location)
            else:
                agent.lane_change("left")
        elif action == "turn_right":
            if "can_right" in go_left_straight_right:
                agent.set_destination(go_left_straight_right["can_right"].transform.location)
            else:
                agent.lane_change("right")
        elif action == "block_the_ego":
            # Set the same location as the ego vehicle
            destination = self.vehicle_agent[0].destination_waypoint.next(DISTANCE_FOR_ROUTE * 5)[0]
            agent.set_destination(
                destination.transform.location,
                interfere_target=self.vehicle_agent[0],
            )
            agent.ignore_traffic_lights()
        elif action == "cross_the_road":
            current_spawn_point = self.world_manager.get_waypoint_from_location(
                location=agent._vehicle.get_location(),
                lane_type=getattr(carla.LaneType, info["road_type"].capitalize()),
            )
            destination = get_different_lane(current_spawn_point)
            destination = self.world_manager.get_waypoint_from_location(
                location=destination,
                lane_type=carla.LaneType.Driving
                | carla.LaneType.Shoulder
                | carla.LaneType.Sidewalk,
            )
            single_vector = (
                np.array(make_vector(current_spawn_point, destination)) / num_interpolate
            )
            interpolate = [
                [
                    current_spawn_point.transform.location.x + single_vector[0] * point_idx,
                    current_spawn_point.transform.location.y + single_vector[1] * point_idx,
                ]
                for point_idx in range(1, num_interpolate)
            ]
            plan = [
                (
                    self.world_manager.get_waypoint_from_location(
                        carla.Location(x=point[0], y=point[1]),
                        lane_type=carla.LaneType.Sidewalk
                        | carla.LaneType.Shoulder
                        | carla.LaneType.Driving,
                    ),
                    RoadOption.VOID,
                )
                for point in interpolate
            ]
            agent._local_planner.set_global_plan(plan)
        elif action == "stop":  # stop or others
            agent.no_act = True

    def create_vehicle_agent(self, vehicle, agent_info):
        behavior = agent_info.get("behavior", "normal")
        agent = BehaviorAgent(
            vehicle,
            behavior=behavior,
            interference_distance=POS_TO_INTERFERE_DISTANCE.get(
                agent_info["relative_to_ego"], 13.0
            ),
        )
        if behavior == "aggressive" and not agent_info["is_ego"]:
            agent.ignore_vehicles(active=True)
            if agent_info["relative_to_ego"] in [
                "road_of_left_turn",
                "road_of_right_turn",
                "road_of_straight",
            ]:
                agent.ignore_traffic_lights(active=True)

        if agent_info["type"] in ["police", "ambulance", "firetruck"]:
            agent.ignore_traffic_lights(active=True)
        self.set_vehicle_agent_action(agent, agent_info["action"], agent_info)
        return agent

    def add_pre_spawn_ego(self, ego_vehicle, ego_waypoint, agent_info, destination=None):
        self.vehicles.append(ego_vehicle)
        agent = BehaviorAgent(ego_vehicle)
        if destination is None:
            destination = ego_vehicle.get_location()
        agent.set_destination(destination)
        agent.no_act = True
        self.vehicle_agent.append(agent)

        while ego_waypoint.is_junction:
            ego_waypoint = ego_waypoint.next(DISTANCE_FOR_ROUTE)[0]
        road_id, lane_id = ego_waypoint.road_id, ego_waypoint.lane_id

        driving_points = self.world_manager.get_driving_points_with_road_and_lane_id(
            road_id, lane_id
        )
        driving_points.sort(
            key=lambda x: x.s,
            reverse=lane_id < 0,
        )
        min_idx = min(
            range(len(driving_points)),
            key=lambda x: driving_points[x].transform.location.distance(ego_vehicle.get_location()),
        )

        self.points_to_front = driving_points[:min_idx]
        self.points_to_back = driving_points[min_idx:]
        self.front_required = self.count_points_required("front", agent_info)
        self.back_required = self.count_points_required("back", agent_info)

    def spawn_car(self, spawn_point, model: str = "vehicle.lincoln.mkz_2017", agent_info=None):
        if model == "random":
            ego_vehicle_bp = self.agent_model_manager.get_blueprint_from_type(agent_info["type"])
        else:
            ego_vehicle_bp = self.agent_model_manager.get_blueprint_from_name(model)
        new_spawn_point = carla.Transform(
            spawn_point.transform.location + carla.Location(z=0.1), spawn_point.transform.rotation
        )
        vehicle = self.world_manager.spawn_actor(ego_vehicle_bp, new_spawn_point)
        if vehicle is None:
            # Move the spawn point a little bit left or right
            if agent_info["relative_to_ego"].endswith("left"):
                spawn_point = spawn_point.get_left_lane()
            elif agent_info["relative_to_ego"].endswith("right"):
                spawn_point = spawn_point.get_right_lane()
            if spawn_point is not None:
                new_spawn_point = carla.Transform(
                    spawn_point.transform.location + carla.Location(z=0.1),
                    spawn_point.transform.rotation,
                )
                vehicle = self.world_manager.spawn_actor(ego_vehicle_bp, new_spawn_point)

        if vehicle is not None:
            self.vehicles.append(vehicle)
            agent = self.create_vehicle_agent(vehicle, agent_info)
            self.vehicle_agent.append(agent)
        return spawn_point

    def spawn_car_from_selected_waypoint(self, agent_info, direction):
        pos_id_to_waypoint = getattr(self, f"{direction}_pos_id_to_waypoint")

        for agent in agent_info:
            if agent["pos_id"] not in pos_id_to_waypoint:
                continue
            spawn_point = pos_id_to_waypoint[agent["pos_id"]]
            if agent["relative_to_ego"].endswith("right"):
                spawn_point = spawn_point.get_right_lane()
                if spawn_point is None:
                    continue
            if agent["relative_to_ego"].endswith("left"):
                spawn_point = spawn_point.get_left_lane()
                if spawn_point is None:
                    continue

            if agent["road_type"] == "shoulder":
                spawn_point = self.world_manager.get_waypoint_from_location(
                    spawn_point.transform.location, lane_type=carla.LaneType.Shoulder
                )
            self.spawn_car(spawn_point, "random", agent)

    def spawn_car_from_list_of_waypoint(self, waypoint_list, agent_info, debug=False):
        if len(waypoint_list) == 0:
            return
        maximum_allow_cars = len(waypoint_list) // NUM_POINT_PER_CAR
        agent_info = agent_info[:maximum_allow_cars]
        if len(agent_info) == 1:
            sum_of_s = sum([waypoint.s for waypoint in waypoint_list])
            average_s = sum_of_s / len(waypoint_list)
            is_right = waypoint_list[0].lane_id < 0
            waypoint_list = [
                waypoint
                for waypoint in waypoint_list
                if (is_right and (waypoint.s > average_s))
                or (not is_right and (waypoint.s < average_s))
            ]
        if debug:
            for spawn_point in waypoint_list:
                self.world_manager.draw_point(spawn_point.transform.location)
        for agent_idx, agent in enumerate(agent_info, 1):
            valid_num = len(waypoint_list) - NUM_POINT_PER_CAR * (len(agent_info) - agent_idx) - 1
            valid_points = waypoint_list[:valid_num]
            spawn_point = random.choice(valid_points)

            if agent["road_type"] == "shoulder":
                spawn_point = self.world_manager.get_waypoint_from_location(
                    spawn_point.transform.location, lane_type=carla.LaneType.Shoulder
                )
            self.spawn_car(spawn_point, "random", agent)
            waypoint_list = waypoint_list[valid_num:]

    def count_points_required(self, position, agent_info, get_plan=False):
        pos_id_to_agent = defaultdict(list)
        for target in agent_info:
            if not target["is_ego"] and position in target["relative_to_ego"]:
                pos_id_to_agent[target["pos_id"]].append(target)
        if len(pos_id_to_agent) == 0:
            return 0
        if get_plan:
            required_point = getattr(self, f"{position}_required")
            waypoints = getattr(self, f"points_to_{position}")
            if required_point < CLIP_NUM_POINTS and len(waypoints) > CLIP_NUM_POINTS:
                if position == "front":
                    waypoints = waypoints[-CLIP_NUM_POINTS:]
                else:
                    waypoints = waypoints[CLIP_NUM_POINTS:]
            if len(waypoints) > required_point:
                choose_start_idx = random.choice(range(len(waypoints) - required_point))
                waypoints = waypoints[choose_start_idx:]
            pos_id_to_waypoint = {}

        existing_pos_id = sorted(list(pos_id_to_agent.keys()))
        previous_pos_id = min(existing_pos_id) - 1
        num_points_required = 0

        for pos_id in existing_pos_id:
            while pos_id != previous_pos_id + 1:  # Make a small gap
                num_points_required += NULL_SPACE
                previous_pos_id += 1
            agent_on_pos = pos_id_to_agent[pos_id]
            maximum_points_required = max(
                [AGENT_TYPE_TO_SIZE.get(x["type"], NUM_POINT_PER_CAR) for x in agent_on_pos]
            )
            if get_plan:
                if num_points_required + 1 < len(waypoints):
                    pos_id_to_waypoint[pos_id] = waypoints[num_points_required + 1]
                else:
                    break
            num_points_required += maximum_points_required
            previous_pos_id = pos_id

        if get_plan:
            setattr(self, f"{position}_pos_id_to_waypoint", pos_id_to_waypoint)
        return num_points_required

    def spawn_other_cars(self, agent_info, ego_agent):
        ego_waypoint = self.world_manager.get_waypoint_from_location(
            ego_agent.get_location(), carla.LaneType.Driving
        )
        if ego_waypoint.is_junction:
            ego_waypoint = ego_waypoint.next(DISTANCE_FOR_ROUTE)[0]
        self.count_points_required("front", agent_info, True)
        self.count_points_required("back", agent_info, True)

        target_info = defaultdict(list)
        for agent in agent_info:
            if agent["type"] in CAR_TYPE and not agent["is_ego"]:
                target_info[agent["relative_to_ego"]].append(agent)
        direction_of_each_road = self.get_left_straight_right(ego_waypoint, get_road_id_only=True)
        for relative_position, agents in target_info.items():
            if relative_position in ["front", "front_left", "front_right"]:
                self.spawn_car_from_selected_waypoint(agents, "front")
            elif relative_position in ["back", "back_left", "back_right"]:
                self.spawn_car_from_selected_waypoint(agents, "back")
            elif relative_position == "left":
                spawn_point = ego_waypoint.get_left_lane()
                if spawn_point is None:
                    continue
                self.spawn_car(spawn_point, "random", agents[0])
            elif relative_position == "right":
                spawn_point = ego_waypoint.get_right_lane()
                if spawn_point is None:
                    continue
                self.spawn_car(spawn_point, "random", agents[0])
            elif relative_position == "road_of_left_turn" and "have_left" in direction_of_each_road:
                road_id_to_spawn = direction_of_each_road["have_left"]
                waypoint = get_points_to_front(
                    ego_waypoint,
                )[-1]
                move_one_more_forward = waypoint.next(DISTANCE_FOR_ROUTE * 5)[0]
                previous_vector = make_vector(waypoint, move_one_more_forward)
                self.spawn_car_from_list_of_waypoint(
                    check_direction_relative_to_ego_and_sample_all(
                        self.world_manager, previous_vector, road_id_to_spawn, "left"
                    ),
                    sorted(agents, key=lambda x: x["pos_id"]),
                )
            elif (
                relative_position == "road_of_right_turn" and "have_right" in direction_of_each_road
            ):
                road_id_to_spawn = direction_of_each_road["have_right"]
                waypoint = get_points_to_front(
                    ego_waypoint,
                )[-1]
                move_one_more_forward = waypoint.next(DISTANCE_FOR_ROUTE * 5)[0]
                previous_vector = make_vector(waypoint, move_one_more_forward)
                self.spawn_car_from_list_of_waypoint(
                    check_direction_relative_to_ego_and_sample_all(
                        self.world_manager, previous_vector, road_id_to_spawn, "right"
                    ),
                    sorted(agents, key=lambda x: x["pos_id"]),
                )
            elif (
                relative_position == "road_of_straight"
                and "have_straight" in direction_of_each_road
            ):
                road_id_to_spawn = direction_of_each_road["have_straight"]
                waypoint = get_points_to_front(
                    ego_waypoint,
                )[-1]
                move_one_more_forward = waypoint.next(DISTANCE_FOR_ROUTE * 5)[0]
                previous_vector = make_vector(waypoint, move_one_more_forward)
                self.spawn_car_from_list_of_waypoint(
                    check_direction_relative_to_ego_and_sample_all(
                        self.world_manager, previous_vector, road_id_to_spawn, "straight"
                    ),
                    sorted(agents, key=lambda x: x["pos_id"]),
                )

    def spawn_ego_car(self, road_id, agent_info, direction, at_junction=False):
        # left, right, front, back
        relative_agents_direction_count = [0, 0, 0, 0]
        relative_agents_direction_count[2] = self.count_points_required("front", agent_info)
        relative_agents_direction_count[3] = self.count_points_required("back", agent_info)

        self.front_required = relative_agents_direction_count[2]
        self.back_required = relative_agents_direction_count[3]
        ego_agent = [agent for agent in agent_info if agent.get("is_ego", False)][0]
        for agent in agent_info:
            if (
                not agent["type"] in CAR_TYPE
                or agent.get("is_ego", False)
                or agent["road_type"] != "driving"
            ):
                continue
            if agent["relative_to_ego"].endswith("left"):
                relative_agents_direction_count[0] = 1
            if agent["relative_to_ego"].endswith("right"):
                relative_agents_direction_count[1] = 1

        right_driving_points, left_driving_points = (
            self.world_manager.get_left_right_driving_points(road_id)
        )
        choose_right = direction == "right"
        waypoints_to_spawn = right_driving_points if choose_right else left_driving_points

        if len(waypoints_to_spawn) == 0:
            print("The road has no driving points")
            return None
        valid_lane_id = set()
        for waypoint in waypoints_to_spawn:
            valid_lane_id.add(waypoint.lane_id)

        leftmost, rightmost = max(valid_lane_id), min(valid_lane_id)
        if not choose_right:
            leftmost, rightmost = rightmost, leftmost

        if relative_agents_direction_count[0] > 0:  # left
            valid_lane_id.remove(leftmost)
        if relative_agents_direction_count[1] > 0:  # right
            valid_lane_id.remove(rightmost)

        if len(valid_lane_id) == 0:
            return None

        if ego_agent["action"] == "turn_right":
            target_lane_id = min(valid_lane_id)
            if not choose_right:
                target_lane_id = max(valid_lane_id)
        elif ego_agent["action"] == "turn_left":
            target_lane_id = max(valid_lane_id)
            if not choose_right:
                target_lane_id = min(valid_lane_id)
        else:
            target_lane_id = random.choice(list(valid_lane_id))

        remain_valid_driving_points = sorted(
            [waypoint for waypoint in waypoints_to_spawn if waypoint.lane_id == target_lane_id],
            key=lambda x: x.s,
            reverse=choose_right,
        )
        max_distance = max([waypoint.s for waypoint in remain_valid_driving_points])
        valid_start = relative_agents_direction_count[2]
        valid_end = len(remain_valid_driving_points) - relative_agents_direction_count[3]
        self.points_to_front = remain_valid_driving_points[:valid_start]
        self.points_to_back = remain_valid_driving_points[valid_end:]
        remain_valid_driving_points = remain_valid_driving_points[valid_start:valid_end]

        if at_junction:
            if choose_right:
                remain_valid_driving_points = [
                    waypoint
                    for waypoint in remain_valid_driving_points
                    if waypoint.s > max_distance * 2 / NUM_POINT_PER_CAR
                ]
            else:
                remain_valid_driving_points = [
                    waypoint
                    for waypoint in remain_valid_driving_points
                    if waypoint.s < max_distance / NUM_POINT_PER_CAR
                ]
        if len(remain_valid_driving_points) == 0:
            print("No remain valid driving points")
            return None
        spawn_point_idx = random.choice(range(len(remain_valid_driving_points)))
        self.points_to_front += remain_valid_driving_points[:spawn_point_idx]
        if len(remain_valid_driving_points) - spawn_point_idx - 1 >= 3:
            self.points_to_back = (
                remain_valid_driving_points[spawn_point_idx + 3 :] + self.points_to_back
            )
        ego_waypoint = self.spawn_car(
            remain_valid_driving_points[spawn_point_idx],
            "vehicle.lincoln.mkz_2017" if ego_agent["type"] == "car" else "random",
            ego_agent,
        )
        return ego_waypoint

    def run_step(self):
        all_done = True
        for idx, (agent, vehicle) in enumerate(zip(self.vehicle_agent, self.vehicles)):
            if idx == 0 and vehicle.is_alive:
                spectator = self.world_manager.world.get_spectator()
                spectator.set_transform(
                    carla.Transform(
                        vehicle.get_location() + carla.Location(z=50), carla.Rotation(pitch=-90)
                    ),
                )
            if agent is None:
                continue
            elif not agent.done():
                vehicle.apply_control(agent.run_step())
                all_done = False
            else:
                if vehicle.is_alive:
                    vehicle.apply_control(carla.VehicleControl(brake=1.0))
                    if not agent.no_act:
                        vehicle.destroy()
        return all_done

    def clean(self):
        for vechile in self.vehicles:
            if vechile.is_alive:
                vechile.destroy()
        if len(self.vehicles) > 0:
            self.world_manager.world.tick()
