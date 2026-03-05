import os
from datetime import datetime

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, RegisterEventHandler, Shutdown
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    bag = LaunchConfiguration("bag").perform(context)
    tracker_type = LaunchConfiguration("tracker").perform(context)
    out_root = LaunchConfiguration("out_root").perform(context)
    rate = LaunchConfiguration("rate").perform(context)
    run_date = LaunchConfiguration("run_date").perform(context)

    bag_base = os.path.basename(os.path.normpath(bag))
    out_dir = os.path.join(out_root, f"{run_date}__eval__{bag_base}__{tracker_type}")

    if os.path.exists(out_dir):
        i = 1
        while os.path.exists(f"{out_dir}__r{i}"):
            i += 1
        out_dir = f"{out_dir}__r{i}"

    os.makedirs(out_root, exist_ok=True)

    # Get config file path based on tracker type
    bringup_share = get_package_share_directory("thesis_bringup")
    config_file = os.path.join(bringup_share, "config", f"tracker_{tracker_type}.yaml")
    
    # Validate tracker type
    if not os.path.exists(config_file):
        raise ValueError(f"Unknown tracker type: {tracker_type}. Config file not found: {config_file}")

    tracker = Node(
        package="thesis_tracker",
        executable="tracker_node",
        name="tracker_node",
        output="screen",
        parameters=[config_file],
    )

    selector = Node(
        package="thesis_target_selector",
        executable="target_selector_node",
        name="thesis_target_selector_node",
        output="screen",
    )

    record = ExecuteProcess(
        cmd=[
        "ros2", "bag", "record",
        "--storage", "mcap",
        "-o", out_dir,
        "--topics", "/tracks", "/target", "/timing_tracker",
        ],
        output="screen",
    )

    play_cmd = ["ros2", "bag", "play", bag]
    if rate and rate != "0":
        play_cmd += ["--rate", rate]
    play = ExecuteProcess(cmd=play_cmd, output="screen")

    echo = ExecuteProcess(
        cmd=["bash", "-lc", f'echo "[eval_replay] recording to: {out_dir}"'],
        output="screen",
    )

    # Shut everything down (recorder, nodes) as soon as bag play exits
    auto_shutdown = RegisterEventHandler(
        OnProcessExit(target_action=play, on_exit=[Shutdown()])
    )

    # Order: start nodes, start recorder, then play bag
    return [tracker, selector, record, echo, play, auto_shutdown]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("bag", default_value=""),
            DeclareLaunchArgument("tracker", default_value="sort"),
            DeclareLaunchArgument(
                "out_root",
                default_value=os.path.join(os.environ.get("THESIS_ROOT", os.path.expanduser("~/Desktop/Thesis-Code")),
                "bags",
                "eval",
            ),
            ),
            DeclareLaunchArgument("rate", default_value="1.0"),
            DeclareLaunchArgument(
                "run_date",
                default_value=datetime.now().strftime("%Y-%m-%d"),
            ),
            OpaqueFunction(function=_setup),
        ]
    )