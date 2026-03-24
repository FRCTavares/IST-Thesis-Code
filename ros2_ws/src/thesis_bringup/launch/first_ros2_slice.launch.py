import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # Get default SORT config
    bringup_share = get_package_share_directory("thesis_bringup")
    tracker_config = os.path.join(bringup_share, "config", "tracker_sort.yaml")
    
    inference = Node(
        package="thesis_inference_client",
        executable="inference_client_node",
        name="inference_client_node",
        output="screen",
        parameters=[
            {
                "image_topic": "/camera/image_raw",
                "addr": "tcp://127.0.0.1:5556",
                "queue_size": 1,
                "img_w": 640,
                "img_h": 640,
                "label": "person",
                "min_score": 0.35,
            }
        ],
    )

    tracker = Node(
        package="thesis_tracker",
        executable="tracker_node",
        name="tracker_node",
        output="screen",
        parameters=[tracker_config],
    )

    selector = Node(
        package="thesis_target_selector",
        executable="target_selector_node",
        name="thesis_target_selector_node",
        output="screen",
    )

    return LaunchDescription([inference, tracker, selector])