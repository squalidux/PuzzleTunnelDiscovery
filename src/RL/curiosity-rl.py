'''
    curiosity-rl.py

    Curiosity driven RL Framework
'''

from __future__ import print_function
import tensorflow as tf
import numpy as np
from scipy.misc import imsave # Unused ... now
import time
import uw_random
import config
import pyosr
import rlargs
import a2c
import random
from multiprocessing import Process
from six.moves import queue,input
import qtrainer
import ctrainer
import iftrainer
import curiosity
import rlsampler

AlphaPuzzle = curiosity.RigidPuzzle
CuriosityRL = curiosity.CuriosityRL

def create_trainer(args, global_step, batch_normalization):
    '''
    if len(args.egreedy) != 1 and len(args.egreedy) != args.threads:
        assert False,"--egreedy should have only one argument, or match the number of threads"
    '''
    advcore = CuriosityRL(learning_rate=1e-3, args=args, batch_normalization=batch_normalization)
    bnorm = batch_normalization
    if args.train == 'a2c':
        if args.threads > 1:
            TRAINER = a2c.A2CTrainerDTT
        else:
            TRAINER = a2c.A2CTrainer
        train_everything = False if args.viewinitckpt else True
        trainer = TRAINER(
                advcore=advcore,
                tmax=args.batch,
                gamma=args.GAMMA,
                # gamma=0.5,
                learning_rate=1e-3,
                ckpt_dir=args.ckptdir,
                global_step=global_step,
                batch_normalization=bnorm,
                total_number_of_replicas=args.localcluster_size,
                period=args.period,
                LAMBDA=args.LAMBDA,
                train_everything=train_everything)
    elif args.train == 'QwithGT' or args.qlearning_with_gt or args.train == 'QandFCFE':
        trainer = qtrainer.QTrainer(
                advcore=advcore,
                batch=args.batch,
                learning_rate=1e-4,
                ckpt_dir=args.ckptdir,
                period=args.period,
                global_step=global_step,
                train_fcfe=(args.train == 'QandFCFE'))
        if args.qlearning_gt_file:
            trainer.attach_gt(args.qlearning_gt_file)
    elif args.train == 'curiosity':
        trainer = ctrainer.CTrainer(
                advcore=advcore,
                batch=args.batch,
                learning_rate=1e-4,
                ckpt_dir=args.ckptdir,
                period=args.period,
                global_step=global_step)
        trainer.set_action_set(args.actionset)
        trainer.limit_samples_to_use(args.sampletouse)
        if args.samplein != '':
            trainer.attach_samplein(args.samplein)
    elif args.train == 'InF':
        # TODO: allow samples from files
        # Note: precomputed samples have one problem:
        #       Actions cannot be translated to new permutations
        trainer = iftrainer.IFTrainer(
                advcore=advcore,
                batch=args.batch,
                learning_rate=1e-4,
                ckpt_dir=args.ckptdir,
                period=args.period,
                global_step=global_step)
    elif args.train == 'Ionly':
        # SAN Check: Only optimize agains Inverse Model
        # Should work pretty well after loading pretrained weights
        trainer = iftrainer.ITrainer(
                advcore=advcore,
                batch=args.batch,
                learning_rate=1e-4,
                ckpt_dir=args.ckptdir,
                period=args.period,
                global_step=global_step)
    else:
        assert False, '--train {} not implemented yet'.format(args.train)
    return trainer, advcore

#
# IEngine: wrapper over distributed training and non-distributed evaluation
#
class IEngine(object):
    def __init__(self, args):
        self.args = args
        if 'gpu' in args.device:
            session_config = tf.ConfigProto()
            session_config.gpu_options.allow_growth = True
        else:
            session_config = None
        self.session_config = session_config

    def run(self, sess):
        pass

class ParamServer(IEngine):
    def __init__(self, args, server):
        super(ParamServer, self).__init__(args)
        self.server = server

    def run(self):
        self.server.join()

class TEngine(IEngine):
    def __init__(self, args):
        super(TEngine, self).__init__(args)
        self.mts_master = ''
        self.mts_is_chief = True

    def get_hooks(self):
        hooks = [tf.train.StopAtStepHook(last_step=args.iter)]

        if self.args.viewinitckpt:
            class PretrainLoader(tf.train.SessionRunHook):
                def __init__(self, advcore, ckpt):
                    self.advcore = advcore
                    self.ckpt = ckpt

                def after_create_session(self, session, coord):
                    self.advcore.load_pretrain(session, self.ckpt)
                    print("PretrainLoader.after_create_session called")

            ckpt = tf.train.get_checkpoint_state(checkpoint_dir=self.args.ckptdir)
            # Do NOT load the pretrained weights if checkpoint exists.
            if not (ckpt and ckpt.model_checkpoint_path):
                hooks += [PretrainLoader(self.advcore, self.args.viewinitckpt)]

        return hooks

    def _create_trainer(self, args):
        self.bnorm = tf.placeholder(tf.bool, shape=()) if args.batchnorm else None
        self.trainer, self.advcore = create_trainer(args, global_step, batch_normalization=bnorm)

    def run(self):
        hooks = self.get_hooks()
        with tf.train.MonitoredTrainingSession(master=self.mts_master,
                                               is_chief=self.mts_is_chief,
                                               checkpoint_dir=args.ckptdir,
                                               config=self.session_config,
                                               hooks=hooks) as mon_sess:
            while not mon_sess.should_stop():
                self.trainer.train(self.envir, mon_sess, self.tid)

class CentralizedTrainer(TEngine):
    def __init__(self, args):
        super(CentralizedTrainer, self).__init__(args)
        self.envir = AlphaPuzzle(args, 0, 0)
        self._create_trainer(args)

'''
DistributedTrainer:
    Enable the distribution by:
        1. Create model under different tf.device
        2. set self.mts_* to enable distributed MonitoredTrainingSession in TEngine.run
'''
class DistributedTrainer(TEngine):
    def __init__(self, args, cluster, server):
        super(DistributedTrainer, self).__init__(args)
        self.tid = args.task_index
        self.envir = AlphaPuzzle(args, self.tid, self.tid)
        self.cluster = cluster
        self.server = server
        # Enable distributed training
        with tf.device(tf.train.replica_device_setter(
            worker_device="/job:worker/task:{}".format(args.task_index),
            cluster=cluster)):
            self._create_trainer(args)
        self.mts_master = self.server.target
        self.mts_is_chief = (args.task_index == 0)

class Evaluator(IEngine):
    def __init__(self, args):
        super(Evaluator, self).__init__(args)
        self.gs = tf.contrib.framework.get_or_create_global_step()
        self.g = tf.get_default_graph()
        self.player = rlsampler.create_visualizer(args, self.g, self.gs)

    def run(self):
        args = self.args
        assert args.ckptdir, "--ckptdir is mandatory when --eval"
        saver = tf.train.Saver()
        with tf.Session(config=self.session_config) as sess:
            tf.get_default_graph().finalize()
            ckpt = tf.train.get_checkpoint_state(checkpoint_dir=args.ckptdir)
            print('ckpt {}'.format(ckpt))
            if ckpt and ckpt.model_checkpoint_path:
                saver.restore(sess, ckpt.model_checkpoint_path)
                accum_epoch = sess.run(self.gs)
                print('Restored!, global_step {}'.format(accum_epoch))
            self.player.attach(sess)
            self.player.play()

def curiosity_create_engine(args):
    if args.eval:
        return Evaluator(args)
    cluster_dict = rlutil.create_cluster_dic(args)
    if cluster_dict is None:
        return CentralizedTrainer(args)
    # Create a cluster from the parameter server and worker hosts.
    cluster = tf.train.ClusterSpec(cluster_dict)
    # Create and start a server for the local task.
    server = tf.train.Server(cluster,
            job_name=args.job_name,
            task_index=args.task_index)
    if args.job_name == 'ps':
        engine = ParamServer(args, server)
    else:
        assert args.job_name == 'worker', "--job_name should be either ps or worker"
        engine = DistributedTrainer(args, cluster, server)
    return engine

'''
Main Function:
    1. Create TF graphs by creating Facade class TrainingManager
        - This facade class will create corresponding training class on demand
    1.a Alternatively, call rlsampler.create_visualizer to evaluate the traing results
    2. Initialize TF sessions and TF Saver
    3. Restore from checkpoints on demand
    3. Call TrainingManager for some iterations on demand
'''
def process_main(args):
    '''
    CAVEAT: WITHOUT ALLOW_GRWTH, WE MUST CREATE RENDERER BEFORE CALLING ANY TF ROUTINE
    '''
    pyosr.init()
    # Create Training/Evaluation Engine
    engine = curiosity_create_engine(args)
    # Engine execution
    engine.run()

def curiosity_main(args):
    if args.localcluster_size <= 0 and not args.ps_hosts:
        process_main(args)
        return
    # Distributed execution
    args_list = rlutil.assemble_distributed_arguments(args)
    procs = [Process(target=process_main, args=(a)) for a in args_list]
    for p in procs:
        p.start()
    for p in procs:
        p.join()

if __name__ == '__main__':
    args = rlargs.parse()
    if args.continuetrain:
        if args.samplein:
            print('--continuetrain is incompatible with --samplein')
            exit()
        if args.batching:
            print('--continuetrain is incompatible with --batching')
            exit()
    if -1 in args.actionset:
        args.actionset = [i for i in range(12)]
    assert args.threads == 1, "--threads has no effect in distributed training"
    args.total_sample = args.iter * args.threads
    args.total_epoch = args.total_sample / args.samplebatching
    print("> Arguments {}".format(args))
    curiosity_main(args)
