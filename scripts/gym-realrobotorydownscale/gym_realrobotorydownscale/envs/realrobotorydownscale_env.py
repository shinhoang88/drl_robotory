# **********************************************************************************************************************
# Contents          :RobotoryLab 7-DOF Downscale OpenAI's Gym environment for DRL.
# Observation       :[qT qdotT p_goalT p_eeT] belongs to R20
# Action            :[tauqT] belongs to R7  (manipulator torque vector including control and friction compensate torque)
# Task Modeling     :Manipulator track the arbitrary target from the initial configuration w.r.t [-0.4, -0.65, 0.1]
#                   and orientation [0., -math.pi, math.pi]
# Environment ver   :env = gym.make("realrobotorydownscale-v2")
# Author            :Phi Tien Hoang
# Date              :2020/09/06
# **********************************************************************************************************************

# ##########################################LIBRARIES IMPORTING#########################################################
import gym
from gym import error, spaces, utils
from gym.utils import seeding
from timeit import default_timer as timer
import os
import math
import random
import time
from time import sleep

import pybullet as p
import pybullet_data
import numpy as np
import rospy
from downscale4.msg import seven
from drl_robotory.msg import seven_py

MAX_ESPISODE_LEN = 2000

# ###########################################ENVIRONMENT PARAMETERS#####################################################
# p_init = np.array([0., -0.6, 0.12])  # Initial EE position
p_init = np.array([0.7, -0.0, 0.32])  # Initial EE position
# q_limit = np.array([3.14, 1.92, 3.14, 1.92, 3.14, 1.92, 3.14])
q_limit = np.array([2.9, 1.3, 2.9, 1.7, 2.9, 1.7, 2.9])
q_limit_action = np.array([0.02, 0.02, 0.02, 0.02, 0.02, 0.02, 0.02])
qdot_limit = np.array([0.1, 0.1, 0.1, 0.15, 0.15, 0.15, 0.15])
tau_limit = np.array([100, 250, 150, 150, 100, 100, 100])
# ###############################MANIPULATOR KINEMATICS CALCULATING SUB-FUNCTIONS#######################################
# Arm parameters
d1 = 0.371 + 0.2
d3 = 0.547
d5 = 0.484
d7 = 0.323


# d1 = 0.371 + 0.2
# d3 = 0.547
# d5 = 0.484
# d7 = 0.23066 + 0.2877313 # EE with gripper 0.0877313 0.211 0.1877313
# # d7 = 0.23066 + 0.05 # The old EE


# Kinematics calculating sub-functions
def matrixcomputationrotx(angle):
    rotx = np.array([[1, 0, 0],
                     [0, np.cos(angle), -np.sin(angle)],
                     [0, np.sin(angle), np.cos(angle)]])
    return rotx


def matrixcomputationroty(angle):
    roty = np.array([[np.cos(angle), 0, np.sin(angle)],
                     [0, 1, 0],
                     [-np.sin(angle), 0, np.cos(angle)]])
    return roty


def matrixcomputationrotz(angle):
    rotz = np.array([[np.cos(angle), -np.sin(angle), 0],
                     [np.sin(angle), np.cos(angle), 0],
                     [0, 0, 1]])
    return rotz


def robotorydownscaleforwardkinematics(jointPosition):
    T01 = np.array([[np.cos(jointPosition[0]), 0, -np.sin(jointPosition[0]), 0],
                    [np.sin(jointPosition[0]), 0, np.cos(jointPosition[0]), 0],
                    [0, -1, 0, d1],
                    [0, 0, 0, 1]])
    T12 = np.array([[np.cos(jointPosition[1]), 0, np.sin(jointPosition[1]), 0],
                    [np.sin(jointPosition[1]), 0, -np.cos(jointPosition[1]), 0],
                    [0, 1, 0, 0],
                    [0, 0, 0, 1]])
    T23 = np.array([[np.cos(jointPosition[2]), 0, -np.sin(jointPosition[2]), 0],
                    [np.sin(jointPosition[2]), 0, np.cos(jointPosition[2]), 0],
                    [0, -1, 0, d3],
                    [0, 0, 0, 1]])
    T34 = np.array([[np.cos(jointPosition[3]), 0, np.sin(jointPosition[3]), 0],
                    [np.sin(jointPosition[3]), 0, -np.cos(jointPosition[3]), 0],
                    [0, 1, 0, 0],
                    [0, 0, 0, 1]])
    T45 = np.array([[np.cos(jointPosition[4]), 0, -np.sin(jointPosition[4]), 0],
                    [np.sin(jointPosition[4]), 0, np.cos(jointPosition[4]), 0],
                    [0, -1, 0, d5],
                    [0, 0, 0, 1]])
    T56 = np.array([[np.cos(jointPosition[5]), 0, np.sin(jointPosition[5]), 0],
                    [np.sin(jointPosition[5]), 0, -np.cos(jointPosition[5]), 0],
                    [0, 1, 0, 0],
                    [0, 0, 0, 1]])
    T67 = np.array([[np.cos(jointPosition[6]), 0, -np.sin(jointPosition[6]), 0],
                    [np.sin(jointPosition[6]), 0, np.cos(jointPosition[6]), 0],
                    [0, -1, 0, d7],
                    [0, 0, 0, 1]])
    T07 = T01.dot(T12).dot(T23).dot(T34).dot(T45).dot(T56).dot(T67)
    posx = T07[0][3]
    posy = T07[1][3]
    posz = T07[2][3]

    p_result = np.array([posx, posy, posz])
    return p_result


def robotorydownscaleinversekinematics(targetPosition, targetOrientation, armAngle):
    targetPosition = np.array(targetPosition)
    targetOrientation = np.array(p.getEulerFromQuaternion(targetOrientation))

    alpha = targetOrientation[0]
    beta = targetOrientation[1]
    gamma = targetOrientation[2]

    Rinput = matrixcomputationrotz(gamma).dot(matrixcomputationroty(beta)).dot(matrixcomputationrotx(alpha))

    Tinput = np.array([[Rinput[0][0], Rinput[0][1], Rinput[0][2], targetPosition[0]],
                       [Rinput[1][0], Rinput[1][1], Rinput[1][2], targetPosition[1]],
                       [Rinput[2][0], Rinput[2][1], Rinput[2][2], targetPosition[2]],
                       [0, 0, 0, 1]])

    DZ = np.array([0, 0, 1])
    D1 = np.array([0, 0, d1])

    W = Tinput[:3, 3] - d7 * Tinput[:3, :3].dot(DZ)

    L_SW = W - D1
    norm_L_SW = np.linalg.norm(L_SW)
    # Elbow angle theta4 in radian
    q3 = np.arccos((np.power(norm_L_SW, 2) - np.power(d3, 2) - np.power(d5, 2)) / (2 * d3 * d5))

    if q3 >= 0:
        GC4 = 1
    else:
        GC4 = -1

    USW = L_SW / norm_L_SW
    KSW = np.array([[0, -USW[2], USW[1]],
                    [USW[2], 0, -USW[0]],
                    [-USW[1], USW[0], 0]])
    q1dot = np.arctan2(W[1], W[0])
    q2dot = np.pi / 2 - np.arcsin((W[2] - d1) / norm_L_SW) - \
            np.arccos((np.power(d3, 2) + np.power(norm_L_SW, 2) - np.power(d5, 2)) / (2 * d3 * norm_L_SW))
    R03dot = np.array([[np.cos(q1dot) * np.cos(q2dot), -np.cos(q1dot) * np.sin(q2dot), -np.sin(q1dot)],
                       [np.cos(q2dot) * np.sin(q1dot), -np.sin(q1dot) * np.sin(q2dot), np.cos(q1dot)],
                       [-np.sin(q2dot), -np.cos(q2dot), 0]])

    I3 = np.identity(3)
    XS = KSW.dot(R03dot)
    YS = - (KSW.dot(KSW)).dot(R03dot)
    ZS = (I3 + KSW.dot(KSW)).dot(R03dot)

    R34 = np.array([[np.cos(q3), 0, np.sin(q3)],
                    [np.sin(q3), 0, -np.cos(q3)],
                    [0, 1, 0]])
    XW = ((R34.transpose()).dot(XS.transpose())).dot(Tinput[:3, :3])
    YW = ((R34.transpose()).dot(YS.transpose())).dot(Tinput[:3, :3])
    ZW = ((R34.transpose()).dot(ZS.transpose())).dot(Tinput[:3, :3])

    # Theta2
    q1 = np.arccos(-np.sin(armAngle) * XS[2][1] - np.cos(armAngle) * YS[2][1] - ZS[2][1])

    if q1 >= 0:
        GC2 = 1
    else:
        GC2 = -1

    # Theta1 & Theta3
    q0 = np.arctan2(GC2 * (-np.sin(armAngle) * XS[1][1] - np.cos(armAngle) * YS[1][1] - ZS[1][1]),
                    GC2 * (-np.sin(armAngle) * XS[0][1] - np.cos(armAngle) * YS[0][1] - ZS[0][1]))
    q2 = np.arctan2(GC2 * (np.sin(armAngle) * XS[2][2] + np.cos(armAngle) * YS[2][2] + ZS[2][2]),
                    GC2 * (-np.sin(armAngle) * XS[2][0] - np.cos(armAngle) * YS[2][0] - ZS[2][0]))

    # Theta6
    q5 = np.arccos(np.sin(armAngle) * XW[2][2] + np.cos(armAngle) * YW[2][2] + ZW[2][2])
    if q5 >= 0:
        GC6 = 1
    else:
        GC6 = -1

    # Theta5 & Theta7
    q4 = np.arctan2(GC6 * (np.sin(armAngle) * XW[1][2] + np.cos(armAngle) * YW[1][2] + ZW[1][2]),
                    GC6 * (np.sin(armAngle) * XW[0][2] + np.cos(armAngle) * YW[0][2] + ZW[0][2]))
    q6 = np.arctan2(GC6 * (np.sin(armAngle) * XW[2][1] + np.cos(armAngle) * YW[2][1] + ZW[2][1]),
                    GC6 * (-np.sin(armAngle) * XW[2][0] - np.cos(armAngle) * YW[2][0] - ZW[2][0]))

    theta = np.array([q0, q1, q2, q3, q4, q5, q6])

    return theta


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

def messpublish(jointpos):
    msg = seven()
    msg.a = jointpos[0]
    msg.b = jointpos[1]
    msg.c = jointpos[2]
    msg.d = jointpos[3]
    msg.e = jointpos[4]
    msg.f = jointpos[5]
    msg.g = jointpos[6]
    pub.publish(msg)


def listener():
    # rospy.Subscriber('downscale_actp', seven, callback)
    msg = rospy.wait_for_message("downscale_actp", seven, timeout=None)
    global tt1, tt2, tt3, tt4, tt5, tt6, tt7
    tt1 = msg.a
    tt2 = msg.b
    tt3 = msg.c
    tt4 = msg.d
    tt5 = msg.e
    tt6 = msg.f
    tt7 = msg.g
    # rospy.spin()  # sleep for one second

# Initialize ros publisher node
rospy.init_node('drl_downscale', anonymous=True)
pub = rospy.Publisher('gazebo/downscale_jointp', seven, queue_size=1000)


# ############################################ENVIRONMENT CLASS#########################################################
class RealRobotorydownscaleEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    # Initialize the environment
    def __init__(self):

        self.step_counter = 0
        self.rate = rospy.Rate(250)  # 200hz
        # Terminating condition
        self.cartesian_2D_threshold_lv1 = 0.05
        self.cartesian_2D_threshold_lv2 = 0.02
        self.z_distance_threshold_lv1 = 0.02
        self.z_distance_threshold_lv2 = 0.012
        # Joint velocity limits
        self.max_theta_prime = qdot_limit
        self.min_theta_prime = -qdot_limit

        # Joint physical constraints
        self.max_theta = q_limit
        self.min_theta = -q_limit

        self.min_theta_action = -q_limit_action
        self.max_theta_action = q_limit_action

        # Joint torque limits
        self.max_torque = tau_limit
        self.min_torque = -tau_limit

        # Target object
        self.target_obj_display = p_init + \
                                  np.array([random.uniform(-0.1, 0.2), random.uniform(-0.5, 0.5), random.uniform(0, 0)])
        self.target_obj = self.target_obj_display + np.array([0, 0, 0.2])

        # Get info from URDF file
        self.downscaleEndEffectorIndex = 6
        self.numJoints = 7

        # Init configuration
        self.init_position = np.array([0.7, -0.0, 0.75])
        self.init_orientation = p.getQuaternionFromEuler([0., -math.pi, math.pi])
        self.rest_pose = robotorydownscaleinversekinematics(targetPosition=self.init_position,
                                                            targetOrientation=self.init_orientation,
                                                            armAngle=0)
        self.state_robot = self.init_position
        self.actual_joint_pos = self.rest_pose
        self.prev_joint_pos = self.actual_joint_pos
        self.next_joint_pos = self.actual_joint_pos
        self.actual_joint_vel = np.array([0, 0, 0, 0, 0, 0, 0])

        # self.rest_pose = np.array([0, 0, 0, math.pi / 2, 0, math.pi / 2, 0])
        self.rest_vel = np.array([0, 0, 0, 0, 0, 0, 0])

        # Define the box boundary for the Observation space
        self.current_eepos = p_init
        # Observation [theta1, ... , theta7, theta1_prime, ... , theta7_prime]
        self.low_state = np.concatenate((self.min_theta, self.min_theta_prime, self.target_obj, self.current_eepos),
                                        axis=0)
        self.high_state = np.concatenate((self.max_theta, self.max_theta_prime, self.target_obj, self.current_eepos),
                                         axis=0)
        self.observation_space = spaces.Box(low=self.low_state,
                                            high=self.high_state,
                                            dtype=np.float32)

        # Define the box boundary for the Action space
        # Action [theta1_prime, ... , theta7_prime]
        self.low_action = np.array(self.min_theta_prime,
                                   dtype=np.float32)
        self.high_action = np.array(self.max_theta_prime,
                                    dtype=np.float32)
        # self.low_action = np.concatenate((self.min_theta_action, self.min_theta_prime),
        #                                  axis=0)
        # self.high_action = np.concatenate((self.max_theta_action, self.max_theta_prime),
        #                                   axis=0)
        self.action_space = spaces.Box(low=self.low_action,
                                       high=self.high_action,
                                       dtype=np.float32)
        self.init_action = np.concatenate((self.rest_pose, self.rest_vel),
                                          axis=0)
        self.cartesian_distance = 0
        self.torque_norm = 0
        # Simulation step freq = 1kHz
        # p.setTimeStep(timeStep=0.001)

    # Reset the environment
    def reset(self):
        self.step_counter = 0
        # Target object
        self.target_obj_display = p_init + \
                                  np.array([random.uniform(-0.1, 0.2), random.uniform(-0.5, 0.5), random.uniform(0, 0)])
        self.target_obj = self.target_obj_display + np.array([0, 0, 0.2])
        trajpos = self.rest_pose
        # Initialize the robot to the init pose

        # NEED A REFINE RESET PROCEDURE HERE (generate a trajectory)
        listener()
        trajpos = np.array([tt1, tt2, tt3, tt4, tt5, tt6, tt7])
        time_count = 0
        Tf = 30
        time_start = time.time()
        while (np.linalg.norm(trajpos - self.rest_pose) > 0.0015):

            trajpos = trajpos + ((0.02 * (self.rest_pose - trajpos)) / pow(Tf, 2)) * pow(time_count, 2) + \
                             (((-0.02) * (self.rest_pose - trajpos)) / pow(Tf, 3)) * pow(time_count, 3)

            messpublish(trajpos)
            # msg = seven_py()
            # msg.a = trajpos[0]
            # msg.b = trajpos[1]
            # msg.c = trajpos[2]
            # msg.d = trajpos[3]
            # msg.e = trajpos[4]
            # msg.f = trajpos[5]
            # msg.g = trajpos[6]
            #
            # # rospy.loginfo(msg)
            # pub.publish(msg)

            time_count = time_count + 0.004
            # rospy.loginfo("")
            self.rate.sleep()
            # time_elapsed = (time.time() - time_start)
            # time_start = time.time()
            # print(time_elapsed)

        sleep(3)

        # Get new state data including: joint positions, velocities, torques
        listener()
        self.actual_joint_pos = np.array([tt1, tt2, tt3, tt4, tt5, tt6, tt7])
        self.prev_joint_pos = self.actual_joint_pos
        self.next_joint_pos = self.actual_joint_pos
        self.actual_joint_vel = np.array([0, 0, 0, 0, 0, 0, 0])
        self.state_robot = robotorydownscaleforwardkinematics(self.actual_joint_pos)
        print(self.state_robot)

        # Observation [theta1, ... , theta7, theta1_prime, ... , theta7_prime]
        self.observation = np.concatenate(
            (self.actual_joint_pos, self.actual_joint_vel, self.target_obj, self.state_robot),
            axis=0)

        # Return the observation
        return self.observation

    def step(self, action, stepnum):
        done = False

        for i in range(self.numJoints):
            self.next_joint_pos[i] = self.prev_joint_pos[i] + 0.004*action[i]
            if np.abs(self.next_joint_pos[i]) >= q_limit[i]:
                self.next_joint_pos[i] = self.prev_joint_pos[i]
        self.state_robot = robotorydownscaleforwardkinematics(self.next_joint_pos)
        if self.state_robot[2] <= 0.52:
            msg = seven_py()
            msg.a = self.prev_joint_pos[0]
            msg.b = self.prev_joint_pos[1]
            msg.c = self.prev_joint_pos[2]
            msg.d = self.prev_joint_pos[3]
            msg.e = self.prev_joint_pos[4]
            msg.f = self.prev_joint_pos[5]
            msg.g = self.prev_joint_pos[6]
            # rospy.loginfo(msg)
            pub.publish(msg)
            reward_pen = -0.5
        else:
            msg = seven_py()
            msg.a = self.next_joint_pos[0]
            msg.b = self.next_joint_pos[1]            msg.c = self.next_joint_pos[2]
            msg.d = self.next_joint_pos[3]
            msg.e = self.next_joint_pos[4]
            msg.f = self.next_joint_pos[5]
            msg.g = self.next_joint_pos[6]
            # rospy.loginfo(msg)
            pub.publish(msg)
            reward_pen = 0

        listener()
        self.actual_joint_pos = np.array([tt1, tt2, tt3, tt4, tt5, tt6, tt7])
        # print(self.actual_joint_pos)
        self.prev_joint_pos = self.actual_joint_pos
        self.actual_joint_vel = action
        self.state_robot = robotorydownscaleforwardkinematics(self.actual_joint_pos)

        w1 = 1
        w2 = 0.001
        w3 = 0
        target_2D = np.array([self.target_obj[0], self.target_obj[1]])
        current_2D = np.array([self.state_robot[0], self.state_robot[1]])
        z_distance = np.abs(self.target_obj[2] - self.state_robot[2])
        self.cartesian_distance = np.linalg.norm(self.target_obj - np.array(self.state_robot), 2)
        self.cartesian_2D = np.linalg.norm(target_2D - current_2D, 2)
        self.torque_norm = 0
        # self.torque_norm = np.linalg.norm(np.array(joint_torques), 2)

        # # if stepnum < 600000:
        # xy_threshold = self.cartesian_2D_threshold_lv2
        # z_threshold = self.z_distance_threshold_lv2



        if stepnum < 3e7:
            xy_threshold = self.cartesian_2D_threshold_lv1
            z_threshold = self.z_distance_threshold_lv1
        else:
            xy_threshold = self.cartesian_2D_threshold_lv2
            z_threshold = self.z_distance_threshold_lv2

        if self.cartesian_distance < xy_threshold and z_distance < z_threshold:
            done = True
            w3 = 25
        if self.step_counter == MAX_ESPISODE_LEN:
            done = True
            # Step simulation 1kHz
            # r.sleep()

        reward = - w1 * self.cartesian_distance - \
                 w2 * self.torque_norm + \
                 w3 + reward_pen

        # info = self.state_robot_sim
        # self.observation = np.concatenate((joint_positions, joint_velocities, self.target_obj, self.state_robot_sim),
        #                                   axis=0)

        info = self.state_robot
        self.observation = np.concatenate(
            (self.actual_joint_pos, self.actual_joint_vel, self.target_obj, self.state_robot),
            axis=0)

        # Step simulation 1kHz

        return self.observation, reward, done, info

    # def render(self, mode='human'):

    def __getstate__(self):
        return self.observation

    def close(self):
        p.disconnect()
