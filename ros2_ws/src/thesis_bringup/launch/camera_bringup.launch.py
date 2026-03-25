from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    device_arg = DeclareLaunchArgument("device", default_value="/dev/video0")
    media_dev_arg = DeclareLaunchArgument("media_dev", default_value="/dev/media0")
    sensor_subdev_arg = DeclareLaunchArgument("sensor_subdev", default_value="/dev/v4l-subdev2")

    width_arg = DeclareLaunchArgument("width", default_value="1280")
    height_arg = DeclareLaunchArgument("height", default_value="720")
    fps_arg = DeclareLaunchArgument("fps", default_value="30.0")
    flip_image_arg = DeclareLaunchArgument("flip_image", default_value="true")

    frame_id_arg = DeclareLaunchArgument("frame_id", default_value="camera")
    fourcc_arg = DeclareLaunchArgument("fourcc", default_value="UYVY")
    dashboard_topic_arg = DeclareLaunchArgument("dashboard_topic", default_value="/camera/dashboard")
    dashboard_width_arg = DeclareLaunchArgument("dashboard_width", default_value="640")
    dashboard_height_arg = DeclareLaunchArgument("dashboard_height", default_value="360")
    dashboard_fps_arg = DeclareLaunchArgument("dashboard_fps", default_value="30.0")
    publish_dashboard_topic_arg = DeclareLaunchArgument("publish_dashboard_topic", default_value="true")
    sensor_entity_arg = DeclareLaunchArgument("sensor_entity", default_value="tevs 11-0048")
    csi_entity_arg = DeclareLaunchArgument("csi_entity", default_value="csi2")
    csi_source_pad_arg = DeclareLaunchArgument("csi_source_pad", default_value="4")
    video_entity_arg = DeclareLaunchArgument("video_entity", default_value="rp1-cfe-csi2_ch0")
    trigger_mode_arg = DeclareLaunchArgument("trigger_mode", default_value="0")
    command_delay_arg = DeclareLaunchArgument("command_delay_s", default_value="0.10")
    command_timeout_arg = DeclareLaunchArgument("command_timeout_s", default_value="5.0")

    camera_capture = Node(
        package="thesis_bringup",
        executable="camera_capture_node",
        name="camera_capture_node",
        output="screen",
        parameters=[
            {
                "device": LaunchConfiguration("device"),
                "media_dev": LaunchConfiguration("media_dev"),
                "sensor_subdev": LaunchConfiguration("sensor_subdev"),
                "width": LaunchConfiguration("width"),
                "height": LaunchConfiguration("height"),
                "fps": LaunchConfiguration("fps"),
                "frame_id": LaunchConfiguration("frame_id"),
                "fourcc": LaunchConfiguration("fourcc"),
                "dashboard_topic": LaunchConfiguration("dashboard_topic"),
                "dashboard_width": LaunchConfiguration("dashboard_width"),
                "dashboard_height": LaunchConfiguration("dashboard_height"),
                "dashboard_fps": LaunchConfiguration("dashboard_fps"),
                "publish_dashboard_topic": LaunchConfiguration("publish_dashboard_topic"),
                "sensor_entity": LaunchConfiguration("sensor_entity"),
                "csi_entity": LaunchConfiguration("csi_entity"),
                "csi_source_pad": LaunchConfiguration("csi_source_pad"),
                "video_entity": LaunchConfiguration("video_entity"),
                "trigger_mode": LaunchConfiguration("trigger_mode"),
                "command_delay_s": LaunchConfiguration("command_delay_s"),
                "command_timeout_s": LaunchConfiguration("command_timeout_s"),
                "flip_image": LaunchConfiguration("flip_image"),
            }
        ],
    )

    return LaunchDescription(
        [
            device_arg,
            media_dev_arg,
            sensor_subdev_arg,
            width_arg,
            height_arg,
            fps_arg,
            frame_id_arg,
            fourcc_arg,
            dashboard_topic_arg,
            dashboard_width_arg,
            dashboard_height_arg,
            dashboard_fps_arg,
            publish_dashboard_topic_arg,
            sensor_entity_arg,
            csi_entity_arg,
            csi_source_pad_arg,
            video_entity_arg,
            trigger_mode_arg,
            command_delay_arg,
            command_timeout_arg,
            flip_image_arg,
            camera_capture,
        ]
    )
