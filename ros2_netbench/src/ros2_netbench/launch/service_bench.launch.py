from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    args = [
        DeclareLaunchArgument("role", default_value="server"),
        DeclareLaunchArgument("payload_size", default_value="1024"),
        DeclareLaunchArgument("rate_hz", default_value="10"),
        DeclareLaunchArgument("duration", default_value="10"),
        DeclareLaunchArgument("warmup", default_value="2"),
        DeclareLaunchArgument("service", default_value="/netbench/service"),
        DeclareLaunchArgument("output_dir", default_value="results"),
        DeclareLaunchArgument("reliability", default_value="reliable"),
        DeclareLaunchArgument("depth", default_value="10"),
    ]
    cli = [
        "--mode",
        "service",
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
        "--service",
        LaunchConfiguration("service"),
        "--output-dir",
        LaunchConfiguration("output_dir"),
        "--reliability",
        LaunchConfiguration("reliability"),
        "--depth",
        LaunchConfiguration("depth"),
    ]
    return LaunchDescription(
        [
            *args,
            Node(package="ros2_netbench", executable="run_benchmark", output="screen", arguments=cli),
        ]
    )
