from misc.constant import ACTION, AGENT_TYPE, ROAD_TYPE


def check_parsable(input):
    try:
        return eval(input)
    except Exception:
        return "The output can not read as a dictionary in Python.\n"


def check_key_in_dict(input):
    if len(input) > 4:
        return "There should only be `signals`, `objects`, `agents` and `unknown` keys in the dictionary.\n"
    elif len(input) < 4:
        return (
            "There should be `signals`, `objects`, `agents` and `unknown` keys in the dictionary.\n"
        )

    output_message = ""
    for key in ["signals", "objects", "agents", "unknown"]:
        if key not in input:
            output_message += f"Key `{key}` is missing in the dictionary.\n"

    return output_message


def check_key_in_agents(input):
    agents = input["agents"]
    output_message = ""
    for agent in agents:
        if len(agent) > 3:
            output_message += "Each agent should only have `type`, `road_type` and `action` keys.\n"
        elif len(agent) < 3:
            output_message += "Each agent should have `type`, `road_type` and `action` keys.\n"
        else:
            for key in ["type", "road_type", "action"]:
                if key not in agent:
                    output_message += f"Key `{key}` is missing in the agent dictionary.\n"

    return output_message


def check_key_type_in_agents(input):
    agents = input["agents"]
    output_message = ""
    for agent in agents:
        if agent["type"] not in AGENT_TYPE:
            output_message += f"Agent type `{agent['type']}` is not in the predefined list.\n"
        if agent["road_type"] not in ROAD_TYPE:
            output_message += (
                f"Agent road type `{agent['road_type']}` is not in the predefined list.\n"
            )
        if agent["action"] not in ACTION:
            output_message += f"Agent action `{agent['action']}` is not in the predefined list.\n"

    return output_message


def check_analysis_output(input):
    all_func = [check_key_in_dict, check_key_in_agents, check_key_type_in_agents]

    output = check_parsable(input)
    if isinstance(output, str):
        return False, output

    for func in all_func:
        output_message = func(output)
        if output_message != "":
            return False, output_message

    return True, output
