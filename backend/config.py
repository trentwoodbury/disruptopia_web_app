# Compute Level costs and requirements
COMPUTE_UPGRADE_COSTS = {2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}
# 0 = Startup, 1 = Millionaire, 2 = Billionaire
COMPUTE_NET_WORTH_REQ = {
    3: 1, # Must be Millionaire for Level 3
    4: 1, # Must be Millionaire for Level 4
    5: 2, # Must be Billionaire for Level 5
    6: 2,
    7: 2
}

# How many Tech Workers are required to increase TO this version?
MODEL_WORKER_COSTS = {
    1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4
}
# 0 = Startup, 1 = Millionaire, 2 = Billionaire
MODEL_NET_WORTH_REQ = {
    3: 1, # Must be Millionaire for V3
    4: 1,
    5: 2, # Must be Billionaire for V5
    6: 2,
    7: 2
}

WORLD_MAP = {
    1: [2, 6],
    2: [1, 3, 7],
    3: [2, 4, 8],
    4: [3, 5, 9],
    5: [4, 10],
    6: [1, 7],
    7: [2, 6, 8],
    8: [3, 7, 9],
    9: [4, 8, 10],
    10: [5, 9],
}

# --- Net Worth Upgrades ---
# Level 1 = Millionaire, Level 2 = Billionaire
NET_WORTH_COSTS = {
    1: {"money": 3, "reputation": 2}, # Pay $3, Lose 2 Rep
    2: {"money": 5, "reputation": 4}  # Pay $5, Lose 4 Rep
}
# Bonuses for being the first to reach a Net Worth (based on player count)
# Format: {NetWorthLevel: {PlayerCount: [1stBonus, 2ndBonus]}}
NET_WORTH_VP_BONUS = {
    1: {2: [1], 3: [2, 1], 4: [2, 1, 1], 5: [2, 1, 1]},
    2: {2: [1], 3: [2, 1], 4: [2, 1, 1], 5: [2, 1, 1]}
}

# --- Tech Worker Recruitment ---
RECRUIT_COSTS = {
    4: {"money": 2, "min_nw": 0}, # Startup
    5: {"money": 3, "min_nw": 1}, # Millionaire
    6: {"money": 4, "min_nw": 1}, # Millionaire
    7: {"money": 5, "min_nw": 2}, # Billionaire
    8: {"money": 6, "min_nw": 2}, # Billionaire
}

# Marketing Bonuses based on Net Worth Level
# 0: Startup, 1: Millionaire, 2: Billionaire
MARKETING_BONUSES = {
    0: {"reputation": 3, "power": 0},
    1: {"reputation": 1, "power": 1},
    2: {"reputation": 0, "power": 2}
}