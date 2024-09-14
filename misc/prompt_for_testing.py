PROMPTS_FOR_TESTING = [
    # Three cases for critical scenario
    "A dangerous motorcycle on the right front is trying to turn left. The ego car is going straight.",
    "A car on the front left is trying to block the ego car. A dangerous pedestrian on the shoulder right in front of a stopped truck is crossing the road. Both the truck and the pedestrian are in the front right of the ego car.",
    "Two cars from the opposite straight is coming when the ego car is turning left.",
    # Three cases for normal scenario
    "The ego car is going straight.",
    "Three cars including the ego car are driving. The car in front go straight. The ego is turning right. The car behind the ego is turning left.",
    "A bus coming from the left road is turning left. A truck from the opposite straight is turning right. The ego car is turning right. Two cars in front of the ego car are going straight.",
    "The ego vehicle is turning left. A pedestrian on the destination suddenly block the ego.",
    # Three cases for the conditional generation
    "The ego car is turning left at the intersection with no traffic light and stop sign. Three cars from the opposite straight are turning right.",
    "The ego car is going straight at the intersection with a traffic light. There are some puddles on the road.",
    "A pedestrian is crossing the road with the parallel open crosswalk and the ego car is turning left.",
]
