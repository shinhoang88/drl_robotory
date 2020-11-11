#!/usr/bin/env python
import rospy
from std_msgs.msg import Empty
from std_msgs.msg import String
import numpy as np
from downscale4.msg import seven

pub = rospy.Publisher('gazebo/downscale_jointp', seven, queue_size=1000)

def callback(data):
    global tt1, tt2, tt3, tt4, tt5, tt6, tt7
    tt1 = data.a
    tt2 = data.b
    tt3 = data.c
    tt4 = data.d
    tt5 = data.e
    tt6 = data.f
    tt7 = data.g
    print_data = np.array([tt1, tt2, tt3, tt4, tt5, tt6, tt7])
    print(print_data)

def listener():

    rospy.init_node('drl_downscale', anonymous=True)

    rospy.Subscriber('downscale_actp', seven, callback)
    # rospy.spin()  # sleep for one second
    while not rospy.is_shutdown():
        # do whatever you want here
        msg = seven()
        msg.a = 0
        msg.b = - 0.1
        msg.c = 0
        msg.d = 0
        msg.e = 0
        msg.f = 0
        msg.g = 0
        pub.publish(msg)
        rospy.sleep(0.01)  # sleep for one second

if __name__ == '__main__':
    listener()
