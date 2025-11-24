#%%
import numpy as np
import cvxpy as cp
from scipy.linalg import block_diag

# % Inputs:
#   params : struct with fields
#     k       % is the current step such that:
#             % k = 0 means that the current time is at the beginning of the pricing window
#             % k in [1,...,Ups-1] means that the current time is within the pricing window
#     n       % number of prosumers
#     g       % energy production (in a matrix form, where columns represents the prosumers)
#     c       % energy consumption (in a matrix form, where columns represents the prosumers)
#     Delta   % sample time [min]
#     Ups     % samples per pricing window
#     h       % # pricing windows in opt horizon
#     Y       % # samples in sim horizon
#     rmax, dmax            % T×1 istantaneous recharge/discharge limits [kW]
#     pmax, smax            % T×1 istantaneous grid power limits [kW]
#     emax                  % T×1 istantaneous battery capacity [kW]
#     vemax, vemin          % T×1 SoC bounds
#     rho_p, rho_s, rho_sh  % (h+1)×1 price weights
#     eta                   % T×1 charging efficiency
#     SoC0                  % n×1 initial SoC
#   Pln2    : Y×n matrix of predicted load
#   Pvn2    : Y×n matrix of predicted generation

def solve_opt_prob(k, n, c, g, Delta, Ups, h, T,
                   rmax, dmax, pmax, smax, emax, vemax, vemin,
                   rho_p, rho_s, rho_sh,
                   eta_da, eta_r, eta_d, ve0):

    eta_r = np.round(eta_r / eta_da,2).clip(min=0.01, max=0.99)
    eta_d = np.round(eta_d * eta_da,2).clip(min=0.01, max=0.99)

    Dinv = np.tril(np.ones((T, T)))
    e1 = np.vstack([1, np.zeros((T-1,1))])
    Mtemp = np.roll(np.vstack([np.kron(np.eye(h),np.ones((1,Ups))),np.zeros((1,h*Ups))]), -(k%Ups))
    Mwsum = np.where(Mtemp.sum(axis=1) == 0, 1, Mtemp.sum(axis=1))
    Mwavg = Mtemp / Mwsum[:, np.newaxis]
    Mw = ((Ups*Delta)/60) * Mwavg

    # Optimization variables
    ri, di, dci, gci, pi, si, vei = {}, {}, {}, {}, {}, {}, {}
    for i in range(n):
        ri[i] = cp.Variable((T, 1), nonneg=True)
        di[i] = cp.Variable((T, 1), nonneg=True)
        dci[i] = cp.Variable((T, 1), nonneg=True)
        gci[i] = cp.Variable((T, 1), nonneg=True)
        pi[i] = cp.Variable((T, 1), nonneg=True)
        si[i] = cp.Variable((T, 1), nonneg=True)
        vei[i] = cp.Variable((T, 1), nonneg=True)

    th = cp.Variable((h + 1, 1), nonneg=True)

    # Define the objective function
    obj_p = np.round((Mwavg @rho_p).T,2) @ (Mw @ cp.sum([pi[i] for i in range(n)]))
    obj_s = np.round((Mwavg @rho_s).T,2) @ (Mw @ cp.sum([si[i] for i in range(n)]))
    obj_sh = np.round((Mwavg @rho_sh).T,2) @ th
    objective = obj_p - obj_s - obj_sh

    # Define the set of constraints
    cons = []
    for i in range(n):
        # Constraint on the redundant variables (for simplicity of readability)
        cons.append(pi[i] == ri[i] + c[:,i].reshape(-1,1) - dci[i] - gci[i])
        cons.append(si[i] == di[i] - dci[i] + g[:,i].reshape(-1,1) - gci[i])
        cons.append(vei[i] == Dinv @ (((Delta/60) / emax[i]) *
                                      (eta_r[i] * ri[i] - di[i] / eta_d[i]) + ve0[i] * e1))
        # Constraints in eq. (6) -- Limits on the recharge, discharge, and consumptions
        cons.append(ri[i] >= 0)
        cons.append(ri[i] <= rmax[i])
        cons.append(di[i] >= 0)
        cons.append(di[i] <= dmax[i])
        cons.append(dci[i] >= 0)
        cons.append(dci[i] <= di[i])
        cons.append(gci[i] >= 0)
        cons.append(gci[i] <= g[:,i].reshape(-1,1))
        cons.append(gci[i] >= 0)
        cons.append(ri[i] / rmax[i] + di[i] / dmax[i] >= 0)
        cons.append(ri[i] / rmax[i] + di[i] / dmax[i] <= 1)
        # Constraints in eq. (7) -- Limits on the energy from/to the grid
        cons.append(pi[i] >= 0)
        cons.append(pi[i] <= pmax[i])
        cons.append(si[i] >= 0)
        cons.append(si[i] <= smax[i])
        # Constraints in eq. (10) -- Dynamics of the battery
        cons.append(vei[i] >= vemin[i])
        cons.append(vei[i] <= vemax[i])

    # Constraints in eq. (15) -- Replacing the nonlinear term associated to the shared energy
    cons.append(th <= Mw @ cp.sum([pi[i] for i in range(n)]))
    cons.append(th <= Mw @ cp.sum([si[i] for i in range(n)]))

    #Solve the problem
    prob = (cp.Problem(cp.Minimize(objective), cons))
    #prob.solve(solver=cp.GLPK_MI)
    prob.solve(solver=cp.GLPK_MI)
    status = prob.status

    # Extract results
    if status == "infeasible":
        raise RuntimeError(f"It crashes at k = {k}")

    r = np.hstack([ri[i].value.reshape(-1, 1) for i in range(n)])
    d = np.hstack([di[i].value.reshape(-1, 1) for i in range(n)])
    p = np.hstack([pi[i].value.reshape(-1, 1) for i in range(n)])
    s = np.hstack([si[i].value.reshape(-1, 1) for i in range(n)])
    ve = np.hstack([vei[i].value.reshape(-1, 1) for i in range(n)])
    theta = th.value.reshape(-1,1)

    return r, d, p, s, ve, theta