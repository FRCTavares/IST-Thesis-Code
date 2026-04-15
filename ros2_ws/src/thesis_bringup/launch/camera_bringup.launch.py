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
    publish_width_arg = DeclareLaunchArgument("publish_width", default_value="0")
    publish_height_arg = DeclareLaunchArgument("publish_height", default_value="0")
    publish_resize_mode_arg = DeclareLaunchArgument("publish_resize_mode", default_value="letterbox")
    publish_encoding_arg = DeclareLaunchArgument("publish_encoding", default_value="bgr8")
    fps_arg = DeclareLaunchArgument("fps", default_value="30.0")
    flip_image_arg = DeclareLaunchArgument("flip_image", default_value="true")

    frame_id_arg = DeclareLaunchArgument("frame_id", default_value="camera")
    fourcc_arg = DeclareLaunchArgument("fourcc", default_value="UYVY")
    dashboard_topic_arg = DeclareLaunchArgument("dashboard_topic", default_value="/camera/dashboard")
    dashboard_width_arg = DeclareLaunchArgument("dashboard_width", default_value="640")
    dashboard_height_arg = DeclareLaunchArgument("dashboard_height", default_value="360")
    dashboard_fps_arg = DeclareLaunchArgument("dashboard_fps", default_value="30.0")
    publish_dashboard_topic_arg = DeclareLaunchArgument("publish_dashboard_topic", default_value="true")
    dashboard_publish_requires_subscribers_arg = DeclareLaunchArgument(
        "dashboard_publish_requires_subscribers", default_value="true"
    )
    capture_fps_topic_arg = DeclareLaunchArgument("capture_fps_topic", default_value="/camera/capture_fps")
    publish_capture_fps_topic_arg = DeclareLaunchArgument("publish_capture_fps_topic", default_value="true")
    sensor_entity_arg = DeclareLaunchArgument("sensor_entity", default_value="tevs 11-0048")
    csi_entity_arg = DeclareLaunchArgument("csi_entity", default_value="csi2")
    csi_source_pad_arg = DeclareLaunchArgument("csi_source_pad", default_value="4")
    video_entity_arg = DeclareLaunchArgument("video_entity", default_value="rp1-cfe-csi2_ch0")
    trigger_mode_arg = DeclareLaunchArgument("trigger_mode", default_value="0")
    apply_sensor_rate_controls_arg = DeclareLaunchArgument(
        "apply_sensor_rate_controls", default_value="true"
    )
    sensor_max_fps_arg = DeclareLaunchArgument("sensor_max_fps", default_value="30")
    sensor_ae_exposure_upper_arg = DeclareLaunchArgument("sensor_ae_exposure_upper", default_value="8333")
    sensor_ae_exposure_max_arg = DeclareLaunchArgument("sensor_ae_exposure_max", default_value="33333")
    sensor_exposure_mode_arg = DeclareLaunchArgument("sensor_exposure_mode", default_value="1")
    sensor_manual_exposure_arg = DeclareLaunchArgument("sensor_manual_exposure", default_value="8333")
    command_delay_arg = DeclareLaunchArgument("command_delay_s", default_value="0.10")
    command_timeout_arg = DeclareLaunchArgument("command_timeout_s", default_value="5.0")
    adopt_detected_sensor_resolution_arg = DeclareLaunchArgument(
        "adopt_detected_sensor_resolution", default_value="true"
    )

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
                "publish_width": LaunchConfiguration("publish_width"),
                "publish_height": LaunchConfiguration("publish_height"),
                "publish_resize_mode": LaunchConfiguration("publish_resize_mode"),
                "publish_encoding": LaunchConfiguration("publish_encoding"),
                "fps": LaunchConfiguration("fps"),
                "frame_id": LaunchConfiguration("frame_id"),
                "fourcc": LaunchConfiguration("fourcc"),
                "dashboard_topic": LaunchConfiguration("dashboard_topic"),
                "dashboard_width": LaunchConfiguration("dashboard_width"),
                "dashboard_height": LaunchConfiguration("dashboard_height"),
                "dashboard_fps": LaunchConfiguration("dashboard_fps"),
                "publish_dashboard_topic": LaunchConfiguration("publish_dashboard_topic"),
                "dashboard_publish_requires_subscribers": LaunchConfiguration(
                    "dashboard_publish_requires_subscribers"
                ),
                "capture_fps_topic": LaunchConfiguration("capture_fps_topic"),
                "publish_capture_fps_topic": LaunchConfiguration("publish_capture_fps_topic"),
                "sensor_entity": LaunchConfiguration("sensor_entity"),
                "csi_entity": LaunchConfiguration("csi_entity"),
                "csi_source_pad": LaunchConfiguration("csi_source_pad"),
                "video_entity": LaunchConfiguration("video_entity"),
                "trigger_mode": LaunchConfiguration("trigger_mode"),
                "apply_sensor_rate_controls": LaunchConfiguration("apply_sensor_rate_controls"),
                "sensor_max_fps": LaunchConfiguration("sensor_max_fps"),
                "sensor_ae_exposure_upper": LaunchConfiguration("sensor_ae_exposure_upper"),
                "sensor_ae_exposure_max": LaunchConfiguration("sensor_ae_exposure_max"),
                "sensor_exposure_mode": LaunchConfiguration("sensor_exposure_mode"),
                "sensor_manual_exposure": LaunchConfiguration("sensor_manual_exposure"),
                "command_delay_s": LaunchConfiguration("command_delay_s"),
                "command_timeout_s": LaunchConfiguration("command_timeout_s"),
                "flip_image": LaunchConfiguration("flip_image"),
                "adopt_detected_sensor_resolution": LaunchConfiguration(
                    "adopt_detected_sensor_resolution"
                ),
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
            publish_width_arg,
            publish_height_arg,
            publish_resize_mode_arg,
            publish_encoding_arg,
            fps_arg,
            frame_id_arg,
            fourcc_arg,
            dashboard_topic_arg,
            dashboard_width_arg,
            dashboard_height_arg,
            dashboard_fps_arg,
            publish_dashboard_topic_arg,
            dashboard_publish_requires_subscribers_arg,
            capture_fps_topic_arg,
            publish_capture_fps_topic_arg,
            sensor_entity_arg,
            csi_entity_arg,
            csi_source_pad_arg,
            video_entity_arg,
            trigger_mode_arg,
            apply_sensor_rate_controls_arg,
            sensor_max_fps_arg,
            sensor_ae_exposure_upper_arg,
            sensor_ae_exposure_max_arg,
            sensor_exposure_mode_arg,
            sensor_manual_exposure_arg,
            command_delay_arg,
            command_timeout_arg,
            adopt_detected_sensor_resolution_arg,
            flip_image_arg,
            camera_capture,
        ]
    )
