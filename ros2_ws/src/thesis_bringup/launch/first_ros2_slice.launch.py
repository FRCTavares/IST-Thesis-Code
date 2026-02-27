from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    inference = Node(
        package="thesis_inference_client",
        executable="inference_client_node",
        name="inference_client_node",
        output="screen",
        parameters=[
            {
                "addr": "tcp://127.0.0.1:5555",
                "topic": "dets",
                "img_w": 640,
                "img_h": 640,
                "min_score": 0.35,
                "conflate": True,
            }
        ],
    )

    tracker = Node(
        package="thesis_tracker",
        executable="tracker_node",
        name="thesis_tracker_node",
        output="screen",
        parameters=[
            {
                "iou_threshold": 0.18,
                "max_age": 4,
                "min_hits": 3,
                "min_score": 0.35,
            }
        ],
    )

    selector = Node(
        package="thesis_target_selector",
        executable="target_selector_node",
        name="thesis_target_selector_node",
        output="screen",
    )

    return LaunchDescription([inference, tracker, selector])