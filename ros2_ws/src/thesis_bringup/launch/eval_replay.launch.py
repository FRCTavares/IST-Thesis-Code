import os
from datetime import datetime

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
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

    tracker = Node(
        package="thesis_tracker",
        executable="tracker_node",
        name="thesis_tracker_node",
        output="screen",
        parameters=[
            {
                # keep your SORT params as defaults
                "iou_threshold": 0.18,
                "max_age": 4,
                "min_hits": 3,
                "min_score": 0.35,

                # future-proof: switch tracker implementation internally
                "tracker": tracker_type,
            }
        ],
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

    # Order: start nodes, start recorder, then play bag
    return [tracker, selector, record, echo, play]


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