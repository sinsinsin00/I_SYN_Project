#!/usr/bin/env python
# -*- coding: utf-8 -*-

import threading
import rospy, os, time, sys, termios, select

from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from std_msgs.msg import Empty, UInt8, Int8, Int32, String
from bebop_msgs.msg import Ardrone3PilotingStateAltitudeChanged
if os.name == 'nt':
  import msvcrt
else:
  import tty, termios


class Bebop:
    def __init__(self):
        rospy.init_node('bebop_move', anonymous=True)

        # bebop info
        # sub
        self.bebop_odom_sub = rospy.Subscriber('/orb_slam2_mono/odom', Odometry, self.callback_bebop_odom, queue_size=5)
        self.bebop_altitude_sub = rospy.Subscriber('/bebop/states/ardrone3/PilotingState/AltitudeChanged',Ardrone3PilotingStateAltitudeChanged,self.
                                                   callback_bebop_takeoff_stat,queue_size = 1)

        # bebop control
        # pub
        self.bebop_pub_land = rospy.Publisher('/bebop/land', Empty, queue_size=1)
        self.bebop_pub_takeoff = rospy.Publisher('/bebop/takeoff', Empty, queue_size=1)
        self.bebop_control_pub = rospy.Publisher('/bebop/cmd_vel', Twist, queue_size=1)

        # with isyn
        # sub
        self.isyn_person_to_drone_Alignment_sub = rospy.Subscriber('/person_to_drone_Alignment', String, self.callback_person_to_drone_Alignment)
        self.isyn_status_sub = rospy.Subscriber('/status_isyn', Int32,self.callback_isyn_status, queue_size=1)
        self.isyn_found_object_sub = rospy.Subscriber('/found_person', Int8, self.callback_found_person)
        self.isyn_save_image_clear_sub = rospy.Subscriber('/isyn_save_image_clear',Int8,self.callback_isyn_save_image_clear,queue_size=1)
        # pub
        self.bebop_mode_pub = rospy.Publisher('/bebop_mode', UInt8,queue_size=1)
        self.bebop_status_pub = rospy.Publisher('bebop_status',Int32,queue_size = 1)
        self.bebop_req_save_image_pub = rospy.Publisher('/bebop_req_save_image',Int8,queue_size = 1)


        # with bebop mode_1
        # sub
        self.point_move_all_clear_sub = rospy.Subscriber('/point_reached',Int8,self.callback_point_move_all_clear,queue_size=1)
        # pub
        self.scan_all_clear_pub = rospy.Publisher('/scan_all_clear',Int8, queue_size=1)

        # msg init
        self.empty_msg = Empty()
        self.msg = Twist()

        # init bebop
        self.curr_angular_speed = 0.1
        self.curr_isyn_status_msg = 0
        self.curr_Found_person = 0
        self.curr_Alignment = 0
        self.thresh_Alignment_max = 50
        self.thresh_Alignment_min = -50
        self.curr_bebop_takeoff_stat = 0
        self.curr_point_move_all_clear = 0
        self.curr_bebop_odom_z = 0

        #init flag
        self.set_Alignment_flag = 0
        self.error_check_num = 0
        self.point_local_scan_clear = 0
        self.scan_delay = 0

        # pub msgs
        self.bebop_mode_msg = 0
        self.curr_bebop_status_msg = 0
        print("init clear")

    def take_off(self):
        rospy.sleep(1)
        self.bebop_pub_takeoff.publish(self.empty_msg)
        print("bebop_will_take_off")

    def land(self):
        rospy.sleep(1)
        self.bebop_pub_land.publish(self.empty_msg)
        print("bebop_is_landing")

    def callback_point_move_all_clear(self,point_move_all_clear_data):
        self.curr_point_move_all_clear = point_move_all_clear_data.data
        print('curr_point_move_all_clear : %d ' % self.curr_point_move_all_clear)

    def callback_bebop_odom(self,bebop_odom_data):
        self.curr_bebop_odom_z = bebop_odom_data.pose.pose.orientation.z
        self.curr_bebop_odom_z = self.curr_bebop_odom_z * 100
        self.curr_bebop_odom_z = int(self.curr_bebop_odom_z)
        
    def callback_person_to_drone_Alignment(self,Alignment_data):
        self.curr_Alignment = Alignment_data.data
        if self.curr_Alignment != 0 and self.curr_Alignment != 'not data':
            self.split_Alignment_data = self.curr_Alignment[1:-1]
            self.split_Alignment_data = map(int,self.split_Alignment_data.split(','))
        elif self.curr_Alignment == 'not data':
            self.split_Alignment_data = [-1]

    def callback_found_person(self,found_person_data):
        self.curr_found_person = found_person_data.data

    def callback_bebop_takeoff_stat(self,bebop_takeoff_stat_data):
        self.curr_bebop_takeoff_stat = bebop_takeoff_stat_data.altitude

    def callback_isyn_status(self,isyn_status_data):
        self.curr_isyn_status_msg = isyn_status_data.data

    def callback_isyn_save_image_clear(self,isyn_save_image_clear):
        self.curr_isyn_save_image_clear = isyn_save_image_clear.data

    def bebop_change_stat(self):

        #send msg of bebop status
        if self.bebop_mode_msg == 1:
            self.curr_bebop_status_msg = 0
            

        # if self.curr_bebop_takeoff_stat == 0 :
        #     self.curr_bebop_status_msg = 0
        #     self.bebop_mode_msg = 0

        if self.curr_point_move_all_clear == 1:
            self.bebop_mode_msg = 2
            self.curr_bebop_status_msg = 1
            self.point_local_scan_clear = 0
            self.msg.angular.x = self.msg.angular.y = self.msg.angular.z = 0
            self.bebop_control_pub.publish(self.msg)

        if self.bebop_mode_msg == 2 and self.curr_isyn_status_msg == 1:
            self.curr_bebop_status_msg = 2

        if self.bebop_mode_msg == 2 and self.curr_isyn_status_msg == 2:
            self.curr_bebop_status_msg = 3


    def set_detect_person_center(self):
        try:
            if self.split_Alignment_data[0] == -1:
                print('not split Alignment data')
            elif self.curr_bebop_status_msg == 3 and self.split_Alignment_data > 0:
                for i in range(0,len(self.split_Alignment_data),1):
                    while (1):
                        if (self.split_Alignment_data[i] < self.thresh_Alignment_max and self.split_Alignment_data[i] > self.thresh_Alignment_min):
                            self.msg.angular.x = self.msg.angular.y = self.msg.angular.z = 0
                            if self.curr_isyn_save_image_clear == 1:
                                self.bebop_req_save_image_pub.publish(0)
                                rospy.sleep(3)
                                print('clear detect person center')
                                break
                            if self.curr_isyn_save_image_clear == 0:
                                self.bebop_req_save_image_pub.publish(1)

                        if (self.split_Alignment_data[i] < self.thresh_Alignment_max):
                            self.msg.angular.z = self.curr_angular_speed
                            self.msg.angular.x = self.msg.angular.y = 0

                        if (self.split_Alignment_data[i] > self.thresh_Alignment_min):
                            self.msg.angular.z = - self.curr_angular_speed
                            self.msg.angular.x = self.msg.angular.y = 0

                        self.bebop_control_pub.publish(self.msg)
                        rospy.sleep(0.1)
                self.point_local_scan_clear = 1

        except AttributeError:
            self.error_check_num = self.error_check_num + 1
            if self.error_check_num >= 5:
                print("wait Alignment data")
                self.error_check_num = 0

        except IndexError as e:
            self.point_local_scan_clear = 1
            if self.curr_isyn_save_image_clear == 1:
                self.bebop_req_save_image_pub.publish(0)
            print(e)


    def init_location(self):
        while (self.curr_bebop_odom_z > 0):
            self.msg.angular.z = self.curr_angular_speed
            self.bebop_control_pub.publish(self.msg)

        while (self.curr_bebop_odom_z < 0):
            self.msg.angular.z = self.curr_angular_speed
            self.bebop_control_pub.publish(self.msg)

        self.msg.angular.x = self.msg.angular.y = self.msg.angular.z = 0
        self.bebop_control_pub.publish(self.msg)

    # thread func
    def bebop_move(self):
        while(1):
            time.sleep(0.045)
            #change_bebop_status
            self.bebop_change_stat()

            # send msg of isyn status
            self.bebop_mode_pub.publish(self.bebop_mode_msg)
            self.bebop_status_pub.publish(self.curr_bebop_status_msg)

            if self.curr_bebop_status_msg == 3 and self.point_local_scan_clear == 0:
                limit_odom_z = self.curr_bebop_odom_z
                print("limit_odom_z : %d" % limit_odom_z)
                while(1) :
                    self.msg.angular.z = self.curr_angular_speed
                    self.bebop_control_pub.publish(self.msg)
                    print('point_local_scal_clear : %d' %self.point_local_scan_clear)
                    print('self.scan_delay : %d '%self.scan_delay)
                    if self.curr_found_person > 0:
                        self.scan_delay += 1
                        if self.scan_delay >= 20 and self.point_local_scan_clear == 0:
                            print("start detect person center")
                            self.set_detect_person_center()
                            self.scan_delay = 0
                    if self.curr_bebop_odom_z == limit_odom_z and self.point_local_scan_clear == 1:
                        self.bebop_mode_msg = 1
                        self.curr_point_move_all_clear = 0
                        self.point_local_scan_clear = 0
                        self.scan_delay = 0
                        self.scan_all_clear_pub.publish(1)
                        break
                    rospy.sleep(0.045)

                self.msg.angular.x = self.msg.angular.y = self.msg.angular.z = 0
                self.bebop_control_pub.publish(self.msg)


def getKey():
    if os.name == 'nt':
      return msvcrt.getch()
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def key_control():
    while (1):
        try:
            key = getKey()
            if key == 't':
                print("thread take off call")
                bebop.take_off()
            elif key == 'q':
                print("thread landing call")
                bebop.land()
                break
            elif key == 'a':
                print('change bebop stop detecting mode num 0  ')
                bebop.bebop_mode_msg = 0
            elif key == 's':
                print('change bebop detecting mode num 2')
                bebop.bebop_mode_msg = 2
                bebop.point_local_scan_clear = 0
            elif key == 'd':
                print('change bebop detecting mode num 3')
                bebop.init_location()

            time.sleep(0.1)
        except KeyboardInterrupt as e:
            print(e)
            break

if __name__ == "__main__":
    try:
        if os.name != 'nt':
            settings = termios.tcgetattr(sys.stdin)
        bebop = Bebop()
        # key_thread = threading.Thread(target=key_control)
        # key_thread.daemon = True
        # key_thread.start()
        bebop_move_thread = threading.Thread(target=bebop.bebop_move)
        bebop_move_thread.daemon = True
        bebop_move_thread.start()
        rospy.spin()

    except KeyboardInterrupt :
        print("main program exit")

    except rospy.ROSInterruptException as e:
        print("ROS program exit")