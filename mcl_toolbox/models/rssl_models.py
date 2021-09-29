from collections import defaultdict

import mpmath as mp
import numpy as np

from mcl_toolbox.models.base_learner import Learner
from mcl_toolbox.utils.learning_utils import (
    beta_integrate,
    get_log_beta_cdf,
    get_log_beta_pdf,
    get_log_norm_cdf,
    get_log_norm_pdf,
    norm_integrate,
    pickle_load,
)
from mcl_toolbox.utils.planning_strategies import strategy_dict

NS = 79
precision_epsilon = 1e-4
quadrature_max_degree = 1e5


def clear_cache():
    get_log_beta_cdf.cache_clear()
    get_log_beta_pdf.cache_clear()
    get_log_norm_cdf.cache_clear()
    get_log_norm_pdf.cache_clear()


class RSSL(Learner):
    """Base class of the RSSL models with different priors"""

    # TODO:
    # Change the source of the strategies.
    # Pass weights according to features
    # Weights are not used in regular computation, only used for likelihood computation
    def __init__(self, params, attributes):
        super().__init__(params, attributes)
        self.priors = params["priors"]
        self.strategy_space = attributes["strategy_space"]
        self.num_strategies = len(self.strategy_space)
        self.upper_limit = 250  # Buffer for subjective cost
        self.lower_limit = -250  # Buffer for subjective cost
        self.gaussian = attributes["is_gaussian"]
        if self.gaussian:
            self.priors = np.exp(self.priors)
        self.strategy_weights = pickle_load("data/microscope_weights.pkl")
        self.variance = 1
        if "gaussian_var" in attributes:
            self.variance = np.exp(attributes["gaussian_var"])
        self.stochastic_updating = attributes["stochastic_updating"]

    def gaussian_max_likelihoods(
        self,
    ):  # Numerical integration to compute the likelihood under the gaussian distribution
        priors = self.priors
        num_strategies = self.num_strategies
        means = priors[:num_strategies]
        sigmas = np.sqrt(priors[num_strategies:])
        max_val = np.max(means + 5 * sigmas)
        min_val = np.min(means - 5 * sigmas)
        likelihoods = [
            mp.quad(lambda x: norm_integrate(x, i, means, sigmas), [min_val, max_val])
            for i in range(num_strategies)
        ]
        return likelihoods

    def bernoulli_max_likelihoods(
        self,
    ):  # Numerical integration to compute the likelihood under the beta distribution
        priors = self.priors
        num_strategies = self.num_strategies
        alphas = priors[:num_strategies]
        betas = priors[num_strategies:]
        max_val = 1
        min_val = 0
        likelihoods = [
            mp.quad(lambda x: beta_integrate(x, i, alphas, betas), [min_val, max_val])
            for i in range(num_strategies)
        ]
        return likelihoods

    def get_max_likelihoods(self):
        if self.gaussian:
            return self.gaussian_max_likelihoods()
        else:
            return self.bernoulli_max_likelihoods()

    def bernoulli_choice(self):
        priors = self.priors
        values = np.zeros(self.num_strategies)
        for strategy_num in range(self.num_strategies):
            values[strategy_num] = np.random.beta(
                priors[strategy_num] + 1, priors[strategy_num + self.num_strategies] + 1
            )
        return np.argmax(values)

    def gaussian_choice(self):
        priors = self.priors
        num_strategies = self.num_strategies
        values = np.zeros(num_strategies)
        for strategy_num in range(num_strategies):
            values[strategy_num] = np.random.normal(
                priors[strategy_num], np.sqrt(priors[strategy_num + num_strategies])
            )
        return np.argmax(values)

    def update_bernoulli_params(self, reward, strategy_index):
        normalized_prob = (reward - self.lower_limit) / (
            self.upper_limit - self.lower_limit
        )
        priors = self.priors
        if self.stochastic_updating:
            choice = np.random.binomial(n=1, p=normalized_prob) == 1
            if choice:
                priors[strategy_index] += 1
            else:
                priors[strategy_index + self.num_strategies] += 1
        else:
            priors[strategy_index] += normalized_prob
            priors[strategy_index + self.num_strategies] += 1 - normalized_prob

    def update_gaussian_params(self, reward, strategy_index):
        var = self.variance
        num_strategies = self.num_strategies
        priors = self.priors
        priors[strategy_index] = (
            priors[strategy_index + num_strategies] * reward
            + priors[strategy_index] * var
        ) / (priors[strategy_index + num_strategies] + var)
        priors[strategy_index + num_strategies] = (
            priors[strategy_index + num_strategies]
            * var
            / (priors[strategy_index + num_strategies] + var)
        )

    def update_params(self, reward, strategy_index):
        if self.is_null:
            return
        if self.gaussian:
            self.update_gaussian_params(reward, strategy_index)
        else:
            self.update_bernoulli_params(reward, strategy_index)

    def select_strategy(self):
        if self.gaussian:
            strategy_index = self.gaussian_choice()
        else:
            strategy_index = self.bernoulli_choice()
        return strategy_index

    def apply_strategy(self, env, trial, strategy_index):
        S = self.strategy_space[strategy_index]
        actions = strategy_dict[S](trial)
        env.reset_trial()
        r_list = []
        delays = []
        prs = []
        for action in actions:
            delay = env.get_feedback({"action": action})
            self.store_best_paths(env)
            _, r, _, taken_path = env.step(action)
            r_list.append(r)
            delays.append(self.delay_scale * delay)
            prs.append(self.get_pseudo_reward(env))
        info = {"taken_path": taken_path, "delays": delays, "prs": prs}
        return actions, r_list, info

    def get_action_strategy_likelihood(
        self, trial, actions, chosen_strategy, temperature
    ):
        strategy_weights = self.strategy_weights[chosen_strategy - 1] * (
            1 / temperature
        )
        normalized_features = self.normalized_features
        ll = compute_log_likelihood(
            trial,
            actions,
            self.features,
            strategy_weights,
            inv_t=False,
            normalized_features=normalized_features,
        )
        return ll

    def compute_log_likelihood(self, clicks, chosen_strategy):
        likelihoods = self.get_max_likelihoods()
        strategy_index = self.strategy_space.index(chosen_strategy)
        strategy_likelihood = likelihoods[strategy_index]
        actions_strategy_log_likelihood = self.get_action_strategy_likelihood(
            trial, clicks, chosen_strategy, self.temperature
        )
        log_prob = float(
            str(actions_strategy_log_likelihood + mp.log(strategy_likelihood))
        )
        return log_prob

    def generate_trials_data(self, env, compute_likelihood, participant):
        action_log_probs = []
        trials_data = defaultdict(list)
        num_trials = env.num_trials
        for trial_num in range(num_trials):
            trial = env.trial_sequence.trial_sequence[trial_num]
            self.previous_best_paths = []
            if compute_likelihood:
                clicks = all_trials_data["actions"][trial_num]
                rewards = all_trials_data["rewards"][trial_num]
                chosen_strategy = all_trials_data["strategies"][trial_num]
                log_prob = self.compute_log_likelihood(clicks, chosen_strategy)
                action_log_probs.append(log_prob)
                reward = np.sum(rewards)
                self.update_params(reward, strategy_index)
            else:
                strategy_index = self.select_strategy()
                clicks, r_list, info = self.apply_strategy(env, trial, strategy_index)
                reward = np.sum(r_list)
                update_reward = reward.copy()
                update_reward -= (len(r_list) - 1) * self.subjective_cost
                update_reward -= np.sum(info["delays"])
                update_reward += np.sum(info["prs"])
                self.update_params(update_reward, strategy_index)
            trials_data["r"].append(reward)
            chosen_strategy = self.strategy_space[strategy_index]
            trials_data["s"].append(chosen_strategy)
            trials_data["w"].append(self.strategy_weights[chosen_strategy - 1])
            trials_data["a"].append(clicks)
            env.get_next_trial()
        if self.action_log_probs:
            trials_data["loss"] = -np.sum(action_log_probs)
        else:
            trials_data["loss"] = None
        return trials_data

    def simulate(self, env, compute_likelihood=False, participant=None):
        env.reset()
        clear_cache()
        self.action_log_probs = False
        if compute_likelihood:
            self.action_log_probs = True
        self.temperature = 1
        if hasattr(participant, "temperature"):
            self.temperature = participant.temperature
        trials_data = self.generate_trials_data(env, compute_likelihood, participant)
        return dict(trials_data)


class BernoulliRSSL(RSSL):
    """RSSL model with bernoulli priors"""

    def __init__(self, params, attributes):
        super().__init__(params, attributes)


class GaussianRSSL(RSSL):
    """ RSSL model with Gaussian priors"""

    def __init__(self, params, attributes):
        super().__init__(params, attributes)
        self.gaussian = True


class NullBernoulliRSSL(BernoulliRSSL):
    """ Bernoulli RSSL without learning """

    def __init__(self, params, attributes):
        super().__init__(params, attributes)
        self.is_null = True


class NullGaussianRSSL(GaussianRSSL):
    """ Gaussian RSSL without learning """

    def __init__(self, params, attributes):
        super().__init__(params, attributes)
        self.is_null = True
        self.gaussian = True
