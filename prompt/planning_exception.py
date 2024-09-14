from misc.constant import (
    ACTION,
    AGENT_BEHAVIOR,
    AGENT_TYPE,
    RELATIVE_POSITION,
    ROAD_TYPE,
    WEATHER,
)


def check_parsable(input):
    try:
        return eval(input)
    except Exception:
        return "The output can not read as a dictionary in Python.\n"


def check_outside_key(input):
    output_message = ""
    if "env" not in input:
        output_message += "Key `env` is missing in the dictionary.\n"
    if "agents" not in input:
        output_message += "Key `agents` is missing in the dictionary.\n"
    return output_message


def check_env_key(input):
    output_message = ""
    if "weather" not in input["env"]:
        output_message += "Key `weather` is missing in the `env` dictionary.\n"
    if "at_junction" not in input["env"]:
        output_message += "Key `at_junction` is missing in the `env` dictionary.\n"
    return output_message


def check_env_val_type(input):
    output_message = ""
    if not isinstance(input["env"]["weather"], str):
        output_message += "The value of `weather` should be a string.\n"
    if not isinstance(input["env"]["at_junction"], bool):
        try:
            input["env"]["at_junction"] = input["env"]["at_junction"].lower() == "true"
        except Exception:
            output_message += "The value of `at_junction` cannot be represent as boolean.\n"
    return output_message


def check_env_weather_val(input):
    output_message = ""
    if input["env"]["weather"] not in WEATHER:
        output_message = "The value of `weather` in `env` is not in predefined_list.\n"
    return output_message


def check_agents_key(input):
    output_message = ""
    for agent in input["agents"]:
        if agent["is_ego"]:
            continue
        if "type" not in agent:
            output_message += "Key `type` is missing in the `agents` dictionary.\n"
        if "action" not in agent:
            output_message += "Key `action` is missing in the `agents` dictionary.\n"
        if "is_ego" not in agent:
            output_message += "Key `is_ego` is missing in the `agents` dictionary.\n"
        if "behavior" not in agent:
            output_message += "Key `behavior` is missing in the `agents` dictionary.\n"
        if "pos_id" not in agent:
            output_message += "Key `pos_id` is missing in the `agents` dictionary.\n"
        if "road_type" not in agent:
            output_message += "Key `road_type` is missing in the `agents` dictionary.\n"
        if "relative_to_ego" not in agent:
            output_message += "Key `relative_to_ego` is missing in the `agents` dictionary.\n"

        if output_message != "":
            return output_message
    return output_message


def check_agents_val_type(input):
    output_message = ""
    for agent in input["agents"]:
        if agent["is_ego"]:
            continue
        if not isinstance(agent["type"], str):
            return "The value of `type` should be a string.\n"
        if not isinstance(agent["action"], str):
            return "The value of `action` should be a string.\n"
        if not isinstance(agent["is_ego"], bool):
            try:
                agent["is_ego"] = agent["is_ego"].lower() == "true"
            except Exception:
                return "The value of `is_ego` cannot be represent as boolean.\n"
        if not isinstance(agent["behavior"], str):
            return "The value of `behavior` should be a string.\n"
        if not isinstance(agent["pos_id"], int):
            return "The value of `pos_id` should be an integer.\n"
        if not isinstance(agent["road_type"], str):
            return "The value of `road_type` should be a string.\n"
        if not isinstance(agent["relative_to_ego"], str):
            return "The value of `relative_to_ego` should be a string.\n"

        if output_message != "":
            return output_message
    return output_message


def check_agents_val(input):
    output_message = ""
    for agent in input["agents"]:
        if agent["is_ego"]:
            continue
        if agent["type"] not in AGENT_TYPE:
            output_message += "The value of `type` is not in predefined list.\n"
        if agent["action"] not in ACTION:
            output_message += "The value of `action` is not in predefined list.\n"
        if agent["behavior"] not in AGENT_BEHAVIOR:
            output_message += "The value of `behavior` is not in predefined list.\n"
        if agent["road_type"] not in ROAD_TYPE:
            output_message += "The value of `road_type` is not in predefined list.\n"
        if agent["relative_to_ego"] not in RELATIVE_POSITION:
            output_message += "The value of `relative_to_ego` is not in predefined list.\n"

        if output_message != "":
            return output_message
    return output_message


def check_planning_output(input):
    all_func = [
        check_outside_key,
        check_env_key,
        check_env_val_type,
        check_env_weather_val,
        check_agents_key,
        check_agents_val_type,
        check_agents_val,
    ]

    output = check_parsable(input)
    if isinstance(output, str):
        return False, output

    for func in all_func:
        output_message = func(output)
        if output_message != "":
            return False, output_message

    return True, output
