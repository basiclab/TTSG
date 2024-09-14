import argparse
import json
import os
import random

import dotenv
import numpy as np
from colorama import Fore, Style
from openai import OpenAI

from misc.create_scene_from_json import create_seed, scene_generation
from prompt import (
    SYSTEM_PROMPT,
    check_analysis_output,
    check_planning_output,
    check_retreival_output,
)
from prompt.format import (
    ANALYSIS_FORMAT,
    ANALYSIS_FORMAT_WITH_ERROR,
    PLANNING_FORMAT,
    PLANNING_FORMAT_WITH_ERROR,
    ROAD_RETREIVAL_FORMAT,
    ROAD_RETREIVAL_FORMAT_WITH_ERROR,
)

dotenv.load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(description="Text to scene")
    parser.add_argument(
        "--input-prompt",
        type=str,
        required=True,
        help="The input prompt",
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="gpt-4o",
        help="The model name",
    )
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
    parser.add_argument(
        "--return-ego",
        action="store_true",
        help="Return the ego information",
        default=False,
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Plan only",
        default=False,
    )
    parser.add_argument(
        "--max-retry",
        type=int,
        default=3,
        help="The maximum retry for each stage",
    )
    return parser.parse_args()


def split_planning_response(response):
    road_condition, agent_info = response.split("---")
    return eval(road_condition.strip()), eval(agent_info.strip())


def text_to_scene(
    input_prompt: str,
    model_name: str = "gpt-4o",
    map_folder: str = "maps",
    ip_address: str = "localhost",
    port: int = 2000,
    plan_only: bool = False,
    save_dir: str = "text_to_scene",
    use_cache: bool = True,
    cache_dir: str = "graph_cache",
    return_ego: bool = False,
    max_retry: int = 3,
):
    chat_client = OpenAI()
    analysis_success = False
    analysis_check_output = None
    analysis_output = None
    count_analysis_retry = 0
    while not analysis_success and count_analysis_retry < max_retry:
        if analysis_check_output is None or analysis_output is None:
            analysis_input = ANALYSIS_FORMAT.format(
                description=input_prompt,
                return_ego="True" if return_ego else "False",
            )
        else:
            analysis_input = ANALYSIS_FORMAT_WITH_ERROR.format(
                description=input_prompt,
                return_ego="True" if return_ego else "False",
                error=analysis_check_output,
                previous_output=analysis_output,
            )
        analysis_response = chat_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": analysis_input},
            ],
            temperature=0.9,
        )
        try:
            analysis_output = analysis_response.choices[0].message.content
            analysis_success, analysis_check_output = check_analysis_output(analysis_output)
            print(f"{Style.BRIGHT}Analysis input{Style.RESET_ALL}: {analysis_input}")
            print(f"{Style.BRIGHT}Analysis output{Style.RESET_ALL}: {analysis_output}")
            print(
                f"{Style.BRIGHT}Analysis check message{Style.RESET_ALL}: {Fore.GREEN + 'success' + Style.RESET_ALL if analysis_success else Fore.RED + analysis_check_output + Style.RESET_ALL}"
            )
        except Exception as e:
            print(str(e))
            analysis_output = None
        count_analysis_retry += 1

    retreival_success = False
    retreival_check_output = None
    retreival_output = None
    count_retreival_retry = 0
    while not retreival_success and count_retreival_retry < max_retry:
        if retreival_check_output is None or retreival_output is None:
            retreival_input = ROAD_RETREIVAL_FORMAT.format(
                description=input_prompt,
                analysis_context=analysis_output,
                return_ego="True" if return_ego else "False",
            )
        else:
            retreival_input = ROAD_RETREIVAL_FORMAT_WITH_ERROR.format(
                description=input_prompt,
                analysis_context=analysis_output,
                return_ego="True" if return_ego else "False",
                error=retreival_check_output,
                previous_output=retreival_output,
            )
        retreival_response = chat_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": retreival_input},
            ],
            temperature=0.9,
        )
        try:
            retreival_output = retreival_response.choices[0].message.content
            retreival_success, retreival_check_output = check_retreival_output(retreival_output)
            print(f"{Style.BRIGHT}Retreival input{Style.RESET_ALL}: {retreival_input}")
            print(f"{Style.BRIGHT}Retreival output{Style.RESET_ALL}: {retreival_output}")
            print(
                f"{Style.BRIGHT}Retreival check message{Style.RESET_ALL}: {Fore.GREEN + 'success' + Style.RESET_ALL if retreival_success else Fore.RED + retreival_check_output + Style.RESET_ALL}"
            )
        except Exception:
            retreival_output = None
        count_retreival_retry += 1

    planning_success = False
    planning_check_output = None
    planning_output = None
    count_planning_retry = 0
    while not planning_success and count_planning_retry < max_retry:
        if planning_check_output is None or planning_output is None:
            planning_input = PLANNING_FORMAT.format(
                description=input_prompt,
                analysis_context=analysis_output,
                return_ego={"True" if return_ego else "False"},
            )
        else:
            planning_input = PLANNING_FORMAT_WITH_ERROR.format(
                description=input_prompt,
                analysis_context=analysis_output,
                return_ego={"True" if return_ego else "False"},
                error=planning_check_output,
                previous_output=planning_output,
            )
        planning_response = chat_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": planning_input},
            ],
            temperature=0.9,
        )
        try:
            planning_output = planning_response.choices[0].message.content
            planning_success, planning_check_output = check_planning_output(planning_output)
            print(f"{Style.BRIGHT}Planning input{Style.RESET_ALL}: {planning_input}")
            print(f"{Style.BRIGHT}Planning output{Style.RESET_ALL}: {planning_output}")
            print(
                f"{Style.BRIGHT}Planning check message{Style.RESET_ALL}: {Fore.GREEN  + 'success' + Style.RESET_ALL if planning_success else Fore.RED  + planning_check_output + Style.RESET_ALL}"
            )
        except Exception:
            planning_output = None
        count_planning_retry += 1

    os.makedirs(save_dir, exist_ok=True)
    with open(f"{save_dir}/agent_output.json", "w") as f:
        json.dump(
            {
                "analysis": analysis_check_output,
                "retreival": retreival_check_output,
                "planning": planning_check_output,
            },
            f,
            indent=2,
        )
    with open(f"{save_dir}/prompt.txt", "w") as f:
        f.write(str(input_prompt))

    if not plan_only:
        scene_generation(
            retreival_check_output,
            planning_check_output,
            save_dir=save_dir,
            use_cache=use_cache,
            cache_dir=cache_dir,
            ip_address=ip_address,
            port=port,
            map_folder=map_folder,
            return_ego=return_ego,
        )


if __name__ == "__main__":
    args = parse_args()
    # create_seed()
    text_to_scene(
        input_prompt=args.input_prompt,
        model_name=args.model_name,
        map_folder=args.map_folder,
        ip_address=args.ip_address,
        port=args.port,
        plan_only=args.plan_only,
        save_dir=args.save_dir,
        use_cache=args.use_cache,
        cache_dir=args.cache_dir,
        return_ego=args.return_ego,
        max_retry=args.max_retry,
    )
