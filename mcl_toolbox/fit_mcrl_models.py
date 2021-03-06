import sys
import ast

from pathlib import Path
import random

from mcl_toolbox.utils.learning_utils import create_dir
from mcl_toolbox.utils.model_utils import ModelFitter

"""
Run this using: 
python3 fit_mcrl_models.py <exp_name> <model_index> <optimization_criterion> <pid> <string of other parameters>
<optimization_criterion> can be ["pseudo_likelihood", "mer_performance_error", "performance_error", "clicks_overlap"]
Example: python3 fit_mcrl_models.py v1.0 1 pseudo_likelihood 1 "{\"plotting\":True, \"optimization_params\" : 
{\"optimizer\":\"hyperopt\", \"num_simulations\": 2, \"max_evals\": 2}}"
"""


# todo: not all optimization methods work with all models. Need to add this somewhere in the code
# Likelihood computation is currently available for all reinforce and lvoc models
#
# TODO: Give right strategy weights to RSSL model for likelihood computation


def fit_model(
        exp_name,
        pid,
        model_index,
        optimization_criterion,
        optimization_params=None,
        exp_attributes=None,
        sim_params=None,
        simulate=True,
        plotting=False,
        data_path=None
):
    """

    :param exp_name: experiment name, which is the folder name of the experiment in ../data/human/
    :param pid: participant id, as int
    :param model_index: model index, as displayed in rl_models.csv
    :param optimization_criterion: as string, choose one of: ["pseudo_likelihood", "mer_performance_error", "performance_error"]
    :param optimization_params: parameters for ParameterOptimizer.optimize, passed in as a dict
    :return:
    """

    # create directory to save priors in
    parent_directory = Path(__file__).resolve().parents[1]
    prior_directory = parent_directory.joinpath(f"results/mcrl/{exp_name}_priors")
    create_dir(prior_directory)

    model_info_directory = None
    plot_directory = None
    if simulate:
        # and directory to save fit model info in
        model_info_directory = parent_directory.joinpath(
            f"results/mcrl/{exp_name}_data"
        )
        create_dir(model_info_directory)
        if plotting:
            # add directory for reward plots, if plotting
            plot_directory = parent_directory.joinpath(f"results/mcrl/{exp_name}_plots")
            create_dir(plot_directory)

    mf = ModelFitter(exp_name, exp_attributes=exp_attributes, data_path=data_path)
    res, prior, obj_fn = mf.fit_model(
        model_index,
        pid,
        optimization_criterion,
        optimization_params,
        params_dir=prior_directory,
    )
    if simulate:
        mf.simulate_params(
            model_index,
            res[0],
            pid=pid,
            sim_dir=model_info_directory,
            plot_dir=plot_directory,
            sim_params=sim_params,
        )


if __name__ == "__main__":
    exp_name = sys.argv[1]
    model_index = int(sys.argv[2])
    optimization_criterion = sys.argv[3]
    pid = int(sys.argv[4])
    other_params = {}
    if len(sys.argv)>5:
        other_params = ast.literal_eval(sys.argv[5])
    else:
        other_params = {}

    if "exp_attributes" not in other_params:
        exp_attributes = {
            "exclude_trials": None,  # Trials to be excluded
            "block": None,  # Block of the experiment
            "experiment": None  # Experiment object can be passed directly with
            # pipeline and normalized features attached
        }
        other_params["exp_attributes"] = exp_attributes

    if "optimization_params" not in other_params:
        optimization_params = {
            "optimizer": "hyperopt",
            "num_simulations": 30,
            "max_evals": 200
        }
        other_params["optimization_params"] = optimization_params

    fit_model(
        exp_name=exp_name,
        pid=pid,
        model_index=model_index,
        optimization_criterion=optimization_criterion,
        **other_params,
    )
