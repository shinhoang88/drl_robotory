#!/usr/bin/env python
import rospy
import cv2
from downscale4.msg import seven
from std_msgs.msg import String
import os
import gym
import gym_realrobotorydownscale

from tf2rl.algos.td3 import TD3
from tf2rl.algos.ddpg import DDPG
from tf2rl.experiments.trainer import Trainer
from tf2rl.experiments.loader import Loader
import argparse
from cpprb import ReplayBuffer, PrioritizedReplayBuffer
parser = Trainer.get_argument()
# parser.add_argument('--max-steps', type=int, default=int(8e4))
parser = TD3.get_argument(parser)
args = parser.parse_args()


def main():
    env = gym.make("realrobotorydownscale-v0")
    policy = DDPG(
    state_shape=env.observation_space.shape,
    action_dim=env.action_space.high.size,
    gpu=0,  # -1 Run on CPU. If you want to run on GPU, specify GPU number
    memory_capacity=1e6,
    max_action=env.action_space.high[0],
    batch_size=100,
    n_warmup=1e4)

    trainer = Trainer(policy, env, args)
    trainer()

def test_import():
    assert main() is True

if __name__ == '__main__':
    # listener()
    try:
        while True:
            main()
    except KeyboardInterrupt:
        print('Done.')

# Follow the tensorboar:
    # cd -> results main folder
    # tensorboard --logdir results
    # http://localhost:6006/
