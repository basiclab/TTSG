import carla
import numpy as np

from scene_utils.vector_utils import make_vector

from .behavior_agent import BehaviorAgent, RoadOption

TO_TARGET_THRESHOLD = 1.0
SPEED_FACTOR = 1.3


class CyclistAgent:
    def __init__(self, cyclist, behavior="normal", use_original=False, plan=False):
        self.cyclist = cyclist
        self.agent = BehaviorAgent(cyclist, behavior)
        if behavior == "aggressive":
            self.agent.ignore_vehicles(active=True)
            self.agent.ignore_traffic_lights(active=True)
        self.behavior = behavior
        self.plan = plan
        self.start_riding = False
        self.destination = None
        self.des_norm_vector = None
        self.speed = None
        self.ego_agent = None  # This is used only for adaptive control
        self.factor = 1.0
        self.ego_straight_vector = None
        self.use_original = False

    def set_ego_agent(self, ego_agent, factor=1.0):
        self.ego_agent = ego_agent
        self.factor = factor

    def set_ego_vector(self, ego_waypoint):
        next_waypoint = ego_waypoint.next(1)[0]
        diff_vector = np.array(
            [
                next_waypoint.transform.location.x - ego_waypoint.transform.location.x,
                next_waypoint.transform.location.y - ego_waypoint.transform.location.y,
            ]
        )
        self.ego_straight_vector = diff_vector / np.linalg.norm(diff_vector)

    def set_destination(self, world_manager, destination, spawn_point, num_interpolate):
        self.destination = destination.transform.location
        single_vector = np.array(make_vector(spawn_point, destination)) / num_interpolate
        interpolate = [
            [
                spawn_point.transform.location.x + single_vector[0] * point_idx,
                spawn_point.transform.location.y + single_vector[1] * point_idx,
            ]
            for point_idx in range(1, num_interpolate)
        ]
        plan = [
            (
                world_manager.get_waypoint_from_location(
                    carla.Location(x=point[0], y=point[1]),
                    lane_type=carla.LaneType.Sidewalk
                    | carla.LaneType.Shoulder
                    | carla.LaneType.Driving,
                ),
                RoadOption.VOID,
            )
            for point in interpolate
        ]
        self.agent._local_planner.set_global_plan(plan)

    def check_finish(self):
        current_location = self.cyclist.get_location()
        if self.destination is not None:
            return self.destination.distance(current_location) < TO_TARGET_THRESHOLD

    def _normal_step(self, speed):
        self.agent._local_planner.set_speed(speed)
        self.cyclist.apply_control(self.agent.run_step())

    def _plan_step(self, move_dis_threshold=28.0):
        ego_location = self.ego_agent.get_location()
        distance_to_ego = ego_location.distance(self.cyclist.get_location())
        if not self.start_riding:
            self.start_riding = distance_to_ego <= move_dis_threshold
            if not self.start_riding:
                self.cyclist.apply_control(carla.VehicleControl(throttle=0.1, brake=0.0))
                return

        speed = SPEED_FACTOR * self.factor * self.agent._behavior.max_speed
        self._normal_step(speed=speed)

    def run_step(self):
        if self.use_original:
            if self.agent.done():
                return True
            else:
                self.cyclist.apply_control(self.agent.run_step())
                return False

        if self.destination is None or not self.cyclist.is_alive or not self.ego_agent.is_alive:
            return True
        if self.check_finish():
            self.cyclist.apply_control(carla.VehicleControl(brake=1.0))
            self.agent._local_planner._waypoints_queue.clear()
            self.destination = None
            return True

        if self.plan:
            self._plan_step()
        else:
            self._normal_step(speed=self.agent._behavior.max_speed)

        return False

    def done(self):
        return self.agent.done()
