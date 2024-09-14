CODE_SNIPPET = """
def create_graph(opendrive_root, in_graph=None, town_name=""):
    if in_graph is None:
        graph = nx.DiGraph()
    else:
        graph = in_graph
    road_elements = opendrive_root.findall("road")
    available_signal_names = set()
    available_object_names = set()

    if town_name != "":
        town_name += "_"

    for road in road_elements:
        road_id = road.get("id")
        length = road.get("length")
        signals = [
            {
                "name": signal.get("name"),
                "type": signal.get("type"),
                "id": signal.get("id"),
                "orientation": signal.get("orientation"),
            }
            for signal in road.findall("signals/signal")
        ]
        for signal in signals:
            available_signal_names.add(signal.get("name"))
        objects = [
            {
                "name": object_.get("name"),
                "type": object_.get("type"),
                "id": object_.get("id"),
                "orientation": object_.get("orientation"),
            }
            for object_ in road.findall("objects/object")
        ]
        for object_ in objects:
            available_object_names.add(object_.get("name"))
        lane_sections = []
        lane_center_indices = []
        for lane_section in road.findall("lanes/laneSection"):
            temp_lane_info = []

            # left lane
            left_lanes = lane_section.findall("left/lane")
            left_lanes.sort(key=lambda x: x.get("id"), reverse=True)

            temp_lane_info.extend(
                {
                    "type": left_lane.get("type"),
                    "id": left_lane.get("id"),
                }
                for left_lane in left_lanes
            )

            lane_center_indices.append(len(left_lanes))
            # center lane
            center_lane = lane_section.findall("center/lane")
            temp_lane_info.append(
                {
                    "type": center_lane[0].get("type"),
                    "id": center_lane[0].get("id"),
                }
            )

            # right lane
            right_lanes = lane_section.findall("right/lane")
            right_lanes.sort(key=lambda x: x.get("id"))

            temp_lane_info.extend(
                {
                    "type": right_lane.get("type"),
                    "id": right_lane.get("id"),
                }
                for right_lane in right_lanes
            )
            lane_sections.append(temp_lane_info)

        graph.add_node(
            f"{town_name}{road_id}",
            road_id=road_id,
            length=length,
            lane_sections=lane_sections,
            lane_center_indices=lane_center_indices,
            signal_object=signals,
            objects=objects,
        )

    junction_elements = opendrive_root.findall("junction")

    for junction in junction_elements:
        connections = junction.findall("connection")
        for connection in connections:
            incoming_road = connection.get("incomingRoad")
            connecting_road = connection.get("connectingRoad")
            graph.add_edge(
                f"{town_name}{incoming_road}",
                f"{town_name}{connecting_road}",
                junction_id=junction.get("id"),
            )

    if in_graph is None:
        return graph
"""

OBJECT_UNUSED = [
    "DashedSingleYellow",
    "Stencil_ArrowType4L",
    "oneWayL_Assembly",
    "ChevronRegion",
    "LaneR_L2_Assembly",
    "Stencil_STOP",
    "NoTurnLeft_Round_Assembly",
    "DoNotEnter_Assembly",
    "LaneR_L3Assembly",
    "LaneR_L1_Assembly",
    "Stencil_ArrowType4R",
    "SignPost_10ft",
    "NoTurn_Assembly",
    "LaneR_L0_Assembly",
    "oneWayR_Assembly",
    "MichiganTurnAssembly",
]

OBJECT_SEARCH_DICT = {
    "speed_30": ["speed_30", "Speed_30", "Speedlimit30Assembly"],
    "speed_40": ["Speed_40", "Speedlimit40Assembly"],
    "speed_60": ["speed_60", "Speed_60", "Speedlimit60Assembly"],
    "speed_90": ["Speed_90", "Speedlimit90Assembly"],
    "parallel_open_crosswalk": ["SimpleCrosswalk"],
    "ladder_crosswalk": ["LadderCrosswalk"],
    "continental_crosswalk": ["ContinentalCrosswalk"],
    "dashed_single_white": ["DashedSingleWhite"],
    "solid_single_white": ["SolidSingleWhite"],
    "crosswalk": [
        "SimpleCrosswalk",
        "LadderCrosswalk",
        "ContinentalCrosswalk",
        "SolidSingleWhite",
        "DashedSingleWhite",
    ],
    "stop_line": ["StopLine"],
    "stop_sign_on_road": ["StopSign", "Stencil_STOP"],
}

SIGNAL_UNUSED = []


SIGNAL_SEARCH_DICT = {
    "traffic_light": ["Signal_3Light_Post01"],
    "stop": ["Sign_Stop"],
    "yield": ["Sign_Yield"],
}


ACTION = [
    "turn_left",
    "turn_right",
    "go_straight",
    "change_lane_to_left",
    "change_lane_to_right",
    "stop",
    "block_the_ego",
    "cross_the_road",
    "on_the_sidewalk",
]
SPEED_MOVENT = ["slow down", "speed up", "constant"]
AGENT_BEHAVIOR = ["cautious", "normal", "aggressive"]
AGENT_TYPE = [
    "ambulance",
    "police",
    "firetruck",
    "bus",
    "truck",
    "motorcycle",
    "car",
    "pedestrian",
    "cyclist",
]
WEATHER = [
    "ClearNight",
    "ClearNoon",
    "ClearSunset",
    "CloudyNight",
    "CloudyNoon",
    "CloudySunset",
    "DustStorm",
    "HardRainNight",
    "HardRainNoon",
    "HardRainSunset",
    "MidRainSunset",
    "MidRainyNight",
    "MidRainyNoon",
    "SoftRainNight",
    "SoftRainNoon",
    "SoftRainSunset",
    "WetCloudyNight",
    "WetCloudyNoon",
    "WetCloudySunset",
    "WetNight",
    "WetNoon",
    "WetSunset",
]

ROAD_TYPE = ["driving", "sidewalk", "shoulder"]

RELATIVE_POSITION = """
- front: The agent is in front of the ego car
- back: The agent is behind the ego car
- left: The agent is on the left side of the ego car
- right: The agent is on the right side of the ego car
- front_left: The agent is in front and on the left side of the ego car
- front_right: The agent is in front and on the right side of the ego car
- back_left: The agent is behind and on the left side of the ego car
- back_right: The agent is behind and on the right side of the ego car
- road_of_left_turn: The agent is on different roads that ego car should take a left turn to reach
- road_of_right_turn: The agent is on different roads that ego car should take a right turn to reach
- road_of_straight: The agent is on different roads that ego car should go straight to reach
- at_the_destination: The agent is near at the destination of the ego car
- near_the_crosswalk: The agent is near at the crosswalk, used for pedestrian
"""

CAR_TYPE = [
    "ambulance",
    "police",
    "firetruck",
    "car",
    "truck",
    "bus",
    "motorcycle",
]
NUM_POINT_PER_CAR = 3
NULL_SPACE = 2
DISTANCE_FOR_ROUTE = 2.0
DIR_TO_COLOR = {
    "left": (0, 255, 0),
    "right": (0, 0, 255),
    "straight": (255, 0, 0),
}
LANE_TO_WAYPOINT = {
    "Driving": "get_driving",
    "Shoulder": "get_shoulder",
    "Sidewalk": "get_side_walk",
}
FRONT_CAMERA = {
    "x": -1.5,
    "y": 0.0,
    "z": 2.0,
    "roll": 0.0,
    "pitch": 0.0,
    "yaw": 0.0,
    "image_size_x": 900,
    "image_size_y": 256,
    "fov": 100,
}
BEV_CAMERA = {
    "x": 0.0,
    "y": 0.0,
    "z": 50.0,
    "roll": 0.0,
    "pitch": -90.0,
    "yaw": 0.0,
    "image_size_x": 512,
    "image_size_y": 512,
    "fov": 50.0,
}
