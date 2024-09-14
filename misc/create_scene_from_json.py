import argparse
import json
import os
import random
import sys
import time

import numpy as np
from colorama import Fore, Style
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from scene_utils.scene_client import CarlaClient

EGO_SETUP = {
    "type": "car",
    "is_ego": True,
    "relative_to_ego": "none",
    "road_type": "driving",
    "behavior": "cautious",
}


def create_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)


def parse_args():
    parser = argparse.ArgumentParser(description="Create scene from json file")
    parser.add_argument("--json-file", type=str, help="Path to json file")
    parser.add_argument(
        "--map-folder",
        type=str,
        default="maps",
        help="The map folder",
    )
    parser.add_argument(
        "--ip-address",
        type=str,
        default="localhost",
        help="The ip address",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=2000,
        help="The port",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default="save_dir",
        help="The save directory",
    )
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Use cache",
        default=False,
    )
    parser.add_argument(
        "--cache-dir",
        type=str,
        default="graph_cache",
        help="The cache directory",
    )
    return parser.parse_args()


def scene_generation(
    retreival,
    planning,
    save_dir,
    use_cache=True,
    cache_dir="graph_cache",
    ip_address="localhost",
    port=2000,
    map_folder="maps",
    return_ego=False,
):
    carla_client = CarlaClient(
        input_folder=map_folder,
        host=ip_address,
        port=port,
        use_cache=use_cache,
        cache_dir=cache_dir,
    )
    agent_planning = planning["agents"] + ([EGO_SETUP] if not return_ego else [])
    action_list = set()
    road_type_list = set()
    agent_type_list = set()
    for agent in agent_planning:
        action_list.add((agent["action"], agent["relative_to_ego"]))
        road_type_list.add(agent["road_type"])
        agent_type_list.add(agent["type"])
    town_name, road_id, direction, road_info = carla_client.get_valid_road(
        retreival,
        list(agent_type_list),
        list(action_list),
        list(road_type_list),
    )

    if town_name is None:
        print(f"{Fore.RED}No valid road found{Style.RESET_ALL}")
        return

    print(
        f"{Style.BRIGHT}{Fore.YELLOW}Spawn information{Style.RESET_ALL}: {town_name}, {road_id}, {direction}"
    )
    print(f"{Style.BRIGHT}{Fore.YELLOW}Road information{Style.RESET_ALL}: {road_info}")

    with open(f"{save_dir}/road_info.json", "w") as f:
        json.dump(
            {"town": town_name, "road_id": road_id, "direction": direction, "road_info": road_info},
            f,
            indent=2,
        )

    carla_client.load_map(town_name, weather=planning["env"]["weather"])
    carla_client.spawn_all_agent(
        road_id[0],
        agent_planning,
        direction=direction,
        at_junction=planning["env"]["at_junction"],
    )

    os.makedirs(f"{save_dir}/front_image", exist_ok=True)
    os.makedirs(f"{save_dir}/bev_image", exist_ok=True)
    try:
        count_frame = 1
        while True:
            done, data = carla_client.check_finish()
            if count_frame > 10:
                for sensor_name, sensor_data in data.items():
                    if sensor_data is not None:
                        try:
                            Image.fromarray(sensor_data).save(
                                f"{save_dir}/{sensor_name}/{count_frame:06d}.png",
                            )
                        except Exception as e:
                            print(str(e))
            if done:
                break
            count_frame += 1
            time.sleep(0.02)

        carla_client.destroy()
    except KeyboardInterrupt:
        carla_client.destroy()


if __name__ == "__main__":
    args = parse_args()
    with open(args.json_file, "r") as f:
        data = json.load(f)
    # create_seed()
    scene_generation(
        data["retreival"],
        data["planning"],
        save_dir=args.save_dir,
        use_cache=args.use_cache,
        cache_dir=args.cache_dir,
        ip_address=args.ip_address,
        port=args.port,
        map_folder=args.map_folder,
        return_ego=True,
    )
