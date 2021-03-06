from mcl_toolbox.utils.model_utils import ModelFitter

import unittest
from parameterized import parameterized

def test_models(
    exp_name, pid, model_list, criterion="reward", optimization_params={}
):
    mf = ModelFitter(exp_name)
    for model_index in model_list:
        optimizer = mf.construct_optimizer(model_index, pid, criterion)
        _, _, _ = optimizer.optimize(criterion, **optimization_params)
    return None


class TestModels(unittest.TestCase):
    @parameterized.expand([[{
            "optimizer": "hyperopt",
            "num_simulations": 1,
            "max_evals": 1,
        }]])
    def test_mcrl_project_models(self, optimization_params):
        """
        Tests models to make sure we didn't break anything for MCRL Project
        Takes around 15 minutes
        """
        test_models("v1.0", 0, range(6432), optimization_params=optimization_params)
        self.assertTrue(True)
