#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from os.path import join
import subprocess
import pathlib
import numpy as np

import util
import matio
import pyosr
import partt
import touchq_util

# Pipeline local file
# 
# Here we always use "trajectory" to represent the curve in configuration space
# and "path" always refers to the path in a file system.
_TRAJECTORY_SCRATCH = join(util.CONDOR_SCRATCH, 'training_trajectory')
_KEYCAN_SCRATCH = join(util.CONDOR_SCRATCH, 'training_key_can')
_CANDIDATE_FILE = 'KeyCan.npz'

def _get_candidate_file(ws):
    return ws.condor_ws(util.TRAINING_DIR, _CANDIDATE_FILE)

'''
System Architecture:
    1. All tasks are executed locally, which makes debugging easier
    2. autorun() will ssh into remote hosts to do the corresponding tasks (e.g. submit condor jobs)
    3. Synchronous Condor job is achieved through condor_submit and condor_wait
    4. If the ssh connection is broken while condor_wait,
       autorun will try it again after 5 seconds
'''

def find_trajectory(args, ws):
    se3solver_path = ws.condor_exec('se3solver.py')
    scratch_dir = ws.condor_ws(_TRAJECTORY_SCRATCH)
    _, config = parse_ompl(ws.training_puzzle)
    args = [se3solver_path,
            'solve', ws.training_puzzle,
            '--cdres', config.getfloat('problem', 'collision_resolution', fallback=0.0001),
            '--trajectory_out', '{}/traj_$(Process).npz'.format(scratch_dir),
            ws.config.get('TrainingTrajectory', 'PlannerAlgorithmID'),
            ws.config.get('TrainingTrajectory', 'CondorTimeThreshold'),
           ]
    if args.only_wait:
        condor.local_wait(scratch_dir)
        return
    condor.local_submit(ws,
                        '/usr/bin/python3',
                        iodir=scratch_dir,
                        arguments=args,
                        instances=ws.config.get('TrainingTrajectory', 'CondorInstances'),
                        wait=True)


def interpolate_trajectory(args, ws):
    scratch_dir = ws.condor_ws(_TRAJECTORY_SCRATCH)
    candidate_file = _get_candidate_file(ws)
    # Do not process only_wait, we need to restart if ssh is broken
    Qs = []
    for fn in pathlib.Path(scratch_dir).glob("traj_*.npz"):
        d = matio.load(fn)
        if d['FLAG_IS_COMPLETE'] == 0:
            continue
        traj = d['OMPL_TRAJECTORY']
        metrics = pyosr.path_metric(traj)
        npoint = ws.config.getint('TrainingKeyConf', 'CandidateNumber')
        dtau = metrics / float(npoint)
        Qs += [pyosr.path_interpolate(traj, dtau * i) for i in range(npoint)]
    np.savez(candidate_file, OMPL_CANDIDATES=Qs)


'''
Note: clearance is measured in unitary configuration space
'''
def estimate_clearance_volume(args, ws):
    scratch_dir = ws.condor_ws(_KEYCAN_SCRATCH)
    if args.only_wait:
        condor.local_wait(scratch_dir)
        return
    # Prepare the data and task description
    candidate_file = _get_candidate_file(ws)
    Qs = matio.load(candidate_file)['OMPL_CANDIDATES']
    nq = Qs.shape[0]
    uw = ws.condor_unit_world(util.TRAINING_DIR)
    task_shape = (nq)
    total_chunks = partt.guess_chunk_number(task_shape,
            ws.config.getint('DEFAULT', 'CondorQuota') * 2,
            ws.config.getint('TrainingKeyConf', 'ClearanceTaskGranularity'))

    if total_chunks > 1 and args.task_id is None:
        os.makedirs(scratch_dir, exist_ok=True)
        # Submit a Condor job
        args = ['facade.py',
                'preprocess_key',
                '--stage', 'estimate_clearance_volume'
                '--task_id', '$(Process)']
        condor.local_submit(ws,
                            '/usr/bin/python3',
                            iodir=scratch_dir,
                            arguments=args,
                            instances=total_chunks,
                            wait=True)
    else:
        # Do the actual work (either no need to partition, or run from HTCondor)
        task_id = 0 if total_chunks == 1 else args.task_id
        tindices = partt.get_task_chunk(task_shape, total_chunks, task_id)
        npoint = ws.config.getint('TrainingKeyConf', 'ClearanceSample')
        for qi in tindices:
            free_vertices, touch_vertices, to_inf, free_tau, touch_tau = touchq_util.calc_touch(uw, Qs[qi], npoint, uw.recommended_cres)
            out_fn = join(scratch_dir, 'unitary_clearance_from_keycan-{}.npz'.format(qi))
            np.savez(out_fn,
                     FROM_V_OMPL=Qs[qi],
                     FROM_V=uw.translate_to_unit_state(Qs[qi]),
                     FREE_V=free_vertices,
                     TOUCH_V=touch_vertices,
                     IS_INF=to_inf,
                     FREE_TAU=free_tau,
                     TOUCH_TAU=touch_tau)

def pickup_key_configuration(args, ws):
    scratch_dir = ws.condor_ws(_KEYCAN_SCRATCH)
    os.makedirs(scratch_dir, exist_ok=True)
    top_k = ws.config.getint('TrainingKeyConf', 'KeyConf')
    fn_list = []
    median_list = []
    # Do not process only_wait, we need to restart if ssh is broken
    for fn in pathlib.Path(scratch_dir).glob('unitary_clearance_from_keycan-*.npz'):
        d = matio.load(fn)
        distances = pyosr.multi_distance(d['FROM_V'], d['FREE_V'])
        fn_list.append(fn)
        median_list.append(np.median(distances))
    top_k_indices = np.array(median_list).argsort()[:top_k]
    kq_ompl = []
    kq = []
    for fn in fn_list[top_k_indices]:
        d = matio.load(fn)
        kq_ompl.append(d['FROM_V_OMPL'])
        kq.append(d['FROM_V'])
    key_out = ws.condor_ws(util.KEY_FILE)
    np.savez(key_out, KEYQ_OMPL=kq_ompl, KEYQ=kq)

# We decided not to use reflections because we may leak internal functions to command line
function_dict = {
        'find_trajectory' : find_trajectory,
        'interpolate_trajectory' : interpolate_trajectory,
        'estimate_clearance_volume' : estimate_clearance_volume,
        'pickup_key_configuration' : pickup_key_configuration,
}

def setup_parser(subparsers):
    p = subparsers.add('preprocess_key',
            help='Preprocessing step, to figure out the key configuration in the training puzzle')
    p.add_argument('--stage', choices=list(function_dict.keys()), default='')
    p.add_argument('--only_wait', action='store_true')
    p.add_argument('--task_id', help='Feed $(Process) from HTCondor', type=int, default=None)

def run(args):
    if args.stage in function_dict:
        ws = util.Workspace(args.dir)
        function_dict[args.stage](args, ws)
    else:
        print("Unknown preprocessing pipeline stage {}".format(args.stage))

# Hint: it's recommended to have a _remote_command per module
# Workspace.remote_command is too tedious to use directly.
def _remote_command(ws, cmd, auto_retry=True):
    ws.remote_command(ws.condor_host, ws.condor_exec, 'preprocess_key', cmd, auto_retry=auto_retry)

def remote_find_trajectory(ws):
    _remote_command(ws, 'find_trajectory')

def remote_interpolate_trajectory(ws):
    _remote_command(ws, 'interpolate_trajectory')

def remote_estimate_clearance_volume(ws):
    _remote_command(ws, 'estimate_clearance_volume')

def remote_pickup_key_configuration(ws):
    _remote_command(ws, 'pickup_key_configuration')

def autorun(args):
    ws = util.Workspace(args.dir)
    ws.deploy_to_condor(util.WORKSPACE_SIGNATURE_FILE,
                        util.WORKSPACE_CONFIG_FILE,
                        util.CONDOR_TEMPLATE,
                        util.TRAINING_DIR+'/')
    remote_find_trajectory(ws)
    remote_interpolate_trajectory(ws)
    remote_esitmate_clearance_volume(ws)
    remote_pickup_key_configuration(ws)

def collect_stages():
    return [ ('deploy_to_condor',
              lambda ws: ws.deploy_to_condor(util.WORKSPACE_SIGNATURE_FILE,
                                             util.WORKSPACE_CONFIG_FILE,
                                             util.CONDOR_TEMPLATE,
                                             util.TRAINING_DIR+'/')
             ),
             ('find_trajectory', remote_find_trajectory),
             ('interpolate_trajectory', remote_interpolate_trajectory),
             ('estimate_clearance_volume', remote_esitmate_clearance_volume),
             ('pickup_key_configuration', remote_pickup_key_configuration),
           ]
