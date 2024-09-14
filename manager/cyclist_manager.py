import random
from typing import Optional

import carla

from agents.navigation.cyclist_agent import CyclistAgent
from graph.graph_manager import GraphManager
from misc.constant import DISTANCE_FOR_ROUTE
from scene_utils.direction_utils import (
    check_direction_and_sample_correct_point,
    get_different_lane,
    get_points_to_end,
    get_points_to_front,
)
from scene_utils.vector_utils import make_vector

from .agent_manager import AgentModelManager
from .world_manager import WorldManager

LANE_DIFF_FACTOR = 1.5


class CyclistManager:
    def __init__(
        self,
        graph_manager: GraphManager,
        agent_model_manager: Optional[AgentModelManager] = None,
        world_manager: Optional[WorldManager] = None,
    ):
        self.agent_model_manager = agent_model_manager
        self.world_manager = world_manager
        self.graph_manager = graph_manager
        self.cyclists = []
        self.cyclist_agent = []
        self.front_pos_id_to_waypoint = {}
        self.back_pos_id_to_waypoint = {}

    def set_pos_id_to_waypoints(self, vehicle_manager):
        self.front_pos_id_to_waypoint = vehicle_manager.front_pos_id_to_waypoint
        self.back_pos_id_to_waypoint = vehicle_manager.back_pos_id_to_waypoint

    def set_new_manager(self, agent_model_manager: AgentModelManager, world_manager: WorldManager):
        self.agent_model_manager = agent_model_manager
        self.world_manager = world_manager

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

    def set_cyclist_agent_action(
        self, agent: CyclistAgent, action, ego_agent, spawn_point, num_interpolate=10
    ):
        go_left_straight_right = self.get_left_straight_right(
            self.world_manager.get_waypoint_from_location(
                location=agent.agent._vehicle.get_location(),
                lane_type=carla.LaneType.Driving,
            ),
        )

        if action == "change_lane_to_left":
            agent.agent.lane_change("left")
            agent.use_original = True
        elif action == "change_lane_to_right":
            agent.agent.lane_change("right")
            agent.use_original = True
        elif action == "go_straight" and "can_straight" in go_left_straight_right:
            agent.agent.set_destination(go_left_straight_right["can_straight"].transform.location)
            agent.use_original = True
        elif action == "turn_left":
            if "can_left" in go_left_straight_right:
                agent.agent.set_destination(go_left_straight_right["can_left"].transform.location)
            else:
                agent.agent.lane_change("left")
            agent.use_original = True
        elif action == "turn_right":
            if "can_right" in go_left_straight_right:
                agent.agent.set_destination(go_left_straight_right["can_right"].transform.location)
            else:
                agent.agent.lane_change("right")
            agent.use_original = True
        elif action == "block_the_ego":
            # Set the same location as the ego vehicle
            destination = self.vehicle_agent[0].destination_waypoint.next(DISTANCE_FOR_ROUTE * 5)[0]
            agent.agent.set_destination(
                destination.transform.location,
                interfere_target=self.vehicle_agent[0],
            )
            agent.agent.ignore_traffic_lights()
            agent.use_original = True
        elif action == "cross_the_road":
            find_point = get_different_lane(spawn_point)
            destination = self.world_manager.get_waypoint_from_location_with_ensure(
                find_point,
                [carla.LaneType.Sidewalk, carla.LaneType.Shoulder, carla.LaneType.Driving],
            )
            agent.set_destination(self.world_manager, destination, spawn_point, num_interpolate)
        elif action == "block_the_ego":
            ego_lane_id = ego_agent.destination_waypoint.lane_id
            different_direction = spawn_point.lane_id * ego_lane_id < 0
            if different_direction:
                find_point = get_different_lane(spawn_point)
                destination = self.world_manager.get_waypoint_from_location_with_ensure(
                    find_point,
                    [carla.LaneType.Sidewalk, carla.LaneType.Shoulder, carla.LaneType.Driving],
                )
            else:
                destination = spawn_point
            while destination.lane_id != ego_lane_id:
                destination = destination.get_left_lane()
            agent.set_ego_agent(
                ego_agent._vehicle, factor=LANE_DIFF_FACTOR if different_direction else 1.0
            )
            agent.set_destination(self.world_manager, destination, spawn_point, num_interpolate)
        elif action == "on_the_sidewalk":
            destination = random.choice(
                get_points_to_front(spawn_point)[1:] + get_points_to_end(spawn_point)[1:]
            )

            agent.set_destination(self.world_manager, destination, spawn_point, num_interpolate)

    def create_cyclist_agent(self, vehicle, agent_info, ego_agent, ego_car_point, spawn_point):
        behavior = agent_info.get("behavior", "normal")
        agent = CyclistAgent(
            vehicle, behavior=behavior, plan=agent_info["action"] == "block_the_ego"
        )
        self.set_cyclist_agent_action(
            agent, agent_info.get("action", "go_straight"), ego_agent, spawn_point
        )
        return agent

    def spawn_cyclist(self, agent, ego_agent, ego_car_point, spawn_point):
        cyclist_bp = self.agent_model_manager.get_blueprint_from_type("bicycle")
        new_spawn_point = carla.Transform(
            spawn_point.transform.location + carla.Location(z=2), spawn_point.transform.rotation
        )
        cyclist = self.world_manager.spawn_actor(cyclist_bp, new_spawn_point)

        if cyclist is not None:
            self.cyclists.append(cyclist)
            agent = self.create_cyclist_agent(cyclist, agent, ego_agent, ego_car_point, spawn_point)
            self.cyclist_agent.append(agent)

    def check_cyclist_spawn_type(self, waypoint, target_road_type=None):
        for road_type in ["Sidewalk", "Shoulder", "Driving"]:
            if target_road_type is not None and road_type.lower() != target_road_type:
                continue
            test_waypoint = self.world_manager.get_waypoint_from_location(
                waypoint.transform.location, lane_type=getattr(carla.LaneType, road_type)
            )
            if test_waypoint is not None and waypoint.road_id == test_waypoint.road_id:
                return road_type
        return "Driving"

    def spawn_cyclists(self, agent_info, ego_agent):
        ego_waypoint = self.world_manager.get_waypoint_from_location(
            ego_agent._vehicle.get_location(), carla.LaneType.Driving
        )
        for agent in agent_info:
            cyclist_spawn_type = self.check_cyclist_spawn_type(ego_waypoint, agent["road_type"])
            # Agent can be from left to right or right to left
            if agent["relative_to_ego"] == "front":
                agent["relative_to_ego"] = random.choice(["front_right", "front_left"])
            elif agent["relative_to_ego"] == "back":
                agent["relative_to_ego"] = random.choice(["back_right", "back_left"])
            elif agent["relative_to_ego"] in ["left", "road_to_left_turn"]:
                agent["relative_to_ego"] = "front_left"
            elif agent["relative_to_ego"] in ["right", "road_to_right_turn"]:
                agent["relative_to_ego"] = "front_right"

            if (
                agent["relative_to_ego"].startswith("front")
                and agent["pos_id"] in self.front_pos_id_to_waypoint
            ):
                spawn_point = self.front_pos_id_to_waypoint[agent["pos_id"]]
                if agent["relative_to_ego"].endswith("left"):
                    spawn_point = get_different_lane(spawn_point)
                else:
                    spawn_point = spawn_point.transform.location
            elif (
                agent["relative_to_ego"].startswith("back")
                and agent["pos_id"] in self.back_pos_id_to_waypoint
            ):
                spawn_point = self.back_pos_id_to_waypoint[agent["pos_id"]]
                if agent["relative_to_ego"].endswith("left"):
                    spawn_point = get_different_lane(spawn_point)
                else:
                    spawn_point = spawn_point.transform.location
            elif agent["relative_to_ego"] == "at_the_destination":
                spawn_point = ego_agent.destination_waypoint
                spawn_point = spawn_point.previous(1)
                if spawn_point is None:
                    spawn_point = spawn_point.next(1)
                spawn_point = spawn_point[0]
                spawn_point = spawn_point.transform.location
            else:
                continue
            spawn_point = self.world_manager.get_waypoint_from_location(
                spawn_point,
                lane_type=getattr(carla.LaneType, cyclist_spawn_type),
            )
            self.spawn_cyclist(agent, ego_agent, ego_waypoint, spawn_point)

    def run_step(self):
        cyclist_agent = []
        for agent in self.cyclist_agent:
            if not agent.done():
                agent.run_step()
                cyclist_agent.append(agent)
        self.cyclist_agent = cyclist_agent

    def clean(self):
        for cyclist in self.cyclists:
            if cyclist.is_alive:
                cyclist.destroy()

        if len(self.cyclists) > 0:
            self.world_manager.world.tick()
