import random

import carla
import numpy as np

PEDESTRIAN_TYPE = {
    "cautious": 0.3,
    "normal": 0.5,
    "aggressive": 1.0,
}

TO_TARGET_THRESHOLD = 1.0
SPEED_FACTOR = 4.0


class PedestrianAgent:
    def __init__(self, walker, behavior="normal", plan=False):
        self.walker = walker
        self.ai_controller = None
        self.behavior = behavior
        self.plan = plan
        self.start_walking = False
        self.destination = None
        self.des_norm_vector = None
        self.speed = None
        self.ego_agent = None  # This is used only for adaptive control
        self.factor = 1.0
        self.ego_straight_vector = None

    def set_controller(self, ai_controller):
        self.ai_controller = ai_controller

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

    def set_destination(self, destination):
        self.destination = destination
        direction = self.destination - self.walker.get_location()
        norm = np.linalg.norm([direction.x, direction.y])
        if norm < 1e-3:
            self.des_norm_vector = carla.Vector3D(1, 0, 0)
        else:
            self.des_norm_vector = carla.Vector3D(direction.x / norm, direction.y / norm, 0)

    def check_finish(self):
        current_location = self.walker.get_location()
        if self.destination is not None:
            return self.destination.distance(current_location) < TO_TARGET_THRESHOLD

    def _normal_step(self, speed):
        self.walker.apply_control(
            carla.WalkerControl(
                direction=self.des_norm_vector,
                speed=speed,
            )
        )

    def _plan_step(self, move_dis_threshold=28.0):
        ego_location = self.ego_agent.get_location()
        distance_to_ego = ego_location.distance(self.walker.get_location())
        if not self.start_walking:
            self.start_walking = distance_to_ego <= move_dis_threshold
            if not self.start_walking:
                return

        walker_location = self.walker.get_location()
        walker_to_destination = self.destination.distance(walker_location)
        car_to_walker_destination = self.destination.distance(ego_location)
        ego_agent_throttle = self.ego_agent.get_control().throttle
        if ego_agent_throttle < 1e-3:
            return

        speed = (
            walker_to_destination
            / car_to_walker_destination
            * ego_agent_throttle
            * SPEED_FACTOR
            * self.factor
        )
        speed = max(speed, 1.0)
        self._normal_step(speed=speed)

    def run_step(self):
        if self.destination is None or not self.walker.is_alive or not self.ego_agent.is_alive:
            if self.ai_controller is not None:
                self.ai_controller.stop()
            return True
        if self.check_finish():
            if self.ai_controller is None:
                self.walker.apply_control(carla.WalkerControl())
                self.destination = None
            else:
                self.ai_controller.stop()
            return True

        if self.ai_controller is not None:
            return False

        if self.plan:
            self._plan_step()
        else:
            self._normal_step(
                speed=(1 + random.random()) * PEDESTRIAN_TYPE[self.behavior],
            )
        return False
