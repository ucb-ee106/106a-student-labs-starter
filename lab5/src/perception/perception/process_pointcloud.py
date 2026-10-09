import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from sensor_msgs.msg import PointCloud2
from geometry_msgs.msg import PointStamped
from std_msgs.msg import Float32
import numpy as np
import cv2
import sensor_msgs_py.point_cloud2 as pc2
from tf2_ros import Buffer, TransformListener, TransformException
from rclpy.time import Time
from tf2_sensor_msgs.tf2_sensor_msgs import do_transform_cloud
from rcl_interfaces.msg import SetParametersResult
from visualization_msgs.msg import Marker, MarkerArray

# The table height next to the cube comes from the points in this ring around it
# (just outside the cube, so none of the cube's own points get in)
TABLE_RING_MIN = 0.06  # m
TABLE_RING_MAX = 0.15  # m

class RealSensePCSubscriber(Node):
    def __init__(self):
        super().__init__('realsense_pc_subscriber')
        self.target_frame = self.declare_parameter('target_frame', 'base_link').value
        self.max_y = float(self.declare_parameter('max_y', 0.79).value)

        self.min_z = float(self.declare_parameter('min_z', -0.18).value)
        self.max_z = float(self.declare_parameter('max_z', -0.15).value)

        self.bounds_pub = self.create_publisher(MarkerArray, '/filter_planes', 1)

        # Part 5: the cube is black, so its points should be dark (HSV value at most this)
        self.cube_max_v = int(self.declare_parameter('cube_max_v', 80).value)

        # Part 5: HSV range for the blue tape (in OpenCV, hue goes from 0 to 179).
        # Use `ros2 run perception hsv_tuner` to find good values for your tape.
        self.tape_h_min = int(self.declare_parameter('tape_h_min', 100).value)
        self.tape_h_max = int(self.declare_parameter('tape_h_max', 130).value)
        self.tape_s_min = int(self.declare_parameter('tape_s_min', 120).value)
        self.tape_v_min = int(self.declare_parameter('tape_v_min', 50).value)
        self.tape_min_points = int(self.declare_parameter('tape_min_points', 30).value)
        self.add_on_set_parameters_callback(self._on_parameter_update)

        

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Subscribers
        self.pc_sub = self.create_subscription(
            PointCloud2,
            '/camera/camera/depth/color/points',
            self.pointcloud_callback,
            10
        )

        # Publishers
        self.cube_pose_pub = self.create_publisher(PointStamped, '/cube_pose', 1)
        self.cube_height_pub = self.create_publisher(Float32, '/cube_height', 1)
        self.filtered_points_pub = self.create_publisher(PointCloud2, '/filtered_points', 1)
        self.tape_pose_pub = self.create_publisher(PointStamped, '/tape_pose', 1)
        self.tape_points_pub = self.create_publisher(PointCloud2, '/tape_points', 1)

        self.get_logger().info("Subscribed to PointCloud2 topic and marker publisher ready")

    def pointcloud_callback(self, msg: PointCloud2):

        # Transform the pointcloud from its original frame to base_link
        # Lookup Transform and use library function to transform cloud

        # Filter points between z coords between min_z and max_z and max_y
        # Call the numpy array filtered_points

        source_frame = _______ # TODO: Fill in the source frame based on what you implemented in your static TF broadcaster 
        try:
            tf = self.tf_buffer.lookup_transform(_______, _______, Time()) # TODO: the entire tf lookup params should be filled in
        except TransformException as ex:
            self.get_logger().warn(f'Could not transform {source_frame} to {self.target_frame}: {ex}')
            return

        transformed_cloud = do_transform_cloud(_______, _______) # TODO: look what do_transform_cloud takes in and outputs


        self.publish_filter_planes(transformed_cloud.header)
        
        raw_points = pc2.read_points(
            transformed_cloud,
            field_names=('x', 'y', 'z'),
            skip_nans=True,
        )

        points_base = np.column_stack(
                (raw_points['x'], raw_points['y'], raw_points['z'])
            ).astype(np.float32, copy=False)

        # Part 5: HSV color of each point, in the same order as points_base.
        # This stays None until you do point_colors_hsv, so the parts before still work.
        hsv = self.point_colors_hsv(msg)
        if hsv is not None and len(hsv) != len(points_base):
            self.get_logger().warn('Colors and points don\'t line up, skipping the color filters')
            hsv = None
        if hsv is not None:
            self.find_tape(points_base, hsv, transformed_cloud.header)

        # TODO: Create masks based on the specified min, max y and z parameters above in order to filter points
        # TODO (Part 5): the cube is black, so once you have hsv, also only keep points with V <= self.cube_max_v
        filtered_points = _______

        if filtered_points.size == 0:
            self.get_logger().warn(
                f'No points after filters: z in [{self.min_z:.3f}, {self.max_z:.3f}] m, y <= {self.max_y:.3f} m'
            )
            return

        filtered_cloud = pc2.create_cloud_xyz32(
            transformed_cloud.header,
            filtered_points.tolist(),
        )
        self.filtered_points_pub.publish(filtered_cloud)

        # TODO: Compute cube position in base_link frame using filtered_points.
        cube_x = _______
        cube_y = _______

        # TODO: Estimate how tall the cube is. For the top of the cube, use one of the
        # highest filtered points (a high percentile is less noisy than the max). For the
        # table, use the points (from points_base) that are between TABLE_RING_MIN and
        # TABLE_RING_MAX away from the cube's center in x and y.
        cube_top = _______
        table_z = _______

        cube_height = cube_top - table_z
        cube_z = table_z + cube_height / 2  # middle of the cube
        if cube_top > self.max_z - 0.005:
            # the top of the cube got cut off by max_z, so the cube looks shorter than it is
            self.get_logger().warn(f'Top of the cube is at max_z ({self.max_z:.3f}), raise max_z '
                                   'so the whole cube gets through the filter', throttle_duration_sec=2.0)
        self.cube_height_pub.publish(Float32(data=cube_height))

        # TODO: Publish the cube pose message with the cube position information
        cube_pose = _______

        self.cube_pose_pub.publish(cube_pose)

    def point_colors_hsv(self, msg):
        # The RealSense packs each point's color into one float field called 'rgb'.
        # Returns an (N, 3) uint8 array with H, S, V for each point, in the same order
        # as points_base (only the points with a valid x, y, z are kept, like skip_nans).
        if 'rgb' not in [f.name for f in msg.fields]:
            return None
        pts = pc2.read_points(msg, field_names=('x', 'y', 'z', 'rgb'), skip_nans=False)
        valid = ~(np.isnan(pts['x']) | np.isnan(pts['y']) | np.isnan(pts['z']))
        packed = np.ascontiguousarray(pts['rgb'][valid], dtype=np.float32).view(np.uint32)
        rgb = np.stack([(packed >> 16) & 255, (packed >> 8) & 255, packed & 255], axis=1).astype(np.uint8)

        # TODO (Part 5): convert rgb to HSV with cv2.cvtColor. cvtColor works on images,
        # so reshape to (N, 1, 3) first and back to (N, 3) after. Careful, these colors
        # are in RGB order, not the BGR order OpenCV usually uses.
        hsv = None  # replace this
        return hsv

    def find_tape(self, points_base, hsv, header):
        # TODO (Part 5): keep the points whose color is in the tape's HSV range
        # (tape_h_min <= H <= tape_h_max, S >= tape_s_min, V >= tape_v_min).
        # The tape is on the table, so also drop anything above max_z or past max_y.
        tape_points = _______

        if len(tape_points) < self.tape_min_points:
            return

        self.tape_points_pub.publish(pc2.create_cloud_xyz32(header, tape_points.tolist()))

        # TODO (Part 5): publish the centroid of the tape points on /tape_pose
        # (a PointStamped in base_link, don't forget the header)
        tape_pose = _______
        self.tape_pose_pub.publish(tape_pose)

    def publish_filter_planes(self, header):
        marker_array = MarkerArray()

        def create_plane(marker_id, x, y, z, scale_x, scale_y, scale_z, r, g, b):
            m = Marker()
            m.header = header
            m.ns = "filter_bounds"
            m.id = marker_id
            m.type = Marker.CUBE
            m.action = Marker.ADD
           
            m.pose.position.x = float(x)
            m.pose.position.y = float(y)
            m.pose.position.z = float(z)
            m.pose.orientation.w = 1.0
            
            m.scale.x = float(scale_x)
            m.scale.y = float(scale_y)
            m.scale.z = float(scale_z)
            
            m.color.r = float(r)
            m.color.g = float(g)
            m.color.b = float(b)
            m.color.a = 0.4
            
            return m

        
        span = 2.0
        thickness = 0.002

        # minz
        marker_array.markers.append(
            create_plane(0, 0.0, 0.0, self.min_z, span, span, thickness, 1.0, 0.0, 0.0))
        
        # maxz
        marker_array.markers.append(
            create_plane(1, 0.0, 0.0, self.max_z, span, span, thickness, 0.0, 1.0, 0.0))
        
        # maxy
        marker_array.markers.append(
            create_plane(2, 0.0, self.max_y, 0.0, span, thickness, span, 0.0, 0.0, 1.0))

        self.bounds_pub.publish(marker_array)


    def _on_parameter_update(self, params):
        new_min_z = self.min_z
        new_max_z = self.max_z
        new_max_y = self.max_y

        for param in params:
            if param.name == 'min_z' and param.type_ == Parameter.Type.DOUBLE:
                new_min_z = float(param.value)
            elif param.name == 'max_z' and param.type_ == Parameter.Type.DOUBLE:
                new_max_z = float(param.value)
            elif param.name == 'max_y' and param.type_ == Parameter.Type.DOUBLE:
                new_max_y = float(param.value)
            elif param.name in ('cube_max_v', 'tape_h_min', 'tape_h_max', 'tape_s_min',
                                'tape_v_min', 'tape_min_points'):
                setattr(self, param.name, int(param.value))

        if new_min_z > new_max_z:
            return SetParametersResult(
                successful=False,
                reason='min_z must be <= max_z',
            )

        self.min_z = new_min_z
        self.max_z = new_max_z
        self.max_y = new_max_y
        return SetParametersResult(successful=True)


def main(args=None):
    rclpy.init(args=args)
    node = RealSensePCSubscriber()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
