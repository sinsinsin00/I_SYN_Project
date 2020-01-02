#!/usr/bin/env python

from __future__ import print_function
import rospy, os, time, sys, termios, select, atexit, tty, math
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import Empty, Bool
from ftplib import FTP
import tempfile
from tf.transformations import euler_from_quaternion    # quaternion_from_euler
from math import pow, atan, atan2, sqrt, pi

print("START <Bebop_autonomous_flight_move_control>\n")

VELOCITY_TOPIC = 'bebop/cmd_vel'
TAKEOFF_TOPIC = 'bebop/takeoff'
LAND_TOPIC = 'bebop/land'
ODOMETRY_TOPIC = 'orb_slam2_mono/odom'

HALF_PI = pi / 2.0
DOUBLE_PI = pi * 2.0
ONE_RAD = 0.017444
HALF_RAD = 0.008722

class Bebop:

#	Initialization function definition.
    def __init__(self):
        rospy.init_node('bebop_move', anonymous=True)

        self.vel_pub = rospy.Publisher(VELOCITY_TOPIC, Twist, queue_size = 5)
        self.takeoff_pub = rospy.Publisher(TAKEOFF_TOPIC, Empty, queue_size = 1)
        self.land_pub = rospy.Publisher(LAND_TOPIC, Empty, queue_size = 1)
        self.odom_sub  = rospy.Subscriber(ODOMETRY_TOPIC, Odometry, self.cb_func)

        self.empty_msg = Empty()
        self.twist_msg = Twist()

        #self.end_poseX    = self.goal_poseX + 0.1
        #self.end_poseY    = self.goal_poseY + 0.1

        #self.angle       = 0
        self.goal_angle  = 0
        #self.q_angle     = 0
        #self.print_count = 0
        
        self.goal_points = 0
        
        self.bebop_poseX  = 0
        self.bebop_poseY  = 0
        
        self.goal_pointsX   = []
        self.goal_pointsY   = []
        self.goal_poseX   = 0
        self.goal_poseY   = 0
        
        self.bebop_angle = 0
        self.atan_angle = 0
        
        self.rotate_direction = 0       # -1 : CCW, 0 : normal, 1 : CW

        self.bebop_normal_speed = 0.1
        
        
    def set_goal_coordinate(self):
        
        print("\n<Enter the goal coordinates>")
        self.goal_poseX = input("The value of the goal x: ")
        self.goal_poseY = input("The value of the goal y: ")
        
    def set_goal_coordinates(self):
        
        self.goal_points = input("Number of navigation points : ")
        
        for i in range(0, self.goal_points):
            print("\n<Enter %d goal coordinates>"%(i + 1))
            self.goal_pointsX.append(input("The value of the goal x: "))
            self.goal_pointsY.append(input("The value of the goal y: "))
            
        for i in range(0, len(self.goal_pointsX)):
            print('%s, %s, %s'%(self.goal_pointsX, self.goal_pointsY, type(self.goal_pointsX[i])))
            
    def set_navi_coordinates(self):
        for i in range(len(self.goal_pointsX)-2, -1, -1):
            self.goal_pointsX.append(self.goal_pointsX[i])
            self.goal_pointsY.append(self.goal_pointsY[i])
            
        for i in range(0, len(self.goal_pointsX)):
            print('%s, %s, %s'%(self.goal_pointsX, self.goal_pointsY, type(self.goal_pointsX[i])))
            
    def navigate_to_coordinates(self):
        self.goal_pointsX.append(self.bebop_poseX)
        self.goal_pointsY.append(self.bebop_poseY)
        
        for i in range(0, len(self.goal_pointsX)):
            self.goal_poseX = self.goal_pointsX[i]
            self.goal_poseY = self.goal_pointsY[i]
            
            #print('%s, %s, %s'%(self.goal_pointsX, self.goal_pointsY, type(self.goal_pointsX[i])))
            b.angle_to_goal()
            b.rotate()
            b.move()
            
    def angle_to_goal(self):  # focused on amcl angle
            
        self.goal_angle = -atan2(self.goal_poseX - self.bebop_poseX , self.goal_poseY - self.bebop_poseY)
        #print('raw atan angle : %s'%self.goal_angle)
        
        if not self.goal_angle > HALF_PI:
            self.goal_angle += HALF_PI
        else:
            self.goal_angle -= HALF_PI + pi
            
        if self.goal_angle < 0:
            self.goal_angle += DOUBLE_PI
            
        #print('calculate atan angle : %s'%self.goal_angle)
        '''
        self.goal_angle = -atan2(self.goal_poseX - self.bebop_amcl_poseX , self.goal_poseY - self.bebop_amcl_poseY)
        
        self.goal_angle = 0 - self.goal_angle
        self.goal_angle -= HALF_PI
        
        
        if self.goal_angle <= (-pi):
            self.goal_angle += DOUBLE_PI
        '''
        
        diff_angle = self.goal_angle - self.bebop_angle
        
        #if diff_angle < 0:
        #    diff_angle += DOUBLE_PI
        #print('not abs diff %s'%diff_angle)
        
        diff_angle = abs(diff_angle)
        
        #print('abs diff %s'%diff_angle)
            
        '''if diff_angle >= pi:        # CCW
            self.rotate_direction = 1
        elif diff_angle < pi:       # CW
            self.rotate_direction = -1'''
        
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

        print('[%s] Goal Angle : %s  Bebop : %s  Diff : %s'%(self.rotate_direction, self.goal_angle, self.bebop_angle, diff_angle))
            
	def send_zero_velocity(self):
		self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
		self.twist_msg.angular.x = self.twist_msg.angular.y = self.twist_msg.angular.z = 0
		self.vel_pub.publish(self.twist_msg)

    def rotate(self):
        print("\nKobuki start rotate!!")
    
        if self.rotate_direction == -1:     # Twist Msg = CW : -  CCW : +
            self.twist_msg.angular.z = 0.2     # bebop speed : 0.1, kobuki : 0.33
        elif self.rotate_direction == 1:
            self.twist_msg.angular.z = -0.2    # bebop speed : 0.1, kobuki : 0.33
            
        self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
        self.twist_msg.angular.x = self.twist_msg.angular.y = 0
        self.vel_pub.publish(self.twist_msg)
        rospy.sleep(0.2)
        
        while 1:
            if abs(self.goal_angle - self.bebop_angle) < ONE_RAD:
                print("\nKobuki rotated at the correct angle!!")
                break
            self.angle_to_goal()
            print("Goal : %s , Kobuki : %s"%(self.goal_angle, self.bebop_angle))
            self.vel_pub.publish(self.twist_msg)
            rospy.sleep(0.01)
            
        self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
        self.twist_msg.angular.x = self.twist_msg.angular.y = self.twist_msg.angular.z = 0
        self.vel_pub.publish(self.twist_msg)
        self.rotate_direction = 0

#	Forward, Backward control function definition.
    def move(self):

        normal_speed = 0.1

        #self.goal_poseX = goal_x - self.bebop_poseX
        #self.goal_poseY = goal_y - self.bebop_poseY

        print("GOAL X, Y    : %s, %s"%(self.goal_poseX, self.goal_poseY))
        print("ROBOT X, Y   : %s, %s"%(self.bebop_poseX, self.bebop_poseY))
        
        self.twist_msg.linear.x = abs(normal_speed)
        
        print("NORMAL_SPEED     : ", abs(normal_speed))
        print("\nBebop is moving forward!!\n")

        self.twist_msg.linear.y = self.twist_msg.linear.z = 0
        self.twist_msg.angular.x = self.twist_msg.angular.y = self.twist_msg.angular.z = 0
        self.vel_pub.publish(self.twist_msg)
        rospy.sleep(0.1)

        while 1:
            if abs(self.goal_poseX - self.bebop_poseX) < 0.5 and abs(self.goal_poseY - self.bebop_poseY) < 0.5:
                self.twist_msg.linear.x = 0.05
                print("MOVE_SPEED_DOWN  : ", self.twist_msg.linear.x)
            if abs(self.goal_poseX - self.bebop_poseX) < 0.1 and abs(self.goal_poseY - self.bebop_poseY) < 0.1:
                print("\nBebop has reached the target!!")
                break
            
            self.angle_to_goal()
            
            if self.rotate_direction == -1:
                self.twist_msg.angular.z = 0.2
            elif self.rotate_direction == 1:
                self.twist_msg.angular.z = -0.2
                
            if abs(self.goal_angle - self.bebop_angle) < HALF_RAD:
                self.twist_msg.angular.z = 0
            
            print("GOAL X, Y    : %s, %s"%(self.goal_poseX, self.goal_poseY))
            print("ROBOT X, Y   : %s, %s"%(self.bebop_poseX, self.bebop_poseY))
            
            
            self.vel_pub.publish(self.twist_msg)
            rospy.sleep(0.01)

        self.twist_msg.linear.x = self.twist_msg.linear.y = self.twist_msg.linear.z = 0
        self.twist_msg.angular.x = self.twist_msg.angular.y = self.twist_msg.angular.z = 0
        self.vel_pub.publish(self.twist_msg)
        rospy.sleep(1)

#	Takeoff, Landing automation function definition.
    def take_off(self):
        rospy.sleep(1)
        self.takeoff_pub.publish(self.empty_msg)
        print("Take off Bebop!!\n")

    def land(self):
        rospy.sleep(1)
        self.land_pub.publish(self.empty_msg)
        print("\nLands Bebop!!")

#	Callback function definition.
    def cb_func(self, msg):
        self.bebop_poseX = msg.pose.pose.position.x
        self.bebop_poseY = msg.pose.pose.position.y
        
        self.bebop_angle = self.get_euler_angle(msg)
        
        if self.bebop_angle < 0:
            self.bebop_angle = self.bebop_angle + 6.28

        #print(self.bebop_angle)
        
    def get_euler_angle(self, data):
        quaternion = (data.pose.pose.orientation.x, data.pose.pose.orientation.y,
                      data.pose.pose.orientation.z, data.pose.pose.orientation.w)
        euler      = euler_from_quaternion(quaternion)
        roll       = euler[0]
        pitch      = euler[1]
        yaw        = euler[2]
        
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
        print('odom : %s  , amcl : %s  error : %s'%(self.bebop_angle, self.amcl_angle, angle_error))
            
def angle_test(x, y):
    angle = -atan2(x, y)
    print('raw atan angle : %s'%angle)
    
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
    
    print('calculate atan angle : %s\n'%angle)

if __name__ == '__main__':
    try:
        b = Bebop()
        #while not rospy.is_shutdown():
        #    b.cali_odom_amcl()
        #while 1:
        #    pass
        #b.take_off()
        
        b.set_goal_coordinate()
        
        while 1:
            b.angle_to_goal()
        '''b.rotate()
        b.move()
        
        b.set_goal_coordinates()
        b.set_navi_coordinates()
        b.navigate_to_coordinates()'''
        
        #b.land()
        '''rospy.sleep(10)
        b.rotate(180, 1)
        b.move()'''
        #b.rotate()
        #b.land()
        #angle_test(0.7258, -3.464)
        '''angle_test(0, 1)
        angle_test(0.5, 1)
        angle_test(1, 1)
        angle_test(1, 0.5)
        angle_test(1, 0)
        angle_test(1, -0.5)
        angle_test(1, -1)
        angle_test(0.5, -1)
        angle_test(0, -1)
        angle_test(-0.5, -1)
        angle_test(-1, -1)
        angle_test(-1, -0.5)
        angle_test(-1, 0)
        angle_test(-1, 0.5)
        angle_test(-1, 1)
        angle_test(-0.5, 1)'''
        

    except rospy.ROSInterruptException: pass
    
    except KeyboardInterrupt:
        loginfo("Program ends.")
