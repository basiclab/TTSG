import carla

from misc.constant import DISTANCE_FOR_ROUTE


class WorldManager:
    def __init__(self, world=None):
        self.world = world
        self.map = world.get_map() if world is not None else None

    def set_world(self, world):
        self.world = world
        self.map = world.get_map()

    def get_random_location_from_navigation(self):
        return self.world.get_random_location_from_navigation()

    def set_attribute(self, attribute, value):
        getattr(self.world, attribute)(value)

    def draw_point(self, location, color=(255, 0, 0)):
        self.world.debug.draw_string(
            location,
            "O",
            color=carla.Color(*color),
            life_time=10,
            draw_shadow=False,
            persistent_lines=True,
        )

    def get_waypoint_from_location(self, location, lane_type):
        return self.map.get_waypoint(
            location,
            project_to_road=True,
            lane_type=lane_type,
        )

    def get_waypoint_from_location_with_ensure(self, location, lane_type_list):
        for lane_type in lane_type_list:
            waypoint = self.get_waypoint_from_location(location, lane_type)
            if waypoint is not None:
                return waypoint
        return self.get_waypoint_from_location(location, carla.LaneType.Driving)

    def get_all_waypoints_from_road(self, road_id):
        all_waypoints = self.map.generate_waypoints(distance=DISTANCE_FOR_ROUTE)
        road_waypoints = []
        for waypoint in all_waypoints:
            waypoint = self.map.get_waypoint(waypoint.transform.location)
            if waypoint is not None and waypoint.road_id == road_id:
                road_waypoints.append(waypoint)
        return road_waypoints

    def compute_distance(self, location1, location2):
        return location1.distance(location2)

    def get_side_walk(self, road_id):
        road_waypoints = self.get_all_waypoints_from_road(road_id)
        side_walk_points = []
        for waypoint in road_waypoints:
            side_walk_point = self.map.get_waypoint(
                waypoint.transform.location,
                project_to_road=True,
                lane_type=carla.LaneType.Sidewalk,
            )
            if side_walk_point is not None:
                side_walk_points.append(side_walk_point)
        return side_walk_points

    def get_shoulder(self, road_id):
        road_waypoints = self.get_all_waypoints_from_road(road_id)
        shoulder_points = []
        for waypoint in road_waypoints:
            shoulder_point = self.map.get_waypoint(
                waypoint.transform.location,
                project_to_road=True,
                lane_type=carla.LaneType.Shoulder,
            )
            if shoulder_point is not None:
                shoulder_points.append(shoulder_point)
        return shoulder_points

    def get_driving(self, road_id):
        road_waypoints = self.get_all_waypoints_from_road(road_id)
        # driving_points = []
        # for waypoint in road_waypoints:
        #     driving_point = self.map.get_waypoint(
        #         waypoint.transform.location,
        #         project_to_road=True,
        #         lane_type=carla.LaneType.Driving,
        #     )
        #     if driving_point is not None and (
        #         (len(driving_points) == 0)
        #         or (
        #             min(
        #                 [
        #                     self.compute_distance(
        #                         driving_point.transform.location, exist_point.transform.location
        #                     )
        #                     for exist_point in driving_points
        #                 ]
        #             )
        #             > 1.5
        #         )
        #     ):
        #         driving_points.append(driving_point)
        return road_waypoints

    def get_left_right_driving_points(self, road_id):
        if not isinstance(road_id, (list, tuple)):
            road_id = [road_id]
        road_waypoints = []
        for road in road_id:
            road_waypoints.extend(self.get_driving(road))
        right_driving_points = []
        left_driving_points = []
        for driving_point in road_waypoints:
            if driving_point.lane_id < 0:
                right_driving_points.append(driving_point)
            elif driving_point.lane_id > 0:
                left_driving_points.append(driving_point)
        return right_driving_points, left_driving_points

    def get_driving_points_with_road_and_lane_id(self, road_id, lane_id):
        if not isinstance(road_id, (list, tuple)):
            road_id = [road_id]
        road_waypoints = []
        for road in road_id:
            road_waypoints.extend(self.get_driving(road))
        driving_points = []
        for driving_point in road_waypoints:
            if driving_point.lane_id == lane_id:
                driving_points.append(driving_point)
        return driving_points

    def spawn_actor(self, blueprint, transform, attach_to=None, tick=True):
        actor = self.world.try_spawn_actor(blueprint, transform, attach_to)
        if actor is not None and tick:
            self.world.tick()
        return actor
