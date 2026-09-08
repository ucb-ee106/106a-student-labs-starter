from setuptools import find_packages, setup

package_name = 'turtle_patrol'

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
    maintainer='ee106a-tad',
    maintainer_email='stellybean.seo@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'patrol_client = turtle_patrol.patrol_client:main',
            'patrol_server = turtle_patrol.patrol_server:main',
            'patrol_client_sol = turtle_patrol.patrol_client_sol:main',
            'patrol_server_sol = turtle_patrol.patrol_server_sol:main'
        ],
    },
)
