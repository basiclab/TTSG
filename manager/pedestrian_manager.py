import random
from typing import Optional

import carla

from agents.navigation.walker_agent import PedestrianAgent
from misc.constant import DISTANCE_FOR_ROUTE
from scene_utils.direction_utils import (
    get_different_lane,
    get_points_to_end,
    get_points_to_front,
)

from .agent_manager import AgentModelManager
from .world_manager import WorldManager

PEDESTRIAN_TYPE = {
    "cautious": 1.5,
    "normal": 2.0,
    "aggressive": 3.0,
}
LANE_DIFF_FACTOR = 1.0

MAX_DEPTH = 10


class PedestrianManager:
    def __init__(
        self,
        agent_model_manager: Optional[AgentModelManager] = None,
        world_manager: Optional[WorldManager] = None,
    ):
        self.agent_model_manager = agent_model_manager
        self.world_manager = world_manager
        self.pedestrian_list = []
        self.walker_controller_list = []
        self.ai_controller_list = []
        self.front_pos_id_to_waypoint = {}
        self.back_pos_id_to_waypoint = {}

    def set_pos_id_to_waypoints(self, vehicle_manager):
        self.front_pos_id_to_waypoint = vehicle_manager.front_pos_id_to_waypoint
        self.back_pos_id_to_waypoint = vehicle_manager.back_pos_id_to_waypoint

    def spawn_pedestrian(self, agent, spawn_point, ego_agent, ego_car_point):
        walker_bp = self.agent_model_manager.get_blueprint_from_type("pedestrian")
        if walker_bp.has_attribute("is_invincible"):
            walker_bp.set_attribute("is_invincible", "false")

        if (
            agent["action"] == "block_the_ego"
            and agent["relative_to_ego"] != "at_the_destination"
            and random.random() < 0.5
        ):  # Randomly applied from the end of the road
            spawn_point = get_points_to_front(spawn_point)
            if len(spawn_point) > 2:
                spawn_point = spawn_point[-2]
            else:
                spawn_point = spawn_point[-1]

        new_spawn_point = carla.Transform(
            spawn_point.transform.location + carla.Location(z=2), spawn_point.transform.rotation
        )
        walker = self.world_manager.spawn_actor(walker_bp, new_spawn_point)

        if walker is not None:
            self.pedestrian_list.append(walker)
            walker_controller = PedestrianAgent(
                walker, agent["behavior"], agent["action"] == "block_the_ego"
            )
            walker_controller.set_ego_agent(ego_agent._vehicle, factor=1.0)
            walker_controller.set_ego_vector(ego_car_point)
            if agent["action"] != "stop":
                if agent["action"] == "cross_the_road":
                    find_point = get_different_lane(spawn_point)
                    destination = self.world_manager.get_waypoint_from_location_with_ensure(
                        find_point,
                        [
                            carla.LaneType.Sidewalk,
                            carla.LaneType.Shoulder,
                            carla.LaneType.Driving,
                        ],
                    )
                    if agent["relative_to_ego"] == "near_the_crosswalk":
                        controller_bp = self.agent_model_manager.get_blueprint_from_name(
                            "controller.ai.walker"
                        )
                        controller = self.world_manager.spawn_actor(
                            controller_bp, carla.Transform(), walker
                        )
                        controller.start()
                        if destination.lane_type != carla.LaneType.Sidewalk:
                            controller.go_to_location(
                                self.world_manager.world.get_random_location_from_navigation()
                            )
                        else:
                            location = destination.transform.location
                            controller.go_to_location(
                                carla.Location(x=location.x, y=location.y, z=0.0)
                            )
                        controller.set_max_speed(PEDESTRIAN_TYPE[agent["behavior"]])
                        walker_controller.set_controller(controller)
                        self.ai_controller_list.append(controller)

                elif agent["action"] == "block_the_ego":
                    if agent["relative_to_ego"] != "at_the_destination":
                        ego_lane_id = ego_car_point.lane_id
                    else:
                        ego_lane_id = ego_agent.destination_waypoint.lane_id
                    different_direction = spawn_point.lane_id * ego_lane_id < 0
                    if different_direction:
                        find_point = get_different_lane(spawn_point)
                        destination = self.world_manager.get_waypoint_from_location_with_ensure(
                            find_point,
                            [
                                carla.LaneType.Sidewalk,
                                carla.LaneType.Shoulder,
                                carla.LaneType.Driving,
                            ],
                        )
                    else:
                        destination = spawn_point
                    cur_depth = 0
                    while destination.lane_id != ego_lane_id and cur_depth < MAX_DEPTH:
                        new_des = destination.get_left_lane()
                        if new_des is None:
                            break
                        else:
                            destination = new_des
                        cur_depth += 1
                elif agent["action"] == "on_the_sidewalk":
                    destination = random.choice(
                        get_points_to_front(spawn_point)[1:] + get_points_to_end(spawn_point)[1:]
                    )

                walker_controller.set_destination(destination.transform.location)
            self.walker_controller_list.append(walker_controller)

    def check_walker_spawn_type(self, waypoint, target_road_type=None):
        for road_type in ["Sidewalk", "Shoulder", "Driving"]:
            if target_road_type is not None and road_type.lower() != target_road_type:
                continue
            check_road_type = self.world_manager.get_waypoint_from_location(
                waypoint.transform.location, lane_type=getattr(carla.LaneType, road_type)
            )
            if check_road_type is not None and check_road_type.road_id == waypoint.road_id:
                return road_type
            target_road_type = None
        return "Driving"

    def spawn_pedestrians(self, agent_info, ego_agent):
        ego_waypoint = self.world_manager.get_waypoint_from_location(
            ego_agent._vehicle.get_location(), carla.LaneType.Driving
        )
        if ego_waypoint.is_junction:
            ego_waypoint = ego_waypoint.next(DISTANCE_FOR_ROUTE * 2)[0]
        self.world_manager.set_attribute("set_pedestrians_cross_factor", 0.0)
        for agent in agent_info:
            walker_spawn_type = self.check_walker_spawn_type(ego_waypoint, agent["road_type"])
            # Agent can be from left to right or right to left
            if agent["relative_to_ego"] == "front":
                agent["relative_to_ego"] = random.choice(["front_right", "front_left"])
            elif agent["relative_to_ego"] == "back":
                agent["relative_to_ego"] = random.choice(["back_right", "back_left"])

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
                spawn_point = self.back_pos_id_to_waypoint[agent["pos_id"]].transform.location
                if agent["relative_to_ego"].endswith("left"):
                    spawn_point = get_different_lane(spawn_point)
                else:
                    spawn_point = spawn_point.transform.location
            elif agent["relative_to_ego"] == "at_the_destination":
                spawn_point = ego_agent.destination_waypoint

                if spawn_point is None:
                    spawn_point = ego_agent._vehicle.get_location()
                    spawn_point = self.world_manager.get_waypoint_from_location(
                        spawn_point, lane_type=carla.LaneType.Driving
                    )
                    spawn_point = spawn_point.next(DISTANCE_FOR_ROUTE)[0]
                else:
                    spawn_point = spawn_point.previous(DISTANCE_FOR_ROUTE)[0]
                if random.random() < 0.5:
                    spawn_point = get_different_lane(spawn_point)
                else:
                    spawn_point = spawn_point.transform.location
            elif agent["relative_to_ego"] == "near_the_crosswalk":
                spawn_point = ego_agent._vehicle.get_location()
                spawn_point = self.world_manager.get_waypoint_from_location(
                    spawn_point, lane_type=carla.LaneType.Driving
                )
                spawn_point = get_points_to_front(spawn_point)[-1]
                spawn_point = spawn_point.transform.location
            else:
                continue

            spawn_point = self.world_manager.get_waypoint_from_location_with_ensure(
                spawn_point,
                lane_type_list=[
                    getattr(carla.LaneType, walker_spawn_type),
                    carla.LaneType.Shoulder,
                    carla.LaneType.Driving,
                ],
            )

            new_spawn_point = None
            if "right" in agent["relative_to_ego"] and spawn_point.lane_id == ego_waypoint.lane_id:
                new_spawn_point = spawn_point.get_right_lane()
            if "left" in agent["relative_to_ego"] and spawn_point.lane_id == ego_waypoint.lane_id:
                new_spawn_point = spawn_point.get_left_lane()
            if new_spawn_point is not None:
                spawn_point = new_spawn_point
            if spawn_point is not None:
                self.spawn_pedestrian(agent, spawn_point, ego_agent, ego_waypoint)

    def set_new_manager(self, agent_model_manager: AgentModelManager, world_manager: WorldManager):
        self.agent_model_manager = agent_model_manager
        self.world_manager = world_manager

    def run_step(self):
        walker_controller_list = []
        for walker_controller in self.walker_controller_list:
            finish = walker_controller.run_step()
            if not finish:
                walker_controller_list.append(walker_controller)
        self.walker_controller_list = walker_controller_list

    def clean(self):
        for pedestrian in self.pedestrian_list:
            if pedestrian.is_alive:
                pedestrian.destroy()

        for ai_controller in self.ai_controller_list:
            if ai_controller.is_alive:
                ai_controller.stop()

        if len(self.pedestrian_list) > 0:
            self.world_manager.world.tick()
