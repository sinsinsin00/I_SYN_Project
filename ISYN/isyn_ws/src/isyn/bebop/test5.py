#!/usr/bin/env python

import rospy, roslib, os, time, sys, termios, select, atexit, tty, math
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Empty, Bool, Int8
from sensor_msgs.msg import Image    	 # for receiving the video feed
from PyQt4 import QtGui, uic, QtCore
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from bebop_msgs.msg import CommonCommonStateBatteryStateChanged
from threading import Lock
import subprocess

CONNECTION_CHECK_PERIOD = 250 #ms
GUI_UPDATE_PERIOD = 20 #ms
DETECT_RADIUS = 4 # the radius of the circle drawn when a tag is detected

class MyWindow(QtGui.QMainWindow):
	def __init__(self):
		super(MyWindow, self).__init__()
		uic.loadUi('test5.ui', self)
		
		image_raw_label = self.image_raw_label	
			
		rospy.init_node('test_take_off', anonymous=True)
		
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

		# buttons set
		self.take_off_button.clicked.connect(self.take_off_push)
		self.land_button.clicked.connect(self.land_push)
		self.emergency_button.clicked.connect(self.emergency_push)
		self.shot_button.clicked.connect(self.shot_push)
		self.start_button.clicked.connect(self.start_push)
		# self.stop_button.clicked.connect(self.stop_push)
		self.send_button.clicked.connect(self.send_push)
		
		#button images
		rMyIcon = QtGui.QPixmap("Take_off.jpg")
		self.take_off_button.setIcon(QtGui.QIcon(rMyIcon))

		#  thread
		self.progress_thread = progressThread()
		self.progress_thread.start()
		self.progress_thread.progress_update.connect(self.set_progress_bar)
		#self.init_main_label()

		#time editor initialize
		self.dateTimeEdit.setDateTime(QtCore.QDateTime.currentDateTime())
		
		#video init
		self.imageBox = self.image_raw_label
		self.subVideo   = rospy.Subscriber('/bebop/image_raw',Image,self.ReceiveImage)
		self.image = None
		self.imageLock = Lock()
		self.tags = []
		self.tagLock = Lock()
		self.communicationSinceTimer = False
		self.connected = False
		self.connectionTimer = QtCore.QTimer(self)
		self.connectionTimer.timeout.connect(self.ConnectionCallback)
		self.connectionTimer.start(CONNECTION_CHECK_PERIOD)
		self.redrawTimer = QtCore.QTimer(self)
		self.redrawTimer.timeout.connect(self.RedrawCallback)
		self.redrawTimer.start(GUI_UPDATE_PERIOD)
		
		#photoviewer init
		self.PhotoViewer = self.main_window
		self.PhotoViewer.photoClicked.connect(self.photoClicked)
		self.PhotoViewer.setPhoto(QtGui.QPixmap('map.png'))
		self._zoom = 0
		self._empty = True
		self._scene = QtGui.QGraphicsScene(self)
		self._photo = QtGui.QGraphicsPixmapItem()
		self._scene.addItem(self._photo)
		self.setScene(self._scene)
		self.setTransformationAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
		self.setResizeAnchor(QtGui.QGraphicsView.AnchorUnderMouse)
		self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
		self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
		self.setFrameShape(QtGui.QFrame.NoFrame)
		
		# Arrange layout
		VBlayout = QtGui.QVBoxLayout(self)
		VBlayout.addWidget(self.PhotoViewer)
		HBlayout = QtGui.QHBoxLayout()
		HBlayout.setAlignment(QtCore.Qt.AlignLeft)
		VBlayout.addLayout(HBlayout)

		
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
	
	def start_push(self):
		self.image = subprocess.Popen('rqt_image_view',shell=True)

	#  status functions
	def get_battery(self, battery_msg) :
		self.battery_percentage = battery_msg.percent

	def set_progress_bar(self):
		self.battery_bar.setValue(self.battery_percentage)
   
	def pixInfo(self):
		self.viewer.toggleDragMode()
	
	def photoClicked(self, pos):
		if self.viewer.dragMode()  == QtGui.QGraphicsView.NoDrag:
			self.editPixInfo.setText('%d, %d' % (pos.x(), pos.y()))
			
			
	#video streaming functions
	def ConnectionCallback(self):
		self.connected = self.communicationSinceTimer
		self.communicationSinceTimer = False

	def RedrawCallback(self):
		if self.image is not None:
			self.imageLock.acquire()
			try:			
					image = QtGui.QPixmap.fromImage(QtGui.QImage(self.image.data, self.image.width, self.image.height, QtGui.QImage.Format_RGB888))
					if len(self.tags) > 0:
						self.tagLock.acquire()
						try:
							painter = QtGui.QPainter()
							painter.begin(image)
							painter.setPen(QtGui.QColor(0,255,0))
							painter.setBrush(QtGui.QColor(0,255,0))
							for (x,y,d) in self.tags:
								r = QtCore.QRectF((x*image.width())/1000-DETECT_RADIUS,(y*image.height())/1000-DETECT_RADIUS,DETECT_RADIUS*2,DETECT_RADIUS*2)
								painter.drawEllipse(r)
								painter.drawText((x*image.width())/1000+DETECT_RADIUS,(y*image.height())/1000-DETECT_RADIUS,str(d/100)[0:4]+'m')
							painter.end()
						finally:
							self.tagLock.release()
			finally:
				self.imageLock.release()

			self.imageBox.setPixmap(image)

	def ReceiveImage(self,data):
		self.communicationSinceTimer = True

		self.imageLock.acquire()
		try:
			self.image = data 
		finally:
			self.imageLock.release()
			
			
	# main window functions
	def hasPhoto(self):
		return not self._empty
		
	def fitInView(self, scale=True):
		rect = QtCore.QRectF(self._photo.pixmap().rect())
		if not rect.isNull():
			self.setSceneRect(rect)
			if self.hasPhoto():
				unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
				self.scale(1 / unity.width(), 1 / unity.height())
				viewrect = self.viewport().rect()
				scenerect = self.transform().mapRect(rect)
				factor = min(viewrect.width() / scenerect.width(),
							 viewrect.height() / scenerect.height())
				self.scale(factor, factor)
			self._zoom = 0
	
	def setPhoto(self, pixmap=None):
		self._zoom = 0
		if pixmap and not pixmap.isNull():
			self._empty = False
			self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)
			self._photo.setPixmap(pixmap)
		else:
			self._empty = True
			self.setDragMode(QtGui.QGraphicsView.NoDrag)
			self._photo.setPixmap(QtGui.QPixmap())
		self.fitInView()
	
	def wheelEvent(self, event):
		if self.hasPhoto():
			if event.delta() > 0:
				factor = 1.25
				self._zoom += 1
			else:
				factor = 0.8
				self._zoom -= 1
			if self._zoom > 0:
				self.scale(factor, factor)
			elif self._zoom == 0:
				self.fitInView()
			else:
				self._zoom = 0

	def toggleDragMode(self):
		if self.dragMode() == QtGui.QGraphicsView.ScrollHandDrag:
			self.setDragMode(QtGui.QGraphicsView.NoDrag)
		elif not self._photo.pixmap().isNull():
			self.setDragMode(QtGui.QGraphicsView.ScrollHandDrag)

	def mousePressEvent(self, event):
		if self._photo.isUnderMouse():
			self.photoClicked.emit(QtCore.QPoint(event.pos()))
		super(PhotoViewer, self).mousePressEvent(event)
		
	


#battery status thread
class progressThread(QtCore.QThread):
	progress_update = QtCore.pyqtSignal(int)  
	
	def __init__(self):
		QtCore.QThread.__init__(self)

	def __del__(self):
		self.wait()

	def run(self):
		while 1:  
			maxVal = 100
			self.progress_update.emit(maxVal)
			time.sleep(1)


if __name__ == '__main__':
	try:
		app = QtGui.QApplication(sys.argv)
		myWindow = MyWindow()
		myWindow.show()
		app.exec_()
	except rospy.ROSInterruptException:
		pass
