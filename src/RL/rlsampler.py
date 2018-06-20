from curiosity import CuriosityRL
from curiosity import RigidPuzzle as AlphaPuzzle
import pyosr
import numpy as np
from rlreanimator import reanimate
import uw_random

class RLVisualizer(object):
    def __init__(self, args, g, global_step):
        self.args = args
        self.dpy = pyosr.create_display()
        self.ctx = pyosr.create_gl_context(self.dpy)
        self.envir = AlphaPuzzle(args, 0)
        self.envir.egreedy = 0.995
        self.advcore = CuriosityRL(learning_rate=1e-3, args=args)
        self.advcore.softmax_policy # Create the tensor
        self.gview = 0 if args.obview < 0 else args.obview
        self.envir.enable_perturbation()

    def attach(self, sess):
        self.sess = sess

class PolicyPlayer(RLVisualizer):
    def __init__(self, args, g, global_step):
        super(PolicyPlayer, self).__init__(args, g, global_step)

    def play(self):
        reanimate(self)

    def __iter__(self):
        envir = self.envir
        sess = self.sess
        advcore = self.advcore
        reaching_terminal = False
        pprefix = "[0] "
        while True:
            rgb,_ = envir.vstate
            yield rgb[self.gview] # First view
            if reaching_terminal:
                print("##########CONGRATS TERMINAL REACHED##########")
                envir.reset()
            policy = advcore.evaluate([envir.vstate], sess, [advcore.softmax_policy])
            policy = policy[0][0]
            action = advcore.make_decision(envir, policy, pprefix)
            print("PolicyPlayer pol {}".format(policy))
            print("PolicyPlayer Action {}".format(action))
            nstate,reward,reaching_terminal,ratio = envir.peek_act(action, pprefix=pprefix)
            envir.qstate = nstate

class QPlayer(RLVisualizer):
    def __init__(self, args, g, global_step):
        super(QPlayer, self).__init__(args, g, global_step)
        if args.permutemag > 0:
            self.envir.enable_perturbation()
        if args.samplein: # User can feed samples through samplein
            self.gt = np.load(args.samplein)
            self.gt_iter = 0
        else:
            self.gt = None

    def render(self, envir, state):
        envir.qstate = state
        return envir.vstate

    def play(self):
        if self.args.sampleout:
            self._sample()
        else:
            self._play()

    def _sample_mini_batch(self, batch):
        if self.gt is None:
            return [uw_random.gen_unit_init_state(envir.r) for i in range(args.batch)]
        states = np.take(self.gt['V'],
                indices=range(self.gt_iter, self.gt_iter + batch),
                axis=0, mode='wrap')
        self.gt_iter += batch
        return states

    def _sample(self):
        Q = [] # list of states
        V = [] # list of numpy array of batched values
        args = self.args
        sess = self.sess
        advcore = self.advcore
        envir = self.envir
        assert args.iter % args.batch == 0, "presumably --iter is dividable by --batch"
        for i in range(args.iter/args.batch):
            states = self._sample_mini_batch(args.batch)
            Q += states
            images = [self.render(envir, state) for state in states]
            batch_rgb = [image[0] for image in images]
            batch_dep = [image[1] for image in images]
            dic = {
                    advcore.rgb_1: batch_rgb,
                    advcore.dep_1: batch_dep,
                  }
            values = sess.run(advcore.value, feed_dict=dic)
            values = np.reshape(values, [-1]) # flatten
            V.append(values)
        Q = np.array(Q)
        V = np.concatenate(V)
        np.savez(args.sampleout, Q=Q, V=V)

    def _play(self):
        reanimate(self)

    def __iter__(self):
        args = self.args
        sess = self.sess
        advcore = self.advcore
        envir = self.envir
        envir.enable_perturbation()
        envir.reset()
        current_value = -1
        TRAJ = []
        while True:
            TRAJ.append(envir.qstate)
            yield envir.vstate[0][args.obview] # Only RGB
            NS = []
            images = []
            # R = []
            T = []
            TAU = []
            state = envir.qstate
            print("> Current State {}".format(state))
            for action in range(uw_random.DISCRETE_ACTION_NUMBER):
                envir.qstate = state # IMPORTANT: Restore the state to unpeeked condition
                nstate, reward, terminal, ratio = envir.peek_act(action)
                envir.qstate = nstate
                NS.append(nstate)
                T.append(terminal)
                TAU.append(ratio)
                image = envir.vstate
                images.append(image)
            batch_rgb = [image[0] for image in images]
            batch_dep = [image[1] for image in images]
            dic = {
                    advcore.rgb_1: batch_rgb,
                    advcore.dep_1: batch_dep,
                  }
            values = sess.run(advcore.value, feed_dict=dic)
            values = np.reshape(values, [-1]) # flatten
            best = np.argmax(values, axis=0)
            print("> Current Values {}".format(values))
            print("> Taking Action {} RATIO {}".format(best, TAU[best]))
            print("> NEXT State {} Value".format(NS[best], values[best]))
            envir.qstate = NS[best]
            should_reset = False
            if current_value > values[best] or TAU[best] == 0.0:
                input("FATAL: Hit Local Maximal! Press Enter to restart")
                should_reset = True
            else:
                current_value = values[best]
            if T[best]:
                input("DONE! Press Enter to restart ")
                should_reset = True
            if should_reset:
                fn = input("Enter the filename to save the trajectory ")
                if fn:
                    TRAJ.append(envir.qstate)
                    TRAJ = np.array(TRAJ)
                    np.savez(fn, TRAJ=TRAJ, SINGLE_PERM=envir.get_perturbation())
                envir.reset()
                current_value = -1
                TRAJ = []

class CuriositySampler(RLVisualizer):
    def __init__(self, args, g, global_step):
        super(CuriositySampler, self).__init__(args, g, global_step)
        assert args.visualize == 'curiosity', '--visualize must be curiosity'
        assert args.curiosity_type == 1, "--curiosity_type should be 1 if --visualize is enabled"
        assert args.sampleout != '', '--sampleout must be enabled for --visualize curiosity'

    def play(self):
        args = self.args
        sess = self.sess
        advcore = self.advcore
        envir = self.envir
        samples= []
        curiosities_by_action = [ [] for i in range(uw_random.DISCRETE_ACTION_NUMBER) ]
        for i in range(args.iter):
            state = uw_random.gen_unit_init_state(envir.r)
            envir.qstate = state
            samples.append(state)
            for action in range(uw_random.DISCRETE_ACTION_NUMBER):
                nstate, reward, terminal, ratio = envir.peek_act(action)
                areward = advcore.get_artificial_reward(envir, sess,
                        state, action, nstate, ratio)
                curiosities_by_action[action].append(areward)
        samples = np.array(samples)
        curiosity = np.array(curiosities_by_action)
        np.savez(args.sampleout, Q=samples, C=curiosity)

def create_visualizer(args, g, global_step):
    if args.qlearning_with_gt:
        # assert args.sampleout, "--sampleout is required to store the samples for --qlearning_with_gt"
        assert args.iter > 0, "--iter needs to be specified as the samples to generate"
        # assert False, "Evaluating of Q Learning is not implemented yet"
        return QPlayer(args, g, global_step)
    elif args.visualize == 'policy':
        return PolicyPlayer(args, g, global_step)
    elif args.visualize == 'curiosity':
        return CuriositySampler(args, g, global_step)
    assert False, '--visualize {} is not implemented yet'.format(args.visualize)