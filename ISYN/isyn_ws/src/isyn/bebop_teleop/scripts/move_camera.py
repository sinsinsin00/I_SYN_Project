#!/usr/bin/env python
  
from __future__ import print_function
import rospy, os, time, sys, termios, select, atexit, tty, math
from geometry_msgs.msg import Twist
from std_msgs.msg import Empty, Bool
from ftplib import FTP
import tempfile
  
msg = """
Control your Bebop2.0!
-----------------------------------------------------------
Left hand around:                    Right hand around:
        w                                    u                      
   a    s    d                         h     j     k
 
' ' : stop( hover )
 
w/s : going   up / down
a/d : rotate ccw / cw
i/k : go  foward / backward
j/l : go    left / righ
  
' ' : hovering
 1  : take off
 2  : landing
 3  : emergency
  
+/- : increase / decrease speed
  
Q to quit
"""
e = """
Communications Failed
"""
#         +---+-------------+---+-------------+---+-------------+---+-------------+---+------------+
#         |'w'| linear.z +  |'a'| angular.z + |'i'| linear.x +  |'j'| linear.y +  |' '|all param=0 |
#         +---+-------------+---+-------------+---+-------------+---+-------------+---+------------+
#         |'s'| linear.z -  |'d'| angular.z - |'k'| linear.x -  |'l'| linear.y +  |   |            |
#         +---+-------------+---+-------------+---+-------------+---+-------------+---+------------+
action = { 'w':( -1, 0),'a':( 0, 1), ' ':( 0, 0), 's':( 1, 0),'d':( 0, -1)}
 
# class for get 1 byte from standard input( keyboard )
class GetChar:
    def __init__(self):
        # Save the terminal settings
        self.fd = sys.stdin.fileno()
        self.new_term = termios.tcgetattr(self.fd)
        self.old_term = termios.tcgetattr(self.fd)
 
        # New terminal setting unbuffered
        self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)
 
        # Support normal-terminal reset at exit
        atexit.register(self.set_normal_term)
     
     
    def set_normal_term(self):
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)
 
    def getch(self):        # get 1 byte from stdin
        """ Returns a keyboard character after getch() has been called """
        return sys.stdin.read(1)
 
    def chk_stdin(self):    # check keyboard input
        """ Returns True if keyboard character was hit, False otherwise. """
        dr, dw, de = select([sys.stdin], [], [], 0)
        return dr
  
def get_currunt_speed(ang_y, ang_z):
    return "currently:\tangular y: %s\tangular z: %s " % (ang_y, ang_z)
 
 
if __name__=="__main__":
    # settings = termios.tcgetattr(sys.stdin)
  
    pub0 = rospy.Publisher('bebop/camera_control', Twist, queue_size = 1)
     
    kb          = GetChar()    
    rospy.init_node('remote_camera_ctrl')
 
    ang_y = 0;    ang_z = 0;    count = 0
  
    try:
        print(msg)
        print(get_currunt_speed(ang_y, ang_z))
         
        key = ''
         
        while(key != 'Q'):
         
            key = kb.getch()
             
            if key in action.keys():    # set linear x,y,z or angular z
                ang_y  = action[key][0]
                ang_z  = action[key][1]
                 
            else:                       # just hover
                ang_y = 0;  ang_z = 0
             
            print(get_currunt_speed(ang_y, ang_z))
  
            twist = Twist()
             
            twist.linear.x  = 0
            twist.linear.y  = 0
            twist.linear.z  = 0
             
            twist.angular.x = 0
            twist.angular.y = ang_y
            twist.angular.z = ang_z
             
            pub0.publish(twist)
         
        #pub2.publish(empty_msg)         # land
        print("camera control Stop!!")
 
    except KeyboardInterrupt:
        pub2.publish(empty_msg)         # land
        print("bebop have landed!")
