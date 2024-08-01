from dataclasses import dataclass

import numpy as np
from timer import timer

from mixing import init_gravity_diffusion


@dataclass
class Params:
    beta: float
    seasonality: float
    demog_scale: float
    mixing_scale: float
    distance_exponent: float


def init_state(settlements_df, params):
    
    population_s = settlements_df.population.astype(int)
    births_s = settlements_df.births.astype(int)

    N = population_s
    S = births_s * 2
    I = (S / 26. / 2.).astype(int)

    state = np.array([S, I, N-S-I]).T

    params.biweek_avg_births = params.demog_scale * births_s / 26.
    params.biweek_death_prob = params.demog_scale * births_s / N / 26.

    params.mixing = init_gravity_diffusion(settlements_df, params.mixing_scale, params.distance_exponent)

    return state


def step_state(state, params, t):
    
        expected = params.beta * (1 + params.seasonality * np.cos(2*np.pi*t/26.)) * np.matmul(params.mixing, state[:, 1])
        prob = 1 - np.exp(-expected/state.sum(axis=1))
        dI = np.random.binomial(n=state[:, 0], p=prob)

        state[:, 2] += state[:, 1]
        state[:, 1] = 0

        births = np.random.poisson(lam=params.biweek_avg_births)
        deaths = np.random.binomial(n=state, p=np.tile(params.biweek_death_prob, (3, 1)).T)

        state[:, 0] += births
        state -= deaths

        state[:, 1] += dI
        state[:, 0] -= dI


@timer("simulate", unit="ms")
def simulate(init_state, params, n_steps):
    
    state_timeseries = np.zeros((n_steps, *init_state.shape), dtype=int)

    state = init_state

    for t in range(n_steps):
        state_timeseries[t, :, :] = state
        step_state(state, params, t)
    
    return state_timeseries


if __name__ == "__main__":
    
    import logging
    logging.basicConfig()
    logging.getLogger('timer').setLevel(logging.DEBUG)

    import matplotlib.pyplot as plt 

    from settlements import parse_settlements
    settlements_df = parse_settlements()

    settlements_slice = slice(None, None)  # all settlements
    # settlements_slice = slice(None, 20)  # only biggest N
    # settlements_slice = slice(400, None)  # exclude biggest N

    biweek_steps = 26 * 20
    params = Params(
         beta=32, seasonality=0.16, demog_scale=1.0, 
         mixing_scale=0.002, distance_exponent=1.5)
    print(params)

    init_state = init_state(settlements_df.iloc[settlements_slice, :], params)
    states = simulate(init_state, params, n_steps=biweek_steps)

    # --------

    # presence_tsteps = (states[:, :, 1] > 0).sum(axis=0)
    # plt.scatter(settlements_df.population[settlements_slice], presence_tsteps / 26.)
    # ax = plt.gca()
    # ax.set(xscale='log', xlabel='population', ylabel='years with infections present')

    # --------

    # test_ix = 5  # a large city to see some endemic dynamics
    # # test_ix = 200  # a medium city to see some extinction dynamics + frequent reintroductions
    # # test_ix = 800  # a smaller village to see some extinction + random reintroduction dynamics
    # print(settlements_df.iloc[test_ix])
    # test_states = states[:, test_ix, :]  # (time, location, SIR)

    # from plotting import plot_timeseries
    # plot_timeseries(test_states)
    # from wavelet import plot_wavelet_spectrum
    # plot_wavelet_spectrum(test_states[:, 1])  # infecteds

    # --------

    # TODO: Something like https://www.nature.com/articles/414716a#Sec4 and/or Xia et al. (2004)
    # https://github.com/krosenfeld-IDM/sandbox-botorch/blob/main/laser/london/analyze.py#L68

    from wavelet import get_phase_diffs
    from mixing import pairwise_haversine
    ref_name = "London"
    sdf = settlements_df.iloc[settlements_slice, :]
    ref_ix = sdf.index.get_loc(ref_name)
    phase_diffs = get_phase_diffs(states[:, :, 1], ref_ix)
    distances_km = pairwise_haversine(sdf)[ref_ix]

    fig, ax = plt.subplots()
    ax.scatter(distances_km, phase_diffs, s=0.1*np.sqrt(sdf.population), alpha=0.4, c='gray')
    ax.set(xlabel="distance from %s (km)" % ref_name, ylabel="phase difference (radians)")

    # fig, ax = plt.subplots()
    # ind = np.where(distances_km < 10)
    # import pandas as pd
    # pd.DataFrame(states[:, ind, 1].squeeze()).plot(ax=ax, legend=False, color='gray', alpha=0.1)
    # ax.set(title="within 10km of London")


    # --------

    # from plotting import plot_animation
    # ani = plot_animation(
    #     states, 
    #     settlements_df.iloc[settlements_slice, :], 
    #     # 'figures/ew_spatial_animation.gif'
    # )

    plt.show()