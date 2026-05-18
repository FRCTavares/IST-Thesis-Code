import os
from datetime import datetime

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, RegisterEventHandler, Shutdown, TimerAction
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    bag = LaunchConfiguration("bag").perform(context)
    tracker_type = LaunchConfiguration("tracker").perform(context)
    out_root = LaunchConfiguration("out_root").perform(context)
    rate = LaunchConfiguration("rate").perform(context)
    run_date = LaunchConfiguration("run_date").perform(context)
    target_id = LaunchConfiguration("target_id").perform(context)
    appearance_enabled = LaunchConfiguration("appearance_enabled").perform(context)

    bag_base = os.path.basename(os.path.normpath(bag))
    out_dir = os.path.join(
        out_root,
        f"{run_date}__eval_tm_extract__{bag_base}__{tracker_type}__target_{target_id}",
    )

    if os.path.exists(out_dir):
        i = 1
        while os.path.exists(f"{out_dir}__r{i}"):
            i += 1
        out_dir = f"{out_dir}__r{i}"

    os.makedirs(out_root, exist_ok=True)

    bringup_share = get_package_share_directory("thesis_bringup")
    config_file = os.path.join(bringup_share, "config", f"tracker_{tracker_type}.yaml")

    if not os.path.exists(config_file):
        raise ValueError(f"Unknown tracker type: {tracker_type}. Config file not found: {config_file}")

    tracker = Node(
        package="thesis_tracker",
        executable="tracker_node",
        name="tracker_node",
        output="screen",
        parameters=[config_file],
    )

    target_memory = Node(
        package="thesis_bringup",
        executable="target_memory_node",
        name="target_memory_node",
        output="screen",
        parameters=[
            {
                "appearance_enabled": appearance_enabled.lower() in ("1", "true", "yes", "on"),
                "appearance_image_topic": "/camera/dashboard",
                "mirror_raw_target_selection": False,
                "auto_select_largest": False,
                "publish_only_when_visible": False,
            }
        ],
    )

    select_target = TimerAction(
        period=2.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "topic",
                    "pub",
                    "--once",
                    "/target_memory/select",
                    "std_msgs/msg/UInt32",
                    "{data: " + str(target_id) + "}",
                ],
                output="screen",
            )
        ],
    )

    record = ExecuteProcess(
        cmd=[
            "ros2", "bag", "record",
            "--storage", "mcap",
            "-o", out_dir,
            "--topics",
            "/tracks",
            "/target_memory",
            "/target_memory/status",
            "/timing_tracker",
            "/camera/dashboard",
        ],
        output="screen",
    )

    play_cmd = ["ros2", "bag", "play", bag]
    if rate and rate != "0":
        play_cmd += ["--rate", rate]

    play = ExecuteProcess(cmd=play_cmd, output="screen")

    echo = ExecuteProcess(
        cmd=["bash", "-lc", f'echo "[eval_tm_extract] recording to: {out_dir}"'],
        output="screen",
    )

    auto_shutdown = RegisterEventHandler(
        OnProcessExit(target_action=play, on_exit=[Shutdown()])
    )

    return [tracker, target_memory, record, echo, play, select_target, auto_shutdown]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("bag", default_value=""),
            DeclareLaunchArgument("tracker", default_value="ocsort"),
            DeclareLaunchArgument(
                "out_root",
                default_value=os.path.join(
                    os.environ.get("THESIS_ROOT", os.path.expanduser("~/Desktop/Thesis-Code")),
                    "artifacts",
                    "bags",
                    "eval_tm_extract",
                ),
            ),
            DeclareLaunchArgument("rate", default_value="1.0"),
            DeclareLaunchArgument("target_id", default_value="1"),
            DeclareLaunchArgument("appearance_enabled", default_value="true"),
            DeclareLaunchArgument(
                "run_date",
                default_value=datetime.now().strftime("%Y-%m-%d"),
            ),
            OpaqueFunction(function=_setup),
        ]
    )
