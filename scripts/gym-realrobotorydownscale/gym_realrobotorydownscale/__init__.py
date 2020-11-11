from gym.envs.registration import register

register(
    id='realrobotorydownscale-v0',
    entry_point='gym_realrobotorydownscale.envs:RealRobotorydownscaleEnv',
)
