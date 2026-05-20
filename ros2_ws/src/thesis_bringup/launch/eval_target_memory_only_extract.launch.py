import os
from datetime import datetime

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, RegisterEventHandler, Shutdown, TimerAction
from launch.event_handlers import OnProcessExit
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _setup(context, *args, **kwargs):
    bag = LaunchConfiguration("bag").perform(context)
    out_root = LaunchConfiguration("out_root").perform(context)
    rate = LaunchConfiguration("rate").perform(context)
    run_date = LaunchConfiguration("run_date").perform(context)
    target_id = LaunchConfiguration("target_id").perform(context)
    select_delay_s = float(LaunchConfiguration("select_delay_s").perform(context))
    appearance_enabled = LaunchConfiguration("appearance_enabled").perform(context)

    rank_aware_enabled = LaunchConfiguration("rank_aware_reacquisition_enabled").perform(context)
    rank_aware_lost_min_total = float(LaunchConfiguration("rank_aware_lost_min_total").perform(context))
    rank_aware_lost_min_geom = float(LaunchConfiguration("rank_aware_lost_min_geom").perform(context))
    rank_aware_lost_min_app = float(LaunchConfiguration("rank_aware_lost_min_app").perform(context))
    rank_aware_lost_app_margin = float(LaunchConfiguration("rank_aware_lost_app_margin").perform(context))
    rank_aware_confirm_frames = int(LaunchConfiguration("rank_aware_confirm_frames").perform(context))
    rank_aware_missing_ttl_frames = int(LaunchConfiguration("rank_aware_missing_ttl_frames").perform(context))

    bag_base = os.path.basename(os.path.normpath(bag))
    out_dir = os.path.join(
        out_root,
        f"{run_date}__eval_tm_only__{bag_base}__target_{target_id}",
    )

    if os.path.exists(out_dir):
        i = 1
        while os.path.exists(f"{out_dir}__r{i}"):
            i += 1
        out_dir = f"{out_dir}__r{i}"

    os.makedirs(out_root, exist_ok=True)

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
                "rank_aware_reacquisition_enabled": rank_aware_enabled.lower() in ("1", "true", "yes", "on"),
                "rank_aware_lost_min_total": rank_aware_lost_min_total,
                "rank_aware_lost_min_geom": rank_aware_lost_min_geom,
                "rank_aware_lost_min_app": rank_aware_lost_min_app,
                "rank_aware_lost_app_margin": rank_aware_lost_app_margin,
                "rank_aware_confirm_frames": rank_aware_confirm_frames,
                "rank_aware_missing_ttl_frames": rank_aware_missing_ttl_frames,
            }
        ],
    )

    select_target = TimerAction(
        period=select_delay_s,
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
            "/target_memory",
            "/target_memory/status",
            "/camera/dashboard",
            "/tracks",
        ],
        output="screen",
    )

    play_cmd = [
        "ros2", "bag", "play", bag,
        "--topics",
        "/camera/dashboard",
        "/tracks",
    ]
    if rate and rate != "0":
        play_cmd += ["--rate", rate]

    play = ExecuteProcess(cmd=play_cmd, output="screen")

    echo = ExecuteProcess(
        cmd=["bash", "-lc", f'echo "[eval_tm_only] recording to: {out_dir}"'],
        output="screen",
    )

    auto_shutdown = RegisterEventHandler(
        OnProcessExit(target_action=play, on_exit=[Shutdown()])
    )

    return [target_memory, record, echo, play, select_target, auto_shutdown]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("bag", default_value=""),
            DeclareLaunchArgument(
                "out_root",
                default_value=os.path.join(
                    os.environ.get("THESIS_ROOT", os.path.expanduser("~/Desktop/Thesis-Code")),
                    "artifacts",
                    "bags",
                    "eval_tm_only",
                ),
            ),
            DeclareLaunchArgument("rate", default_value="1.0"),
            DeclareLaunchArgument("target_id", default_value="1"),
            DeclareLaunchArgument("select_delay_s", default_value="2.0"),
            DeclareLaunchArgument("appearance_enabled", default_value="true"),
            DeclareLaunchArgument("rank_aware_reacquisition_enabled", default_value="false"),
            DeclareLaunchArgument("rank_aware_lost_min_total", default_value="0.40"),
            DeclareLaunchArgument("rank_aware_lost_min_geom", default_value="0.10"),
            DeclareLaunchArgument("rank_aware_lost_min_app", default_value="0.05"),
            DeclareLaunchArgument("rank_aware_lost_app_margin", default_value="0.03"),
            DeclareLaunchArgument("rank_aware_confirm_frames", default_value="1"),
            DeclareLaunchArgument("rank_aware_missing_ttl_frames", default_value="8"),
            DeclareLaunchArgument(
                "run_date",
                default_value=datetime.now().strftime("%Y-%m-%d"),
            ),
            OpaqueFunction(function=_setup),
        ]
    )
