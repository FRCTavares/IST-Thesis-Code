from setuptools import find_packages, setup
from glob import glob
import os

package_name = 'thesis_bringup'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/thesis_bringup"]),
        ("share/thesis_bringup", ["package.xml"]),
        (os.path.join("share", "thesis_bringup", "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", "thesis_bringup", "config"), glob("config/*.yaml")),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='francisco',
    maintainer_email='francisco.carreira.tavares@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        "console_scripts": [
            "detections_occluder_node = thesis_bringup.nodes.detections_occluder_node:main",
            "detections_ambiguity_node = thesis_bringup.nodes.detections_ambiguity_node:main",
            "camera_init_node = thesis_bringup.nodes.camera_init_node:main",
        ],
    },
)
