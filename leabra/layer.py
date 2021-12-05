import numpy as np

from .unit import Unit, INPUT, HIDDEN, OUTPUT


class Layer:
    """Leabra Layer class"""

    def __init__(self, size, spec=None, unit_spec=None, genre=HIDDEN, name=None):
        """
        size     :  Number of units in the layer.
        spec     :  LayerSpec instance with custom values for the parameter of
                    the layer. If None, default values will be used.
        unit_spec:  UnitSpec instance with custom values for the parameters of
                    the units of the layer. If None, default values will be used.

        2021-12-05 TAT: this is like a "population" or "ensemble" of neurons
        """
        self.genre = genre  # type of layer

        self.name = name
        self.spec = spec
        if self.spec is None:
            self.spec = LayerSpec()
        #!#assert self.spec.inhib.lower() in self.spec.legal_inhib

        self.units = [Unit(spec=unit_spec, genre=genre) for _ in range(size)]

        self.gc_i = 0.0  # inhibitory conductance
        self.ffi  = 0.0  # feedforward component of inhibition
        self.fbi  = 0.0  # feedback component of inhibition

        self.avg_act       = 0.0  # average activity, computed after every cycle.
        self.avg_act_p_eff = self.spec.avg_act_targ_init

        self.from_connections = [] # connections from this layer
        self.to_connections   = [] # connections to this layer

        self.logs = {'gc_i': []}

    def trial_init(self):
        """Initialize the layer for a new trial. Reset all units, decays fbi and ffi."""
        self.spec.trial_init(self)

    @property
    def activities(self):
        """Return the matrix of the units's activities"""
        return [u.act for u in self.units]

    @property
    def g_e(self):
        """Return the matrix of the units's net exitatory input"""
        return [u.g_e for u in self.units]

    def update_logs(self):
        """Record current state. Called after each cycle."""
        self.logs['gc_i'].append(self.gc_i)

    def force_activity(self, activities):
        """Set the units's activities equal to the inputs."""
        assert len(activities) == len(self.units)
        for u, act in zip(self.units, activities):
            u.force_activity(act)

    def add_excitatory(self, inputs):
        """Add excitatory inputs to the layer's units."""
        assert len(inputs) == len(self.units)
        for u, net_raw in zip(self.units, inputs):
            u.add_excitatory(net_raw)

    def cycle(self, phase):
        self.spec.cycle(self, phase)

    def show_config(self):
        """Display the value of constants and state variables."""
        print('Parameters:')
        for name in ['fb_dt', 'ff0', 'ff', 'fb', 'g_i']:
            print('   {}: {:.2f}'.format(name, getattr(self.spec, name)))
        print('State:')
        for name in ['gc_i', 'fbi', 'ffi']:
            print('   {}: {:.2f}'.format(name, getattr(self, name)))


class LayerSpec:
    """Layer parameters"""

    def __init__(self, **kwargs):
        """Initialize a LayerSpec"""
        self.lay_inhib = True # activate inhibition?

        # time step constants:
        self.fb_dt = 1/1.4  # Integration constant for feed back inhibition

        # weighting constants
        self.fb    = 1.0    # feedback scaling of inhibition
        self.ff    = 1.0    # feedforward scaling of inhibition
        self.g_i   = 1.8    # inhibition multiplier

        self.trial_decay = 1.0  # decay factor for fbi and ffi. If 1.0, fbi and ffi will be reset to
                                # 0 at the start of every trial

        # thresholds:
        self.ff0 = 0.1

        # average activity
        self.avg_act_targ_init = 0.2    # target for adapting inhibition and
                                        # initial estimated average value level
        self.avg_act_adjust    = 1.0    # avg_p_act_eff = avg_act_adjust * avg_p_act
        self.avg_act_fixed     = False  # if True, `avg_act_p_eff` is constant, =`avg_act_targ_init`
        self.avg_act_use_first = False  # override targ_init value with the first estimation.
        self.avg_act_tau       = False  # time constant for integrating act_p_avg

        for key, value in kwargs.items():
            assert hasattr(self, key) # making sure the parameter exists.
            setattr(self, key, value)

        self.cycle_count = 0

    def _inhibition(self, layer):
        """Compute the layer inhibition"""
        if self.lay_inhib:
            # Calculate feed forward inhibition
            netin = [u.g_e for u in layer.units]
            # if layer.genre == OUTPUT and self.cycle_count < 300:
            #     print(self.cycle_count, netin)
            layer.ffi = self.ff * max(0, np.mean(netin) - self.ff0)

            # Calculate feed back inhibition
            # if layer.genre == OUTPUT and self.cycle_count < 300:
            #     print(self.cycle_count, 'layer.avg_act ', layer.avg_act)
            layer.fbi += self.fb_dt * (self.fb * layer.avg_act - layer.fbi)

            # if layer.genre == OUTPUT and self.cycle_count < 300:
            #     print('gc_i ',  self.g_i * (layer.ffi + layer.fbi))
            #     print('gc_i ',  self.g_i * (layer.ffi + layer.fbi), layer.ffi, layer.fbi)
            return self.g_i * (layer.ffi + layer.fbi)
        else:
            return 0.0

    def cycle(self, layer, phase):
        """Cycle the layer, and all the units in it."""

        # calculate net inputs for this layer
        for u in layer.units:
            u.calculate_net_in()

        # update the state of the layer
        if phase == 'minus':
            layer.gc_i = self._inhibition(layer)
        # if layer.genre == OUTPUT:
        #     print(self.cycle_count, layer.gc_i)
        for u in layer.units:
            u.cycle(phase, g_i=layer.gc_i)

        layer.avg_act = np.mean(layer.activities)

        layer.update_logs()
        self.cycle_count += 1

    def trial_init(self, layer):
        for u in layer.units:
            u.reset()
        layer.ffi -= self.trial_decay * layer.ffi
        layer.fbi -= self.trial_decay * layer.fbi
