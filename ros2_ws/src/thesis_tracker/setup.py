# Thesis-Code
# Purpose: Configure installation, metadata and executable entrypoints for the
# thesis_tracker ROS 2 Python package.
# Author: Francisco Tavares
# Copyright (c) 2026 Francisco Carreira Tavares
# SPDX-License-Identifier: MIT
#
# Use of this source code is governed by an MIT-style
# license that can be found in the LICENSE file or at
# https://opensource.org/licenses/MIT.

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
    maintainer='Francisco Carreira Tavares',
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
