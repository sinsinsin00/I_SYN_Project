#!/usr/bin/env python

import rospy, os, time, sys, termios, select, atexit, tty, math
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Empty, Bool, Int8
from PyQt4 import QtGui, uic
from bebop_msgs.msg import CommonCommonStateBatteryStateChanged

class MyWindow(QtGui.QMainWindow):
	def __init__(self):
		super(MyWindow, self).__init__()
		uic.loadUi('test3.ui', self)
		self.take_off_button.clicked.connect(self.take_off_push)
		self.land_button.clicked.connect(self.land_push)
		self.show()
		self.battery_percentage = 0
		self.empty_msg = Empty()

		self.battery_bar.setValue(self.battery_percentage)
		rospy.init_node('test_take_off', anonymous=True)
		self.pub_takeoff = rospy.Publisher('bebop/takeoff', Empty, queue_size=1)		
		self.pub_land = rospy.Publisher('bebop/land', Empty, queue_size=1)
	
#		self.sub_odom = rospy.Subscriber('/bebop/odom', Odometry, self.get_odom)
		self.sub_battery = rospy.Subscriber('/bebop/states/common/CommonState/BatteryStateChanged/', CommonCommonStateBatteryStateChanged, self.get_battery)
		
		
	def take_off_push(self):
		self.pub_takeoff.publish(self.empty_msg)
		self.main_textBrowser.setText("Bebop take off !")
	
	def land_push(self):
		self.pub_land.publish(self.empty_msg)
		self.main_textBrowser.setText("Bebop land !")
		
	def get_battery(self, battery_msg) :
		self.battery_percentage = battery_msg.percent
		self.battery_bar.setValue(self.battery_percentage)
		print("%s" % self.battery_percentage)

if __name__ == '__main__':
	app = QtGui.QApplication(sys.argv)
	myWindow = MyWindow()
	app.exec_()
