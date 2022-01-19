"""
Implementation of a Leabra Unit, reproducing the behavior of emergent 8.0.

We implement only the rate-coded version. The code is intended to be as simple
as possible to understand. It is not in any way optimized for performance.
"""
import copy

import numpy as np
import scipy.interpolate


# type of layer and correspondingly, unit behaviors
INPUT  = 0
HIDDEN = 1
OUTPUT = 2


class Unit:
    """Leabra Unit (as implemented in emergent 8.0)"""

    def __init__(self, spec=None, genre=HIDDEN, log_names=('net', 'I_net', 'v_m', 'act', 'v_m_eq', 'adapt')):
        """
        spec:  UnitSpec instance with custom values for the unit parameters.
               If None, default values will be used.
        """
        self.genre = genre  # type of Unit

        self.spec = spec
        if self.spec is None:
            self.spec = UnitSpec()

        self.log_names = log_names
        self.logs  = {name: [] for name in self.log_names}

        self.reset()

        # averages of the activity
        self.avg_ss    = self.spec.avg_init # super-short-term average
        self.avg_s     = self.spec.avg_init # short-term average
        self.avg_m     = self.spec.avg_init # medium-term average
        self.avg_l     = self.spec.avg_l_init
        self.avg_s_eff = 0.0  # linear mixing of avg_s and avg_m

    def reset(self):
        """Reset the Unit state. Called at creation, and at every trial."""
        self.ex_inputs  = []    # excitatory inputs for the next cycle
        self.logs = {name: [] for name in self.log_names}
        self.g_e     = 0                  # excitatory conductance
        self.I_net   = 0                  # net current
        self.I_net_r = self.I_net         # net current, equilibrium version (for v_m_eq)
        self.v_m     = self.spec.v_m_init # membrane potential
        self.v_m_eq  = self.v_m           # equilibrium membrane potential
                                          # (not reseted after a spike)
        self.act_ext = None               # externally forced activity (None for not forced)
        self.act     = 0                  # current activity
        self.act_nd  = self.act           # non-depressed activity # FIXME: not implemented yet
        self.act_m   = self.act           # activity at the end of the minus phase

        self.adapt   = 0     # adaptation current: causes the rate of activation
                              # to decrease over time

    @property
    def act_eq(self):
        """For rate-coded units, `act` == `act_eq`. This Unit implementation is only rate-coded."""
        return self.act

    @property
    def avg_l_lrn(self):
        return self.spec.avg_l_lrn(self)

    def cycle(self, phase, g_i=0.0, dt_integ=1):
        """Cycle the unit"""
        return self.spec.cycle(self, phase, g_i=g_i, dt_integ=dt_integ)
        # 2021-12-05 change to use dopa, adeno
        #return self.spec.cycle_da(self, phase, g_i=g_i, dt_integ=dt_integ)

    def calculate_net_in(self):
        return self.spec.calculate_net_in(self)

    @property
    def net(self):
        """Excitatory conductance."""
        return self.spec.g_bar_e * self.g_e

    def force_activity(self, act_ext):
        """Force the activity of a unit.

        The activity of the unit will remain at that value for subsequent cycles,
        until `force_activity()` is called with a different values, or until
        `add_excitatory()` is called, which will resume updating `I_net` and
        `v_m` and compute `act` based on those.
        """
        assert len(self.ex_inputs) == 0  # avoiding mistakes
        self.act_ext = act_ext # forced activity
        self.spec.force_activity(self)

        # self.act    = act  # FIXME: should the activity be delayed until the start of the next cycle?
        # self.act_nd = act


    def add_excitatory(self, inp_act):
        """Add an input for the next cycle."""
        self.ex_inputs.append(inp_act)

    def update_avg_l(self):
        return self.spec.update_avg_l(self)

    def update_logs(self):
        """Record current state. Called after each cycle."""
        for name in self.logs.keys():
            self.logs[name].append(getattr(self, name))

    def show_config(self):
        """Display the value of constants and state variables."""
        print('Parameters:')
        for name in ['dt_v_m', 'dt_net', 'g_l', 'g_bar_e', 'g_bar_l', 'g_bar_i',
                     'e_rev_e', 'e_rev_l', 'e_rev_i', 'act_thr', 'act_gain']:
            print('   {}: {:.2f}'.format(name, getattr(self.spec, name)))
        print('State:')
        for name in ['g_e', 'I_net', 'v_m', 'act', 'v_m_eq']:
            print('   {}: {:.2f}'.format(name, getattr(self, name)))



class UnitSpec:
    """Units specification.

    Each unit can have different parameters values. They don't change during
    cycles, and unless you know what you're doing, you should not change them
    after the Unit creation. The best way to proceed is to create the UnitSpec,
    modify it, and provide the spec when instantiating a Unit:

    >>> spec = UnitSpec(act_thr=0.35) # specifying parameters at instantiation
    >>> spec.bias = 0.5               # you can also do it afterward
    >>> u = Unit(spec=spec)           # creating a Unit instance

    """


    def __init__(self, **kwargs):
        # time step constants
        self.tau_net    = 1.4     # net input integration time constant (net = g_e * g_bar_e)
        self.tau_v_m    = 3.3     # v_m integration time constant
        # input channels parameters
        self.g_l        = 1.0     # leak current (constant)
        self.g_bar_e    = 1.0     # excitatory maximum conductance
        self.g_bar_l    = 0.1     # leak maximum conductance
        self.g_bar_i    = 1.0     # inhibitory maximum conductance
        # reversal potential
        self.e_rev_e    = 1.0     # excitatory
        self.e_rev_l    = 0.3     # leak
        self.e_rev_i    = 0.25    # inhibitory
        # activation function parameters
        self.act_thr    = 0.5     # threshold 2021-12-05 TAT: modulate via dopa D1 D2, adeno A1 A2
        self.c_act_thr = 0 # let original vary, this be constant; logistic(0) = 0.5
        self.act_gain   = 100     # gain
        self.noisy_act  = True    # If True, uses the noisy activation function
        self.act_sd     = 0.01    # standard deviation of the noisy gaussian #FIXME: variance or sd?
        self.act_min    = 0.0     # clamp ranges (min, max) for the activation value.
        self.act_max    = 0.95    #
        # spiking behavior
        self.spk_thr    = 1.2     # spike threshold for resetting v_m # FIXME: actually used?
        self.v_m_init   = 0.4     # init value for v_m
        self.v_m_r      = 0.3     # reset value for v_m
        self.v_m_min    = 0.0     # clamp ranges (min, max) for v_m
        self.v_m_max    = 2.0     #
        # adapt behavior
        self.adapt_on   = False   # if True, enable the adapt behavior
        self.dt_adapt   = 1/144.  # time-step constant for adapt update
        self.v_m_gain   = 0.04    # gain on v_m driving the adaptation variable
        self.spike_gain = 0.00805 # value to add to the adaptation variable after spiking
        # bias #FIXME: not implemented.
        self.bias       = 0.0
        # average parameters
        self.avg_init   = 0.15
        self.avg_ss_dt  = 0.5
        self.avg_s_dt   = 0.5
        self.avg_m_dt   = 0.1
        self.avg_l_dt   = 0.1 # computed once every trial #FIXME tau
        self.avg_l_init = 0.4
        self.avg_l_min  = 0.2
        self.avg_l_gain = 2.5
        self.avg_m_in_s = 0.1
        self.avg_lrn_min = 0.0001 # minimum avg_l_lrn value.
        self.avg_lrn_max = 0.5    # maximum avg_l_lrn value
        # dopa and adenosine
        self.r_d1 = 0.0
        self.r_d2 = 0.0
        self.r_a1 = 0.0
        self.r_a2 = 0.0

        for key, value in kwargs.items():
            assert hasattr(self, key), 'the {} parameter does not exist'.format(key)
            setattr(self, key, value)

        self._nxx1_conv = None # precomputed convolution for the noisy xx1 function

    def avg_l_lrn(self, unit):
        if unit.genre != HIDDEN:  # no self-organization for non-hidden layers
            return 0.0
        avg_fact = (self.avg_lrn_max - self.avg_lrn_min)/(self.avg_l_gain - self.avg_l_min)
        return self.avg_lrn_min + avg_fact * (unit.avg_l - self.avg_l_min)

    @property
    def dt_net(self):
        return 1.0 / self.tau_net

    @property
    def dt_v_m(self):
        return 1.0 / self.tau_v_m

    def copy(self):
        """Return a copy of the spec"""
        return copy.deepcopy(self)

    def xx1(self, v_m):
        """Compute the x/(x+1) activation function."""
        X = self.act_gain * max(v_m, 0.0)
        return X / (X + 1)

    def noisy_xx1(self, v_m):
        """Compute the noisy x/(x+1) activation function.

        The noisy x/(x+1) function is the convolution of the x/(x+1) function
        with a Gaussian with a `self.spec.act_sd` standard deviation. Here, we
        precompute the convolution as a look-up table, and interpolate it with
        the desired point every time the function is called.
        """
        if self._nxx1_conv is None:  # convolution not precomputed yet
            res = 0.001 # resolution of the precomputed array

            # computing the gaussian
            ns_rng = max(3.0 * self.act_sd, res)
            xs = np.arange(-ns_rng, ns_rng+res, res)  # x represents self.v_m
            var = max(self.act_sd, 1.0e-6)**2
            gaussian = np.exp(-xs**2 / var)   # computing unscaled guassian
            gaussian = gaussian/sum(gaussian) # normalization

            # computing xx1 function
            xs = np.arange(-2*ns_rng, 1.0 + ns_rng + res, res)  # x represents self.v_m
            X  = self.act_gain * np.maximum(xs, 0)
            xx1 = X / (X + 1)  # regular x/(x+1) function over xs

            # convolution
            conv = np.convolve(xx1, gaussian, mode='same')

            # cutting to valid range
            xs_valid = np.arange(-ns_rng, 1.0 + res, res)  # x represents self.v_m
            conv = conv[np.searchsorted(xs, xs_valid[0],  side='left'):
                        np.searchsorted(xs, xs_valid[-1], side='right')]
            assert len(xs_valid) == len(conv), '{} != {}'.format(len(xs_valid), len(conv))

            self._nxx1_conv = xs_valid, conv

        xs, conv = self._nxx1_conv
        if v_m < xs[0]:
            return 0.0
        elif xs[-1] < v_m:
            return self.xx1(v_m)
        else:
            return float(scipy.interpolate.interp1d(xs, conv, kind='linear',
                                                    fill_value='extrapolate')(v_m))


    def calculate_net_in(self, unit, dt_integ=1):
        """Calculate the net input for the unit. To execute before cycle().

        If the activity of the unit is forced, then normal external inputs are ignored, and
        net_in is set to the forced activity.
        """
        if unit.act_ext is not None:  # forced activity
            assert len(unit.ex_inputs) == 0  # avoiding mistakes
            return # see self.force_activity

        net_raw = 0.0
        if len(unit.ex_inputs) > 0:
            # computing net_raw, the total, instantaneous, excitatory input for the neuron
            net_raw = sum(unit.ex_inputs)
            unit.ex_inputs = []

        # updating net
        unit.g_e += dt_integ * self.dt_net * (net_raw - unit.g_e)  # eq 2.16


    def force_activity(self, unit):
        """Replace calls to `calculate_net_in` and `cycle` for forced activity units.

        Note that this is computed immediately when forcing a unit's activity, and in particular
        before cycling connections.
        """
        # calculate_netin
        unit.g_e = unit.act_ext / self.g_bar_e  # unit.net == unit.act
        # cycle
        unit.I_net = 0.0
        unit.act    = unit.act_ext
        unit.act_nd = unit.act_ext
        if unit.act == 0:
            unit.v_m = self.e_rev_l
        else:
            unit.v_m = self.act_thr + unit.act_ext / self.act_gain;
        unit.v_m_eq = unit.v_m


    def cycle(self, unit, phase, g_i=0.0, dt_integ=1):
        """Update activity - "tick" or "step"

        unit    :  the unit to cycle
        g_i     :  inhibitory input
        dt_integ:  integration time step, in ms.
        """
        if unit.act_ext is not None: # forced activity
            self.update_avgs(unit, dt_integ)
            unit.update_logs()
            return # see self.force_activity

        # computing I_net and I_net_r
        unit.I_net   = self.integrate_I_net(unit, g_i, dt_integ, ratecoded=False, steps=2) # half-step integration
        unit.I_net_r = self.integrate_I_net(unit, g_i, dt_integ, ratecoded=True,  steps=1) # one-step integration

        # updating v_m and v_m_eq
        unit.v_m    += dt_integ * self.dt_v_m * unit.I_net   # - unit.adapt is done on the I_net value.
        unit.v_m_eq += dt_integ * self.dt_v_m * unit.I_net_r
        #unit.v_m     = max(self.v_m_min, min(unit.v_m, self.v_m_max))

        # modulate act_thr
        

        # reseting v_m if over the threshold (spike-like behavior)
        if unit.v_m > self.act_thr: # 2021-12-05 TAT may use Dopa and Adeno to modulate act_thr!
            unit.spike = 1
            unit.v_m   = self.v_m_r
            unit.I_net = 0.0
        else:
            unit.spike = 0

        # selecting the activation function, noisy or not. (note: could also use sigmoid here)
        act_fun = self.noisy_xx1 if self.noisy_act else self.xx1

        # computing new_act, from v_m_eq (because rate-coded neuron)
        if unit.v_m_eq <= self.act_thr:
            new_act = act_fun(unit.v_m_eq - self.act_thr)
            #print('SUBTHR {} {}\n       new_act={}'.format(unit.v_m_eq, self.act_thr, new_act))
        else:
            gc_e = self.g_bar_e * unit.g_e
            gc_i = self.g_bar_i * g_i
            gc_l = self.g_bar_l * self.g_l
            g_e_thr = (  gc_i * (self.e_rev_i - self.act_thr)
                       + gc_l * (self.e_rev_l - self.act_thr)
                       - unit.adapt + self.bias) / (self.act_thr - self.e_rev_e)

            new_act = act_fun(gc_e - g_e_thr)  # gc_e == unit.net
            #print('ABVTHR {} net={} {}\n       new_act={}'.format(unit.v_m_eq, gc_e, g_e_thr, new_act))


        # updating activity
        unit.act_nd += dt_integ * self.dt_v_m * (new_act - unit.act_nd)
        #print('FASTCYV act={}'.format(unit.act_nd))

        #unit.act_nd = max(self.act_min, min(unit.act_nd, self.act_max))
        unit.act = unit.act_nd # FIXME: implement stp

        # updating adaptation
        if self.adapt_on:
            unit.adapt += dt_integ * (
                            self.dt_adapt * (self.v_m_gain * (unit.v_m - self.e_rev_l) - unit.adapt)
                            + unit.spike * self.spike_gain
                          )

        # if phase == 'minus':
        self.update_avgs(unit, dt_integ)
        unit.update_logs()

    def cycle_da(self, unit, phase, g_i=0.0, dt_integ=1):
        """Update activity - "tick" or "step"

        2021-12-05: TAT updated with dopa, adeno support    

        unit    :  the unit to cycle
        g_i     :  inhibitory input
        dt_integ:  integration time step, in ms.
        """
        if unit.act_ext is not None: # forced activity
            self.update_avgs(unit, dt_integ)
            unit.update_logs()
            return # see self.force_activity

        # computing I_net and I_net_r
        unit.I_net   = self.integrate_I_net(unit, g_i, dt_integ, ratecoded=False, steps=2) # half-step integration
        unit.I_net_r = self.integrate_I_net(unit, g_i, dt_integ, ratecoded=True,  steps=1) # one-step integration

        # updating v_m and v_m_eq
        unit.v_m    += dt_integ * self.dt_v_m * unit.I_net   # - unit.adapt is done on the I_net value.
        unit.v_m_eq += dt_integ * self.dt_v_m * unit.I_net_r
        #unit.v_m     = max(self.v_m_min, min(unit.v_m, self.v_m_max))

        # 2021-12-05 TAT: modulate act_thr
        unit.act_thr = self.logistic(self.c_act_thr - unit.r_d1 + unit.r_a1 + unit.r_d2 - unit.r_a2)
        

        # reseting v_m if over the threshold (spike-like behavior)
        if unit.v_m > unit.act_thr: # 2021-12-05 TAT may use Dopa and Adeno to modulate act_thr!
            unit.spike = 1
            unit.v_m   = self.v_m_r
            unit.I_net = 0.0
        else:
            unit.spike = 0

        # selecting the activation function, noisy or not. (note: could also use sigmoid here)
        act_fun = self.noisy_xx1 if self.noisy_act else self.xx1

        # computing new_act, from v_m_eq (because rate-coded neuron)
        if unit.v_m_eq <= unit.act_thr:
            new_act = act_fun(unit.v_m_eq - unit.act_thr)
            #print('SUBTHR {} {}\n       new_act={}'.format(unit.v_m_eq, self.act_thr, new_act))
        else:
            gc_e = self.g_bar_e * unit.g_e
            gc_i = self.g_bar_i * g_i
            gc_l = self.g_bar_l * self.g_l
            g_e_thr = (  gc_i * (self.e_rev_i - unit.act_thr)
                       + gc_l * (self.e_rev_l - unit.act_thr)
                       - unit.adapt) / (self.act_thr - self.e_rev_e)

            new_act = act_fun(gc_e - g_e_thr)  # gc_e == unit.net
            #print('ABVTHR {} net={} {}\n       new_act={}'.format(unit.v_m_eq, gc_e, g_e_thr, new_act))


        # updating activity
        unit.act_nd += dt_integ * self.dt_v_m * (new_act - unit.act_nd)
        #print('FASTCYV act={}'.format(unit.act_nd))

        #unit.act_nd = max(self.act_min, min(unit.act_nd, self.act_max))
        unit.act = unit.act_nd # FIXME: implement stp

        # updating adaptation
        if self.adapt_on:
            unit.adapt += dt_integ * (
                            self.dt_adapt * (self.v_m_gain * (unit.v_m - self.e_rev_l) - unit.adapt)
                            + unit.spike * self.spike_gain
                          )

        # if phase == 'minus':
        self.update_avgs(unit, dt_integ)
        unit.update_logs()


    def integrate_I_net(self, unit, g_i, dt_integ, ratecoded=True, steps=1):
        """Integrate and returns I_net for the provided v_m

        :param steps:  number of intermediary integration steps.
        """
        assert steps >= 1

        gc_e = self.g_bar_e * unit.g_e
        gc_i = self.g_bar_i * g_i
        gc_l = self.g_bar_l * self.g_l
        v_m_eff = unit.v_m_eq if ratecoded else unit.v_m

        for _ in range(steps):
            I_net = (  gc_e * (self.e_rev_e - v_m_eff)
                     + gc_i * (self.e_rev_i - v_m_eff)
                     + gc_l * (self.e_rev_l - v_m_eff)
                     - unit.adapt
                      + self.bias)
            v_m_eff += dt_integ/steps * self.dt_v_m * I_net

        return I_net


    def update_avgs(self, unit, dt_integ):
        """Update all averages except long-term, at the end of every cycle."""
        unit.avg_ss += dt_integ * self.avg_ss_dt * (unit.act_nd - unit.avg_ss)
        unit.avg_s  += dt_integ * self.avg_s_dt  * (unit.avg_ss - unit.avg_s )
        unit.avg_m  += dt_integ * self.avg_m_dt  * (unit.avg_s  - unit.avg_m )
        unit.avg_s_eff = self.avg_m_in_s * unit.avg_m + (1 - self.avg_m_in_s) * unit.avg_s
        # print('avg_s_eff', unit.avg_s_eff)

    def update_avg_l(self, unit):
        """Update the long-term average.

        Called at the end of every trial (*not every cycle*).
        """
        unit.avg_l += self.avg_l_dt * (self.avg_l_gain * unit.avg_m - unit.avg_l)
        unit.avg_l = max(unit.avg_l, self.avg_l_min)

        # if unit.avg_m > 0.2: # FIXME: 0.2 is a magic number here
        #     unit.avg_l += self.avg_l_dt * (self.avg_l_gain - unit.avg_l)
        # else:
        #     unit.avg_l += self.avg_l_dt * (self.avg_l_min - unit.avg_l)
        # unit.avg_l = 3

    def set_D1(self, ratio):
        """Set the percentage of D1 activation that modulates 
            activation threshold.

            2021-12-05: this could also be set by calculation from
            a density, given some affinity
        """
        self.r_d1 = ratio
    def set_D2(self, ratio):
        """Set the percentage of D2 activation that modulates 
            activation threshold.

            2021-12-05: this could also be set by calculation from
            a density, given some affinity
        """
        self.r_d2 = ratio
    def set_A1(self, ratio):
        """Set the percentage of A1 activation that modulates 
            activation threshold.

            2021-12-05: this could also be set by calculation from
            a density, given some affinity
        """
        self.r_a1 = ratio
    def set_A2(self, ratio):
        """Set the percentage of A1 activation that modulates 
            activation threshold.

            2021-12-05: this could also be set by calculation from
            a density, given some affinity
        """
        self.r_a2 = ratio

    def logistic(self, val):
        return 1.0/(1+exp(-val))