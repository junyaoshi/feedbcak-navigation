# Import Libraries
from gibson.envs.husky_env import HuskyNavigateSpeedControlEnv
import inspect
from pprint import pprint
import pybullet as p
import os
import math
import random
import time as t
from time import sleep
from math import pi
# from transforms3d.euler import quat2euler

# Parse config and object arguments
config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'configs', 'husky_stadium.yaml')
green_cube_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'objects', 'green_cube.urdf')
red_cube_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'objects', 'red_cube.urdf')
yellow_cube_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'objects', 'yellow_cube.urdf')
blue_cube_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'objects', 'blue_cube.urdf')
pprint('config file: {}'.format(config_file))
# pprint('white cube file: {}'.format(green_cube_file))
# pprint('blue cube file: {}'.format(blue_cube_file))

import argparse
parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--config', type=str, default=config_file)
parser.add_argument('--gpu', type=int, default=0)
args = parser.parse_args()
print(args)

# create environment
# env = HuskyNavigateEnv(human=True, timestep=timestep, frame_skip=frame_skip, mode="RGB", is_discrete = True, resolution=args.resolution)
env = HuskyNavigateSpeedControlEnv(config=args.config, gpu_idx = args.gpu)
env.reset()

# (ord('s'), ): [-0.5,0], ## backward
# (ord('w'), ): [0.5,0], ## forward
# (ord('d'), ): [0,-0.5], ## turn right
# (ord('a'), ): [0,0.5], ## turn left

# define constants
FORWARD = [0.2, 0]
BACKWARD = [-0.2, 0]
RIGHT = [0, -0.5]
LEFT = [0, 0.5]
IDLE = [0, 0]
initial_yaw = 3.1415926
initial_x, initial_y, initial_z = 15, 21, 0.14
target_x, target_y, target_z = env.robot.get_target_position()


def calc_3d_dist(p, q):
    """
    :param p: robot position list p
    :param q: robot position list q
    :return: the 3D Euclidean distance between p and q
    """
    return sum((p - q) ** 2 for p, q in zip(p, q)) ** 0.5


def calc_2d_dist(p, q):
    """
    :param p: robot position list p
    :param q: robot position list q
    :return: the 2D Euclidean distance between p and q
    """
    p = [p[0], p[1]]
    q = [q[0], q[1]]
    return sum((p - q) ** 2 for p, q in zip(p, q)) ** 0.5


def calc_x_dist(p, q):
    """
    :param p: robot position list p
    :param q: robot position list q
    :return: the x-axis Euclidean distance between p and q
    """
    return abs(p[0]-q[0])


def quaternion_to_euler(orn, yaw_only=True):
    """
    :param orn: a 4-element list of quarternion angles
    :return: a 3-element list of eulerian angles [yaw, pitch, roll]
    """
    x, y, z, w = orn

    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(t0, t1)
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch = math.asin(t2)
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(t3, t4)
    if yaw_only:
        return yaw
    else:
        return [yaw, pitch, roll]


def convert_angle(angle):
    """
    convert angle to range (0, 2*pi)
    :param angle:
    :return: converted angle
    """
    if angle > 2*pi:
        angle -= 2*pi
    elif angle < 0:
        angle += 2*pi
    return angle


def pause(env, time=100):
    """
    Do nothing
    """
    print('Pausing for {} timesteps'.format(time))
    for i in range(time):
        ensure_orientation(env)
        env.step(IDLE)


def brake(env, time=100, adjustment_precision=0.0001):
    """
    Brakes
    :param adjustment_precision: the amount of adjustment the robot accounts for its drifting
    """
    print('Braking for {} timesteps'.format(time))
    x_pos = env.robot.get_position()[0]
    for i in range(time):
        ensure_orientation(env)
        new_x_pos = env.robot.get_position()[0]
        if new_x_pos < x_pos:
            env.robot.move_backward(adjustment_precision)
        elif new_x_pos > x_pos:
            env.robot.move_forward(adjustment_precision)
        x_pos = new_x_pos
        env.step(IDLE)


def brake_at_state(env, state, time=100, adjustment_precision=0.001):
    """
    Brakes
    :param adjustment_precision: the amount of adjustment the robot accounts for its drifting
    """
    print('Braking at state {} for {} timesteps'.format(state, time))
    for i in range(time):
        ensure_orientation(env)
        x_pos = env.robot.get_position()[0]
        if x_pos < state:
            env.robot.move_backward(adjustment_precision)
        elif x_pos > state:
            env.robot.move_forward(adjustment_precision)
        env.step(IDLE)


def ensure_orientation(env, tolerance=0.001):
    """
    Ensures the robot's orientation does not change
    """
    yaw = convert_angle(quaternion_to_euler(env.robot.get_orientation()))
    while abs(yaw - initial_yaw) > tolerance:
        if yaw < initial_yaw:
            env.step(LEFT)
        else:
            env.step(RIGHT)
        yaw = convert_angle(quaternion_to_euler(env.robot.get_orientation()))


def move_forward(env, distance=3, enforce_state=True):
    """
    Moves robot forward
    """
    print("Moving forward for {} meters".format(abs(distance)))
    p = env.robot.get_position()
    q = p
    if enforce_state:
        x_pos = p[0]
        current_state = int(round(x_pos))
        goal_state = current_state - distance
        while x_pos > goal_state:
            ensure_orientation(env)
            _, rew, _, _ = env.step(FORWARD)
            x_pos = env.robot.get_position()[0]
    else:
        while calc_x_dist(p, q) <= distance:
            ensure_orientation(env)
            _, rew, _, _ = env.step(FORWARD)
            q = env.robot.get_position()


def move_backward(env, distance=3, enforce_state=True):
    """
    :param enforce_state: ensures that the robot arrives at a dicrete state
    Moves robot backward
    """
    print("Moving backward for {} meters".format(abs(distance)))
    p = env.robot.get_position()
    q = p
    if enforce_state:
        x_pos = p[0]
        current_state = int(round(x_pos))
        goal_state = current_state + distance
        while x_pos < goal_state:
            ensure_orientation(env)
            _, rew, _, _ = env.step(BACKWARD)
            x_pos = env.robot.get_position()[0]
    else:
        while calc_x_dist(p, q) <= distance:
            ensure_orientation(env)
            _, rew, _, _ = env.step(BACKWARD)
            q = env.robot.get_position()


def accelerate_forward(env, time=100, indicator_file=None):
    """
    Accelerates forward for designated timesteps
    """
    print("Accelerating forward for {} timesteps".format(time))
    pos = env.robot.get_position()
    # orn = env.robot.get_orientation()
    x0, y0, z0 = pos
    id = p.loadURDF(fileName=indicator_file,
                    basePosition=[x0, y0, z0+1],
                    useFixedBase=True)
    # for i in range(time):
    #     indicator_pos, _ = p.getBasePositionAndOrientation(bodyUniqueId=id)
    #     indicator_x, _, _ = indicator_pos
    #     pos = env.robot.get_position()
    #     orn = env.robot.get_orientation()
    #     old_x, y, z = pos
    #     past = t.time()
    #     if abs(indicator_x - old_x) > 0.1:
    #         p.resetBasePositionAndOrientation(bodyUniqueId=id, posObj=[old_x, y, z+1], ornObj=orn)
    #     ensure_orientation(env)
    #     env.step(FORWARD)
    #     pos = env.robot.get_position()
    #     # orn = env.robot.get_orientation()
    #     new_x, y, z = pos
    #     present = t.time()
    #     x_velocity = (new_x-old_x)/(present-past)
    #     print('x vel: {}'.format(x_velocity))
    #     p.resetBaseVelocity(objectUniqueId=id, linearVelocity=[x_velocity, 0, 0])
    #     if abs(indicator_x - new_x) > 0.1:
    #         p.resetBasePositionAndOrientation(bodyUniqueId=id, posObj=[new_x, y, z+1], ornObj=orn)
    #     # ensure_orientation(env)
    #     # env.step(FORWARD)

    for i in range(time):
        indicator_pos, _ = p.getBasePositionAndOrientation(bodyUniqueId=id)
        indicator_x, _, _ = indicator_pos
        pos = env.robot.get_position()
        orn = env.robot.get_orientation()
        old_x, y, z = pos
        past = t.time()

        if i%time == 0:
            p.resetBasePositionAndOrientation(bodyUniqueId=id, posObj=[old_x, y, z+1], ornObj=orn)
        # ensure_orientation(env)
        env.step(FORWARD)
        pos = env.robot.get_position()
        # orn = env.robot.get_orientation()
        new_x, y, z = pos
        present = t.time()
        x_velocity = (new_x-old_x)/(present-past)
        print('x vel: {}'.format(x_velocity))
        # p.resetBaseVelocity(objectUniqueId=id, linearVelocity=[x_velocity, 0, 0])
        # if abs(indicator_x - new_x) > 0.1:
        #     p.resetBasePositionAndOrientation(bodyUniqueId=id, posObj=[new_x, y, z+1], ornObj=orn)
        # ensure_orientation(env)
        # env.step(FORWARD)
    p.removeBody(id)


def accelerate_backward(env, time=100):
    """
    Accelerates backward for designated timesteps
    """
    print("Accelerating backward for {} timesteps".format(time))
    for i in range(time):
        # ensure_orientation(env)
        env.step(BACKWARD)


def main():
    timestep = 30

    # create white cubes signifying various states, blue cube signifying goal state
    start_state = -99
    end_state = 99
    goal_state = target_x
    interval = 3  # discrete interval of state space

    env.fov = initial_yaw

    # # get the attributes of env object
    # l = dir(env)
    # pprint(l, indent=2)

    p.loadURDF(fileName=blue_cube_file,
               basePosition=[goal_state, initial_y, 0],
               useFixedBase=True)

    # robot takes random actions
    brake(env, time=300)
    for i in range(timestep):
        print('robot position: {}'.format(env.robot.get_position()))
        print('robot orientation: {}'.format(quaternion_to_euler(env.robot.get_orientation())))
        print('robot distance to target: {}'.format(env.robot.dist_to_target()))
        num = random.random()
        object_id = 0
        if num < 1/3:
            accelerate_forward(env, time=300, indicator_file=green_cube_file)
        elif num < 2/3:
            accelerate_backward(env, time=300) #, indicator_file=green_cube_file)
        else:
            accelerate_backward(env, time=300) #, indicator_file=green_cube_file)
        timestep += 1

    brake(env, time=400)


if __name__ == '__main__':
    main()







