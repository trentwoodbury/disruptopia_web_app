from backend.config import (
    COMPUTE_UPGRADE_COSTS,
    COMPUTE_NET_WORTH_REQ,
    MODEL_WORKER_COSTS,
    MODEL_NET_WORTH_REQ,
    NET_WORTH_COSTS,
    PRESENCE_COSTS,
    RECRUIT_COSTS,
    WORLD_MAP,
)

class ActionValidator:
    """
    Centralizes validation logic for all player actions based on a given state.
    The state can be the current state or a projected future state.
    """
    def __init__(self, state: dict, workers_remaining: int = 1, player_modifiers: dict = None, ignore_worker_check: bool = False):
        """
        :param state: Projected state dict.
        :param workers_remaining: Number of workers available to be placed.
        :param player_modifiers: Buffs/Debuffs.
        :param ignore_worker_check: If True, skips the worker availability check.
        """
        self.state = state
        self.workers_remaining = workers_remaining
        self.ignore_worker_check = ignore_worker_check
        self.mods = player_modifiers or {
            "model_worker_cost_offset": 0,
            "compute_cost_offset": 0,
            "hand_limit": 5,
            "income_offset": 0,
            "draw_bonus": 0,
            "worker_income_efficiency": False,
            "free_card_play": False,
            "priority_p1": False,
        }

    def _funds(self):
        return self.state.get("corporate_funds", 0)

    def _nw(self):
        return self.state.get("net_worth_level", 0)

    def _rep(self):
        return self.state.get("reputation", 0)
        
    def _check_worker(self):
        if self.ignore_worker_check:
            return None
        if self.workers_remaining <= 0:
            return {"available": False, "reason": "No Workers Remaining"}
        return None

    def can_raise_funds(self):
        check = self._check_worker()
        if check: return check
        return {"available": True}

    def can_play_card(self):
        check = self._check_worker()
        if check: return check
        return {"available": True}

    def can_marketing(self):
        check = self._check_worker()
        if check: return check
        return {"available": True}

    def can_buy_chips(self):
        check = self._check_worker()
        if check: return check
        
        next_level = self.state.get("compute_level", 0) + 1
        if next_level > 7:
            return {"available": False, "reason": "Max Compute Level Reached"}

        base_cost = COMPUTE_UPGRADE_COSTS.get(next_level, 999)
        cost = max(0, base_cost + self.mods["compute_cost_offset"])
        
        if self._funds() < cost:
            return {"available": False, "reason": f"Insufficient Funds (${cost})"}
            
        req_nw = COMPUTE_NET_WORTH_REQ.get(next_level, 0)
        if self._nw() < req_nw:
            return {"available": False, "reason": "Net Worth Too Low"}

        return {"available": True}

    def can_recruit(self):
        check = self._check_worker()
        if check: return check

        next_num = self.state.get("total_workers", 3) + 1
        if next_num > 8:
            return {"available": False, "reason": "Max Workers Reached"}

        tier = RECRUIT_COSTS.get(next_num)
        if not tier:
            return {"available": False, "reason": "Unknown Recruit Tier"}

        if self._funds() < tier["money"]:
            return {"available": False, "reason": f"Insufficient Funds (${tier['money']})"}
        
        if self._nw() < tier["min_nw"]:
            return {"available": False, "reason": "Net Worth Too Low"}

        return {"available": True}

    def can_train_model(self, available_workers_count: int = 1):
        check = self._check_worker()
        if check: return check

        next_version = self.state.get("model_version", 0) + 1
        if next_version > 7:
            return {"available": False, "reason": "Max Model Version Reached"}

        # Net Worth Check
        if self._nw() < MODEL_NET_WORTH_REQ.get(next_version, 0):
            return {"available": False, "reason": "Net Worth Too Low"}

        # Compute Check
        if self.state.get("compute_level", 0) < next_version:
            return {"available": False, "reason": f"Compute Level {next_version} Required"}
            
        return {"available": True}

    def can_increase_net_worth(self):
        check = self._check_worker()
        if check: return check

        next_nw = self._nw() + 1
        if next_nw > 2:
            return {"available": False, "reason": "Max Net Worth Reached"}

        costs = NET_WORTH_COSTS.get(next_nw)
        if not costs:
            return {"available": False, "reason": "Unknown NW Tier"}

        if self._funds() < costs["money"]:
            return {"available": False, "reason": f"Insufficient Funds (${costs['money']})"}

        # Reputation Check
        if (self._rep() - costs["reputation"]) < -3:
            return {"available": False, "reason": "Reputation Too Low"}

        return {"available": True}

    def can_scale_presence(self):
        check = self._check_worker()
        if check: return check

        current_count = self.state.get("presence_count", 0)
        if current_count >= 10:
             return {"available": False, "reason": "Max Presence Reached"}

        cost_idx = current_count - 1
        if cost_idx < 0: cost_idx = 0
        
        if cost_idx >= len(PRESENCE_COSTS):
            return {"available": False, "reason": "Max Expansion Limit"}
            
        cost = PRESENCE_COSTS[cost_idx]
        
        if self._funds() < cost:
            return {"available": False, "reason": f"Insufficient Funds (${cost})"}

        owned_ids = set(self.state.get("presence_regions", []))
        neighbors = set()
        for r_id in owned_ids:
            adj = WORLD_MAP.get(r_id, [])
            for a in adj:
                if a not in owned_ids:
                    neighbors.add(a)
        
        if not neighbors:
            return {"available": False, "reason": "No Valid Expansion Targets"}
            
        return {"available": True}
        
    def get_availability_report(self):
        """
        Returns a dict of all actions and their availability status.
        """
        return {
            "raise_funds": self.can_raise_funds(),
            "play_card": self.can_play_card(),
            "marketing": self.can_marketing(),
            "buy_chips": self.can_buy_chips(),
            "recruit": self.can_recruit(),
            "train_model": self.can_train_model(),
            "increase_net_worth": self.can_increase_net_worth(),
            "scale_presence": self.can_scale_presence(),
        }
