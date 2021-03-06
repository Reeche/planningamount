import sys
from collections import defaultdict

import numpy as np
from mcl_toolbox.env.generic_mouselab import GenericMouselabEnv
from mcl_toolbox.utils.planning_strategies import strategy_dict
from mcl_toolbox.global_vars import structure

from mcl_toolbox.utils import learning_utils, distributions

sys.modules["learning_utils"] = learning_utils
sys.modules["distributions"] = distributions

"""
This file allows you to simulate the strategies given the environment and condition
v1.0: increasing_variance
c1.1: constant_variance
c2.1_dec: decreasing_variance

Format: python3 calculate_strategy_score.py <exp_num> <num_runs> <cost> <reward_level>
Example: python3 calculate_strategy_score.py c1.1 200000 1 low_constant

// condition 0: training_trial_high_variance_low_click_cost --> click a lot
python3 calculate_strategy_score.py high_variance_low_cost 300000 1 high_variance_low_cost

// condition 1: training_trial_low_variance_high_click_cost -- click nothing
python3 calculate_strategy_score.py low_variance 300000 5 low_variance

// condition 2: training_trial_high_variance_high_click_cost --> unclear
python3 calculate_strategy_score.py high_variance_high_cost 300000 5 high_variance_high_cost

// condition 3: training_trial_low_variance_low_click_cost --> unclear
python3 calculate_strategy_score.py low_variance 300000 1 low_variance

"""

exp_num = sys.argv[1]
num_simulations = int(sys.argv[2])  # at least 200k is recommended
click_cost = int(sys.argv[3])
reward_level = sys.argv[4]

score_list = {}
click_list = {}

# if you are using v1.0, c1.1, c2.1_dec or T1, you can uncomment this line
# if exp_num is "v1.0" or "c1.1" or "c2.1_dec":
#     exp_pipelines = learning_utils.pickle_load("data/exp_pipelines.pkl")
# else:

# Adjust the environment that you want to simulate in global_vars.py
reward_dist = "categorical"
num_trials = 35
reward_distributions = learning_utils.construct_reward_function(
    structure.reward_levels[reward_level], reward_dist
)
repeated_pipeline = learning_utils.construct_repeated_pipeline(
    structure.branchings[exp_num], reward_distributions, num_trials
)
exp_pipelines = {exp_num: repeated_pipeline}

# loops through all strategies and saves into a list
for strategy in range(0, 89):
    print("strategy", strategy)
    strategy_scores = defaultdict(lambda: defaultdict(int))
    scores = []
    gts = []
    number_of_clicks = []
    for _ in range(num_simulations):
        pipeline = exp_pipelines[exp_num]
        env = GenericMouselabEnv(num_trials=1, pipeline=pipeline)
        gts.append(tuple(env.ground_truth[0]))
        clicks = strategy_dict[strategy + 1](
            env.present_trial
        )  # gets the click sequence
        number_of_clicks.append(len(clicks))
        score = (
            env.present_trial.node_map[0].calculate_max_expected_return()
            - (len(clicks) - 1) * click_cost
        )  # len(clicks) is always 13
        scores.append(score)

    print("Score", np.mean(scores))
    print("Clicks", np.mean(number_of_clicks))


    score_list.update({strategy: np.mean(scores)})
    click_list.update({strategy: np.mean(number_of_clicks)})

score_results = dict(sorted(score_list.items(), key=lambda item: item[1], reverse=True))
print("Score results", score_results)
dir = "../results/cm/strategy_scores/"
learning_utils.create_dir(dir)
# learning_utils.pickle_save(
#     score_results, f"{dir}/{exp_num}_clickcost_{click_cost}_strategy_scores.pkl"
# )
print("Number of clicks", click_list)
learning_utils.pickle_save(
    click_list, f"{dir}/{exp_num}_numberclicks.pkl"
)

# only need for
# python3 calculate_strategy_score.py low_variance 300000 1 low_variance