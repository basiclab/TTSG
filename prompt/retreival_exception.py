from misc.constant import OBJECT_SEARCH_DICT, SIGNAL_SEARCH_DICT


def check_parsable(input):
    try:
        return eval(input)
    except Exception:
        return "The output can not read as a dictionary in Python.\n"


def check_length(input):
    if len(input) != 5:
        return "The instance should have 5 keys, 'number_of_lanes', 'required_objects', 'required_signals', 'without_objects', and 'without_signals'.\n"
    return ""


def check_keys(input):
    output_message = ""
    for key in input.keys():
        if key not in [
            "number_of_lanes",
            "required_objects",
            "required_signals",
            "without_objects",
            "without_signals",
        ]:
            output_message += f"Key {key} is not in the predefined list. Should only include 'number_of_lanes', 'required_objects', 'required_signals', 'without_objects', and 'without_signals'\n"
    return output_message


def check_type(instance):
    output_message = ""
    if not isinstance(instance["number_of_lanes"], int):
        output_message += "The 'number_of_lanes' should be an integer.\n"
    if not isinstance(instance["required_objects"], (list, tuple)):
        output_message += "The 'required_objects' should be a list.\n"
    if not isinstance(instance["required_signals"], (list, tuple)):
        output_message += "The 'required_signals' should be a list.\n"
    if not isinstance(instance["without_objects"], (list, tuple)):
        output_message += "The 'without_objects' should be a list.\n"
    if not isinstance(instance["without_signals"], (list, tuple)):
        output_message += "The 'without_signals' should be a list.\n"

    return output_message


def check_predifined(instance):
    output_message = ""
    for obj in instance["required_objects"]:
        if obj not in OBJECT_SEARCH_DICT:
            output_message += (
                f"The object {obj} is not in the predefined list for 'required_objects'.\n"
            )
    for signal in instance["required_signals"]:
        if signal not in SIGNAL_SEARCH_DICT:
            output_message += (
                f"The signal {signal} is not in the predefined list for 'required_signals'.\n"
            )
    for obj in instance["without_objects"]:
        if obj not in OBJECT_SEARCH_DICT:
            output_message += (
                f"The object {obj} is not in the predefined list for 'without_objects'.\n"
            )
    for signal in instance["without_signals"]:
        if signal not in SIGNAL_SEARCH_DICT:
            output_message += (
                f"The signal {signal} is not in the predefined list 'without_signals'.\n"
            )
    return output_message


def check_retreival_output(input):
    all_func = [check_length, check_keys, check_type, check_predifined]

    output = check_parsable(input)
    if isinstance(output, str):
        return False, output

    for func in all_func:
        output_message = func(output)
        if output_message != "":
            return False, output_message
    return True, output
