def make_vector(waypoint1, waypoint2):
    return (
        waypoint2.transform.location.x - waypoint1.transform.location.x,
        waypoint2.transform.location.y - waypoint1.transform.location.y,
    )


def vector_is_close(v1, v2, threshold=0.00001):
    return abs(v1[0] - v2[0]) < threshold and abs(v1[1] - v2[1]) < threshold


def cross_product(v1, v2):
    return v1[0] * v2[1] - v1[1] * v2[0]


def is_counter_clockwise(v1, v2):
    """
    The axis of the carla is:
                y
                ^
                |
                |
                |
    x <----------
    """
    return cross_product(v1, v2) < 0
