"""Configure the thesis_tracker ROS 2 Python package."""
from setuptools import find_packages, setup

package_name = 'thesis_tracker'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='francisco',
    maintainer_email='francisco.carreira.tavares@gmail.com',
    description='Multi-backend ROS 2 person tracker for the thesis perception pipeline',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'tracker_node = thesis_tracker.nodes.tracker_node:main',
        ],
    },
)
