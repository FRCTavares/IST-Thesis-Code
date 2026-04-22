from setuptools import find_packages, setup

package_name = 'thesis_inference_client'

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
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'detector_node = thesis_inference_client.inference_client_node:main',
            'inference_client_node = thesis_inference_client.inference_client_node:main',
        ],
    },
)
