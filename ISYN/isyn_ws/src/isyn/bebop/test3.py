#!/usr/bin/env python

import rospy, os, time, sys, termios, select, atexit, tty, math
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Empty, Bool, Int8
from PyQt4 import QtGui, uic, QtCore
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from bebop_msgs.msg import CommonCommonStateBatteryStateChanged

class MyWindow(QtGui.QMainWindow):
	def __init__(self):
		super(MyWindow, self).__init__()
		uic.loadUi('test5.ui', self)
		self.show()
		rospy.init_node('test_take_off', anonymous=True)

		# buttons initialize
		self.take_off_button.clicked.connect(self.take_off_push)
		self.land_button.clicked.connect(self.land_push)
		self.emergency_button.clicked.connect(self.emergency_push)
		self.shot_button.clicked.connect(self.shot_push)
		# self.start_button.clicked.connect(self.start_push)
		# self.stop_button.clicked.connect(self.stop_push)
		self.send_button.clicked.connect(self.send_push)

		#  values initialize
		self.battery_percentage = 100

		#  message initialize
		self.empty_msg = Empty()

		#  subscriber initialize
		self.sub_battery = rospy.Subscriber('/bebop/states/common/CommonState/BatteryStateChanged/', CommonCommonStateBatteryStateChanged, self.get_battery)

		#  publisher initialize
		self.pub_takeoff = rospy.Publisher('bebop/takeoff', Empty, queue_size=1)
		self.pub_land = rospy.Publisher('bebop/land', Empty, queue_size=1)
		self.pub_shot = rospy.Publisher('bebop/snapshot', Empty, queue_size=1)
		self.pub_emergency = rospy.Publisher('bebop/reset', Empty, queue_size=1)

		#  thread
		self.progress_thread = progressThread()
		self.progress_thread.start()
		self.progress_thread.progress_update.connect(self.set_progress_bar)


	#  button functions
	def take_off_push(self):
		self.pub_takeoff.publish(self.empty_msg)
		self.main_textBrowser.append("Bebop take off !")
	
	def land_push(self):
		self.pub_land.publish(self.empty_msg)
		self.main_textBrowser.append("Bebop land !")

	def shot_push(self):
		self.pub_shot.publish(self.empty_msg)
		self.main_textBrowser.append("Take a snapshot !")

	def emergency_push(self):
		self.pub_emergency.publish(self.empty_msg)
		self.main_textBrowser.append("Emergency Landing !")

	def send_push(self):
		x_value = self.x_text_edit.toPlainText()
		y_value = self.y_text_edit.toPlainText()
		self.main_textBrowser.append("%s" % x_value)
		self.main_textBrowser.append("%s" % y_value)

	#  status functions
	def get_battery(self, battery_msg) :
		self.battery_percentage = battery_msg.percent

	def set_progress_bar(self):
		self.battery_bar.setValue(self.battery_percentage)


class progressThread(QtCore.QThread):
	progress_update = QtCore.pyqtSignal(int)  # or pyqtSignal(int)

	def __init__(self):
		QtCore.QThread.__init__(self)

	def __del__(self):
		self.wait()

	def run(self):
		# your logic here
		while 1:  # self.emit(SIGNAL('PROGRESS'), maxVal)
			maxVal = 100
			self.progress_update.emit(maxVal)
			# Tell the thread to sleep for 1 second and let other things run
			time.sleep(1)


if __name__ == '__main__':
	app = QtGui.QApplication(sys.argv)
	myWindow = MyWindow()
	app.exec_()
