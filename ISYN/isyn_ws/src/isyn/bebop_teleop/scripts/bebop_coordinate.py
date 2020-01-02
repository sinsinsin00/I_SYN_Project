#!/usr/bin/env python

from __future__ import print_function
import rospy, os, time, sys, termios, select, atexit, tty, math
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped, Point
from nav_msgs.msg import Odometry
from std_msgs.msg import Empty, Bool, String, UInt8, Int8
from ftplib import FTP
import tempfile
from tf.transformations import euler_from_quaternion    # quaternion_from_euler
from math import pow, atan, atan2, sqrt, pi

print("START <Bebop_autonomous_flight_move_control>\n")

# Publish topic name
VELOCITY_TOPIC = 'bebop/cmd_vel'
TAKEOFF_TOPIC = 'bebop/takeoff'
LAND_TOPIC = 'bebop/land'

NAVIGATION_LOG_TOPIC = 'isyn/log/navigation'
POINT_REACHED_TOPIC = 'point_reached'
RETURN_ROUTE_TOPIC = 'isyn/navigation/returnRoute'

# Subscribe topic name
ODOMETRY_TOPIC = 'orb_slam2_mono/odom'

WAYPOINT_TOPIC = 'isyn/waypoint'
NAVIGATE_START_TOPIC = 'isyn/navigate/start'
NAVIGATE_STOP_TOPIC = 'isyn/navigate/stop'
NAVIGATE_END_TOPIC = 'isyn/navigate/end'

SCAN_ALL_CLEAR_TOPIC = 'scan_all_clear'

BEBOP_FORWARD_SPEED = 0.05
BEBOP_FORWARD_SLOWDOWN_SPEED = 0.02
BEBOP_SIDEWAY_SPEED = 0.02
BEBOP_TURNING_SPEED = 0.1
BEBOP_TURNING_SLOWDOWN_SPEED = 0.05

'''BEBOP_FORWARD_SPEED = 0.1
BEBOP_FORWARD_SLOWDOWN_SPEED = 0.05
BEBOP_SIDEWAY_SPEED = 0.05
BEBOP_TURNING_SPEED = 0.5
BEBOP_TURNING_SLOWDOWN_SPEED = 0.5'''

HALF_PI = pi / 2.0
DOUBLE_PI = pi * 2.0
ONE_RAD = 0.017444
HALF_RAD = 0.008722


class Bebop:
    def __init__(self):
        rospy.init_node('bebop_move', anonymous=True)

        self.pub_vel = rospy.Publisher(VELOCITY_TOPIC, Twist, queue_size=5)
        self.pub_takeoff = rospy.Publisher(TAKEOFF_TOPIC, Empty, queue_size=1)
        self.pub_land = rospy.Publisher(LAND_TOPIC, Empty, queue_size=1)

        self.pub_navigation_log = rospy.Publisher(NAVIGATION_LOG_TOPIC, String, queue_size=1)
        self.pub_point_reached = rospy.Publisher(POINT_REACHED_TOPIC, Int8, queue_size=1)
        self.pub_return_route = rospy.Publisher(RETURN_ROUTE_TOPIC, Point, queue_size=1)
        self.pub_isyn_navigate_end = rospy.Publisher(NAVIGATE_END_TOPIC, Empty, queue_size=1)

        self.sub_odom = rospy.Subscriber(ODOMETRY_TOPIC, Odometry, self.callbackOdom)
        self.sub_waypoint = rospy.Subscriber(WAYPOINT_TOPIC, Point, self.callbackWaypoint)
        self.sub_navigate_start = rospy.Subscriber(NAVIGATE_START_TOPIC, Empty, self.callbackNavigateStart)
        self.sub_navigate_stop = rospy.Subscriber(NAVIGATE_STOP_TOPIC, Empty, self.callbackNavigateStop)

        self.sub_scan_all_clear = rospy.Subscriber(SCAN_ALL_CLEAR_TOPIC, Int8, self.callbackScanAllClear)

        self.empty_msg = Empty()
        self.twist_msg = Twist()

        # self.end_poseX    = self.goal_pose_x + 0.1
        # self.end_poseY    = self.goal_pose_y + 0.1

        self.bebop_pose_x = 0
        self.bebop_pose_y = 0

        self.waypoint_list_x = []
        self.waypoint_list_y = []
        self.goal_pose_x = 0
        self.goal_pose_y = 0

        self.goal_angle = 0
        self.bebop_angle = 0
        self.diff_angle = 0

        self.rotate_direction = 0       # -1 : CCW, 0 : normal, 1 : CW

        self.navigation_state = False

        self.person_dection_state = False

    # Callback function definition.
    def callbackOdom(self, msg):
        self.bebop_pose_x = msg.pose.pose.position.x
        self.bebop_pose_y = msg.pose.pose.position.y

        self.bebop_angle = self.get_euler_angle(msg)

        if self.bebop_angle < 0:
            self.bebop_angle = self.bebop_angle + 6.28

    def callbackWaypoint(self, msg):
        self.waypoint_list_x.append(msg.x)
        self.waypoint_list_y.append(msg.y)

    def callbackNavigateStart(self, msg):
        if len(self.waypoint_list_x) is not 0:
            self.navigation_state = True
            self.setNaviPoints()
            self.navigateToWaypoint()

        else:
            self.pub_navigation_log.publish('[NAVI] Please set waypoints!!')
            print('[NAVI] Please set waypoints!!')

    def callbackNavigateStop(self, msg):
        self.navigation_state = False
        print('navi stop')

    def callbackScanAllClear(self, msg):
        if msg.data:
            self.person_dection_state = False
        print('opencv_scan Started')

    def setNaviPoints(self):
        for i in range(len(self.waypoint_list_x) - 2, -1, -1):
            self.waypoint_list_x.append(self.waypoint_list_x[i])
            self.waypoint_list_y.append(self.waypoint_list_y[i])
            self.pub_return_route.publish(self.waypoint_list_x[i], self.waypoint_list_y[i], 0)

        for i in range(0, len(self.waypoint_list_x)):
            print('%s, %s, %s' % (self.waypoint_list_x, self.waypoint_list_y, type(self.waypoint_list_x[i])))

    def navigateToWaypoint(self):
        self.waypoint_list_x.append(self.bebop_pose_x)
        self.waypoint_list_y.append(self.bebop_pose_y)
        self.pub_return_route.publish(self.bebop_pose_x, self.bebop_pose_y, 0)

        for i in range(0, len(self.waypoint_list_x)):
            self.goal_pose_x = self.waypoint_list_x[i]
            self.goal_pose_y = self.waypoint_list_y[i]

            # print('%s, %s, %s'%(self.waypoint_list_x, self.waypoint_list_y, type(self.waypoint_list_x[i])))
            b.angleToGoal()
            b.rotate()
            rospy.sleep(0.5)
            b.move()

            if i <= (len(self.waypoint_list_x) - 1) / 2:
                self.person_dection_state = True
                self.pub_point_reached.publish(1)
                while self.person_dection_state:
                    pass

            if not self.navigation_state:
                break

        for i in range(0, len(self.waypoint_list_x)):
            del self.waypoint_list_x[0]

    def angleToGoal(self):  # focused on amcl angle
        self.goal_angle = -atan2(self.goal_pose_x - self.bebop_pose_x, self.goal_pose_y - self.bebop_pose_y)

        if not self.goal_angle > HALF_PI:
            self.goal_angle += HALF_PI
        else:
            self.goal_angle -= HALF_PI + pi

        if self.goal_angle < 0:
            self.goal_angle += DOUBLE_PI

        print('Goal Angle : %s' % (self.goal_angle))
        print('Bebop Angle : %s' % (self.bebop_angle))

        diff_angle = abs(self.goal_angle - self.bebop_angle)

        # -1 : CCW, 0 : normal, 1 : CW
        # between goal angle and current angle make between angle. the between angle's smaller absolute value is direction of turn !!
        cw_judge1 = self.goal_angle - self.bebop_angle
        cw_judge2 = self.bebop_angle - self.goal_angle

        if cw_judge1 < 0:  # if between angle is under the zero value, plus 6.28(this means one cycle of bebop)
            cw_judge1 = cw_judge1 + 6.28

        if cw_judge2 < 0:
            cw_judge2 = cw_judge2 + 6.28

        if cw_judge1 < cw_judge2:  # if goal angle's between value is smaller make turn clock wise
            self.rotate_direction = -1       # CCW
        else:
            self.rotate_direction = 1      # CW

        print('rotate direction = %s' % self.rotate_direction)

    def sendZeroVelocity(self):
        self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
        self.twist_msg.angular.x = self.twist_msg.angular.y = self.twist_msg.angular.z = 0
        self.pub_vel.publish(self.twist_msg)

    '''def holdPosition(self):
        if not self.navigation_state:
            
            self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
            self.twist_msg.angular.x = self.twist_msg.angular.y = 0
            self.pub_vel.publish(self.twist_msg)
            rospy.sleep(0.2)

            while self.navigation_state:
                if abs(self.goal_angle - self.bebop_angle) < ONE_RAD:
                    print("\nBebop rotated at the correct angle!!")
                    break
                self.angleToGoal()
                print("Goal : %s , Bebop : %s" % (self.goal_angle, self.bebop_angle))
                self.pub_vel.publish(self.twist_msg)
                rospy.sleep(0.01)

        self.sendZeroVelocity()
        self.rotate_direction = 0'''

    def rotate(self):
        if self.navigation_state:
            print("\nBebop Turning Start!!")

            if self.rotate_direction == -1:     # Bebop Twist Msg = CW : -  CCW : +
                self.twist_msg.angular.z = BEBOP_TURNING_SPEED
            elif self.rotate_direction == 1:
                self.twist_msg.angular.z = -BEBOP_TURNING_SPEED

            self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
            self.twist_msg.angular.x = self.twist_msg.angular.y = 0
            self.pub_vel.publish(self.twist_msg)
            rospy.sleep(0.2)

            while self.navigation_state:
                if abs(self.goal_angle - self.bebop_angle) < ONE_RAD:
                    print("\nBebop rotated at the correct angle!!")
                    break
                self.angleToGoal()
                print("Goal : %s , Bebop : %s" % (self.goal_angle, self.bebop_angle))
                self.pub_vel.publish(self.twist_msg)
                rospy.sleep(0.01)

        self.sendZeroVelocity()
        self.rotate_direction = 0

    # Forward, Backward control function definition.
    def move(self):
        if self.navigation_state:
            print("GOAL X, Y    : %s, %s" % (self.goal_pose_x, self.goal_pose_y))
            print("ROBOT X, Y   : %s, %s" % (self.bebop_pose_x, self.bebop_pose_y))

            self.twist_msg.linear.x = abs(BEBOP_FORWARD_SPEED)

            print("NORMAL_SPEED     : ", abs(BEBOP_FORWARD_SPEED))
            print("\nBebop is moving forward!!\n")

            while self.navigation_state:
                if abs(self.goal_pose_x - self.bebop_pose_x) < 0.5 and abs(self.goal_pose_y - self.bebop_pose_y) < 0.5:
                    self.twist_msg.linear.x = BEBOP_FORWARD_SLOWDOWN_SPEED
                    print("MOVE_SPEED_DOWN  : ", self.twist_msg.linear.x)
                if abs(self.goal_pose_x - self.bebop_pose_x) < 0.1 and abs(self.goal_pose_y - self.bebop_pose_y) < 0.1:
                    print("\nBebop has reached the target!!")
                    break

                self.angleToGoal()

                if self.rotate_direction == -1:
                    self.twist_msg.linear.y = BEBOP_SIDEWAY_SPEED
                    self.twist_msg.angular.z = BEBOP_TURNING_SLOWDOWN_SPEED
                elif self.rotate_direction == 1:
                    self.twist_msg.linear.y = -BEBOP_SIDEWAY_SPEED
                    self.twist_msg.angular.z = -BEBOP_TURNING_SLOWDOWN_SPEED

                if abs(self.goal_angle - self.bebop_angle) < ONE_RAD:
                    self.twist_msg.linear.y = 0
                    self.twist_msg.angular.z = 0

                print("GOAL X, Y    : %s, %s" % (self.goal_pose_x, self.goal_pose_y))
                print("ROBOT X, Y   : %s, %s" % (self.bebop_pose_x, self.bebop_pose_y))

                self.pub_vel.publish(self.twist_msg)
                rospy.sleep(0.01)

        self.sendZeroVelocity()
        rospy.sleep(1)

# Takeoff, Landing automation function definition.
    def take_off(self):
        rospy.sleep(1)
        self.pub_takeoff.publish(self.empty_msg)
        print("Take off Bebop!!\n")

    def land(self):
        rospy.sleep(1)
        self.pub_land.publish(self.empty_msg)
        print("\nLands Bebop!!")

    def get_euler_angle(self, data):
        quaternion = (data.pose.pose.orientation.x, data.pose.pose.orientation.y,
                      data.pose.pose.orientation.z, data.pose.pose.orientation.w)
        euler = euler_from_quaternion(quaternion)
        roll = euler[0]
        pitch = euler[1]
        yaw = euler[2]

        return yaw

    def rotate_speed_down(self, direction_of_rotation, rotate_slow_speed):
        if direction_of_rotation == 1:
            self.twist_msg.angular.z = -abs(rotate_slow_speed)
        elif direction_of_rotation == -1:
            self.twist_msg.angular.z = abs(rotate_slow_speed)

    def cali_odom_amcl(self):
        angle_error = self.bebop_angle - self.amcl_angle
        if angle_error > pi:
            angle_error = DOUBLE_PI - angle_error
        print('odom : %s  , amcl : %s  error : %s' % (self.bebop_angle, self.amcl_angle, angle_error))


def angle_test(x, y):
    angle = -atan2(x, y)
    print('raw atan angle : %s' % angle)

    if not angle > HALF_PI:
        angle += HALF_PI
    else:
        angle -= HALF_PI + pi
    '''
    if angle > pi:
        angle += DOUBLE_PI

    angle = 0 - angle

    if angle < 0:
        angle += DOUBLE_PI

    if not angle == 0:
        angle = DOUBLE_PI - angle'''

    print('calculate atan angle : %s\n' % angle)


if __name__ == '__main__':
    try:
        b = Bebop()
        rospy.spin()

    except rospy.ROSInterruptException:
        pass

    except KeyboardInterrupt:
        loginfo("Program ends.")
