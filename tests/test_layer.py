import unittest
import copy

import numpy as np

import data

import dotdot  # pylint: disable=unused-import
import leabra



class LayerTestAPI(unittest.TestCase):


    def test_layer_inputs(self):
        """Check that adding inputs works as expected."""
        layer = leabra.Layer(3)
        layer.spec.g_i = 0.0  # no inhibition

        for _ in range(20):
            layer.add_excitatory([0.0, 0.5, 1.0])
            layer.cycle()

        for _ in range(100):
            layer.add_excitatory([0.0, 0.5, 1.0])
            layer.cycle()
            acts = layer.activities
            self.assertEqual(acts[0], 0.0)
            self.assertTrue(np.allclose(0.5, acts[1], rtol=1.0, atol=1e-01))
            self.assertTrue(np.allclose(0.9, acts[1], rtol=1.0, atol=1e-01))


    def test_layer_forced(self):
        """Check forcing of layer's activities."""
        layer = leabra.Layer(5)
        layer.force_activity([0.0, 0.25, 0.50, 0.75, 1.0])

        for _ in range(100):
            layer.cycle()
            self.assertEqual(layer.activities, [0.0, 0.25, 0.50, 0.75, 1.0])



class LayerTestsBehavior(unittest.TestCase):
    """Check that the Layer behaves as they should.

    The checks are concerned with consistency with the equations that define the
    layer's behavior. These test should pass on the emergent implementation as
    well.
    """

    def test_emergent_layer(self):
        """Test quantitative equivalence with emergent on a basic layer inhibition project."""
        emergent_data = data.parse_unit('layer_fffb.dat')

        unit_spec = leabra.UnitSpec(adapt_on=True, noisy_act=True,
                                    g_bar_e=0.3, g_bar_l=0.3, g_bar_i=1.0,
                                    act_thr=0.5, act_gain=40, act_sd=0.01)
        layer_spec = leabra.LayerSpec(g_i=0.4, ff=1.0, fb=0.5)
        connection_spec = leabra.ConnectionSpec(proj='1to1',
                                                rnd_mean=1.0, rnd_var=0.0)

        src_layer = leabra.Layer(10, spec=layer_spec, unit_spec=unit_spec)
        dst_layer = leabra.Layer(10, spec=layer_spec, unit_spec=unit_spec)

        connection0 = leabra.Connection(src_layer, dst_layer,
                                        spec=connection_spec)
        connection0.wt_scale_rel_eff = 1.0 # because we don't use the Network that initialize this
                                           # value here.

        input_pattern = 5 * [1.0, 0.0]

        for i in range(200):
            if ((i >= 10) and (i < 160)):
                src_layer.force_activity(input_pattern)
            else:
                src_layer.force_activity(10 * [0.0])
            src_layer.cycle()
            connection0.cycle()
            dst_layer.cycle()


        check = True
        for name in dst_layer.units[0].logs.keys():
            for t, (py, em) in enumerate(zip(dst_layer.units[0].logs[name], emergent_data[name])):
                if not np.allclose(py, em, rtol=1e-05, atol=1e-07):
                    print('{}:{:3d} [py] {:.10f} != {:.10f} [emergent]'.format(
                            name, t,   py,        em))
                    check = False

        self.assertTrue(check)


if __name__ == '__main__':
    unittest.main()
