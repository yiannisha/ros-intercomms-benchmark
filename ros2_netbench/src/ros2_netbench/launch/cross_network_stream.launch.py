from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [
        DeclareLaunchArgument("role", default_value="receiver"),
        DeclareLaunchArgument("payload_size", default_value="1024"),
        DeclareLaunchArgument("rate_hz", default_value="10"),
        DeclareLaunchArgument("duration", default_value="10"),
        DeclareLaunchArgument("warmup", default_value="2"),
        DeclareLaunchArgument("topic", default_value="/netbench/stream"),
        DeclareLaunchArgument("output_dir", default_value="results"),
        DeclareLaunchArgument("reliability", default_value="reliable"),
        DeclareLaunchArgument("depth", default_value="10"),
        DeclareLaunchArgument("discovery_timeout", default_value="30"),
    ]
    cli = [
        "--mode",
        "stream",
        "--role",
        LaunchConfiguration("role"),
        "--payload-size",
        LaunchConfiguration("payload_size"),
        "--rate-hz",
        LaunchConfiguration("rate_hz"),
        "--duration",
        LaunchConfiguration("duration"),
        "--warmup",
        LaunchConfiguration("warmup"),
        "--topic",
        LaunchConfiguration("topic"),
        "--output-dir",
        LaunchConfiguration("output_dir"),
        "--reliability",
        LaunchConfiguration("reliability"),
        "--depth",
        LaunchConfiguration("depth"),
        "--discovery-timeout",
        LaunchConfiguration("discovery_timeout"),
    ]
    return LaunchDescription(
        [
            *args,
            Node(package="ros2_netbench", executable="run_benchmark", output="screen", arguments=cli),
        ]
    )
