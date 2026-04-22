import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # Get default SORT config
    bringup_share = get_package_share_directory("thesis_bringup")
    tracker_config = os.path.join(bringup_share, "config", "tracker_sort.yaml")
    
    detector = Node(
        package="thesis_inference_client",
        executable="detector_node",
        name="detector_node",
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

    target_bridge = Node(
        package="thesis_bringup",
        executable="dashboard_bridge_node",
        name="dashboard_bridge_node",
        output="screen",
        parameters=[
            {
                "ws_host": "127.0.0.1",
                "ws_port": 0,
                "api_host": "127.0.0.1",
                "api_port": 0,
                "publish_hz": 30.0,
            }
        ],
    )

    # This slice exposes bridge-owned target publication, but no target is selected by default.
    return LaunchDescription([detector, tracker, target_bridge])
