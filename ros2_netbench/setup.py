from glob import glob
from setuptools import find_packages, setup


package_name = "ros2_netbench"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("src/ros2_netbench/launch/*.launch.py")),
        (f"share/{package_name}/config", glob("src/ros2_netbench/config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ros2_netbench maintainers",
    maintainer_email="maintainer@example.com",
    description="Python ROS 2 network benchmarking toolkit.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "run_benchmark = ros2_netbench.run_benchmark:main",
            "stream_sender = ros2_netbench.nodes.stream_sender:main",
            "stream_receiver = ros2_netbench.nodes.stream_receiver:main",
            "ping_client = ros2_netbench.nodes.ping_client:main",
            "ping_server = ros2_netbench.nodes.ping_server:main",
            "service_client = ros2_netbench.nodes.service_client:main",
            "service_server = ros2_netbench.nodes.service_server:main",
            "summarize_run = ros2_netbench.analysis.summarize_run:main",
            "compare_runs = ros2_netbench.analysis.compare_runs:main",
        ],
    },
)
