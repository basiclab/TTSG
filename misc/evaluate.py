import argparse
import glob
import json
import os

import tabulate


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate the results of the model")
    parser.add_argument("--path", type=str, default="results", help="Path to the results folder")
    return parser.parse_args()


def evaluate(path):
    all_agent_files = glob.glob(os.path.join(path, "**/agent_output.json"))
    all_road_files = glob.glob(os.path.join(path, "**/road_info.json"))

    all_agent = []
    all_road = []

    for agent_file in all_agent_files:
        with open(agent_file, "r") as f:
            agents = json.load(f)["planning"]["agents"]

        for agent in agents:
            if agent["is_ego"]:
                continue
            all_agent.append((agent["type"], agent["action"], agent["relative_to_ego"]))

    for road_file in all_road_files:
        with open(road_file, "r") as f:
            road_info = json.load(f)
            road = tuple(road_info["road_id"])
            town = road_info["town"]

        all_road.append((town, road))

    agent_diversity = len(set(all_agent)) / len(all_agent)
    road_diversity = len(set(all_road)) / len(all_road)

    print(
        tabulate.tabulate(
            [
                [agent_diversity, road_diversity],
            ],
            headers=["Agent Diversity", "Road Diversity"],
        )
    )


if __name__ == "__main__":
    args = parse_args()
    evaluate(args.path)
