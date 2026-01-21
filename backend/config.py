# Compute Level costs and requirements
from backend.enums import CardCategory

COMPUTE_UPGRADE_COSTS = {2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}
# 0 = Startup, 1 = Millionaire, 2 = Billionaire
COMPUTE_NET_WORTH_REQ = {
    3: 1,  # Must be Millionaire for Level 3
    4: 1,  # Must be Millionaire for Level 4
    5: 2,  # Must be Billionaire for Level 5
    6: 2,
    7: 2,
}

# How many Tech Workers are required to increase TO this version?
MODEL_WORKER_COSTS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4}
# 0 = Startup, 1 = Millionaire, 2 = Billionaire
MODEL_NET_WORTH_REQ = {
    3: 1,  # Must be Millionaire for V3
    4: 1,
    5: 2,  # Must be Billionaire for V5
    6: 2,
    7: 2,
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
    1: {"money": 3, "reputation": 2},  # Pay $3, Lose 2 Rep
    2: {"money": 5, "reputation": 4},  # Pay $5, Lose 4 Rep
}
# Bonuses for being the first to reach a Net Worth (based on player count)
# Format: {NetWorthLevel: {PlayerCount: [1stBonus, 2ndBonus]}}
NET_WORTH_VP_BONUS = {
    1: {2: [1], 3: [2, 1], 4: [2, 1, 1], 5: [2, 1, 1]},
    2: {2: [1], 3: [2, 1], 4: [2, 1, 1], 5: [2, 1, 1]},
}

# --- Tech Worker Recruitment ---
RECRUIT_COSTS = {
    4: {"money": 2, "min_nw": 0},  # Startup
    5: {"money": 3, "min_nw": 1},  # Millionaire
    6: {"money": 4, "min_nw": 1},  # Millionaire
    7: {"money": 5, "min_nw": 2},  # Billionaire
    8: {"money": 6, "min_nw": 2},  # Billionaire
}

# Marketing Bonuses based on Net Worth Level
# 0: Startup, 1: Millionaire, 2: Billionaire
MARKETING_BONUSES = {
    0: {"reputation": 3, "power": 0},
    1: {"reputation": 1, "power": 1},
    2: {"reputation": 0, "power": 2},
}

REPUTATION_TILE_POOL = {
    0: [
        {"name": "Inefficient R&D", "effect": "model_cost_plus_1"},
        {"name": "Legacy Tax", "effect": "compute_cost_plus_3"},
        {"name": "Information Leak", "effect": "discard_per_round"},
        {"name": "Security Audit", "effect": "hand_limit_3"},
        {"name": "Power Drain", "effect": "lose_2_power_round"},
    ],
    1: [
        {"name": "Subsidy Bonus", "effect": "income_plus_1"},
        {"name": "Rapid Intel", "effect": "draw_extra_card"},
        {"name": "Expanded Library", "effect": "hand_limit_6"},
        {"name": "Hardware Discount", "effect": "compute_minus_1"},
    ],
    2: [
        {"name": "Market Leader", "effect": "income_plus_2"},
        {"name": "Cloud Partnership", "effect": "compute_minus_2"},
        {"name": "Streamlined Ops", "effect": "play_card_worker_minus_1"},
        {"name": "Optimized Training", "effect": "model_worker_minus_1"},
    ],
    3: [
        {"name": "Venture Mogul", "effect": "free_hand_card"},
        {"name": "Board Chairman", "effect": "perma_p1"},
        {"name": "Infinite Loop", "effect": "free_active_effect"},
        {"name": "Automated Finance", "effect": "one_worker_income"},
    ],
}

# Assuming CardCategory is already imported or defined in your config
CARD_LIBRARY = [
    {
        "name": "good_ol_corporate_espionage",
        "is_effect": True,
        "qty": 5,
        "cost": 2,
        "deck": CardCategory.INFLUENCE.value,
        "effect_slug": "corporate_espionage",
    },
    {
        "name": "unethical_data_source",
        "is_effect": False,
        "qty": 10,
        "cost": 1,
        "deck": CardCategory.RESEARCH.value,
        "effect_slug": "unethical_data",
    },
    {
        "name": "some_nerdy_server_optimization_thing",
        "is_effect": False,
        "qty": 5,
        "cost": 1,
        "deck": CardCategory.RESEARCH.value,
        "effect_slug": "nerdy_server_optimization",
    },
    {
        "name": "hire_a_lobbyist",
        "is_effect": False,
        "qty": 5,
        "cost": 1,
        "deck": CardCategory.INFLUENCE.value,
        "effect_slug": "hire_a_lobbyist",
    },
]
