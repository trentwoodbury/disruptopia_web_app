import pytest
from backend.availability import ActionValidator
from backend.config import PRESENCE_COSTS

def test_actions_unavailable_with_zero_funds():
    """Verify that all actions requiring money are unavailable when funds are 0."""
    state = {
        "corporate_funds": 0,
        "net_worth_level": 0,
        "reputation": 0,
        "compute_level": 1,
        "model_version": 1,
        "total_workers": 3,
        "presence_count": 1,
        "presence_regions": [1] # Random start
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()

    # Free actions should be available
    assert report["raise_funds"]["available"] is True
    assert report["play_card"]["available"] is True
    assert report["marketing"]["available"] is True

    # Paid actions should be unavailable
    assert report["buy_chips"]["available"] is False
    assert report["buy_chips"]["reason"].startswith("Insufficient Funds")

    assert report["recruit"]["available"] is False
    assert report["recruit"]["reason"].startswith("Insufficient Funds")
    
    assert report["increase_net_worth"]["available"] is False
    assert report["increase_net_worth"]["reason"].startswith("Insufficient Funds")

    assert report["scale_presence"]["available"] is False
    assert report["scale_presence"]["reason"].startswith("Insufficient Funds")

def test_startup_limitations():
    """Verify Startup (Net Worth 0) cannot access advanced tiers."""
    # Give plenty of money but 0 Net Worth
    state = {
        "corporate_funds": 100,
        "net_worth_level": 0,
        "reputation": 0,
        "compute_level": 2, # Trying to go to 3
        "model_version": 2, # Trying to go to 3
        "total_workers": 4, # Trying for 5th worker
        "presence_count": 1,
        "presence_regions": [1]
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()

    # Compute Level 3 requires Millionaire (NW 1)
    assert report["buy_chips"]["available"] is False
    assert report["buy_chips"]["reason"] == "Net Worth Too Low"

    # Model Version 3 requires Millionaire (NW 1)
    assert report["train_model"]["available"] is False
    # Note: train_model validates against next version cost which includes NW check
    assert report["train_model"]["reason"] == "Net Worth Too Low"

    # Recruit 5th Worker requires Millionaire (NW 1)
    assert report["recruit"]["available"] is False
    assert report["recruit"]["reason"] == "Net Worth Too Low"

def test_reputation_blocking():
    """Verify Reputation constraints block actions."""
    # Situation: Want to increase NW to Millionaire (Cost: $3, -2 Rep)
    # Current Rep: -3. Result would be -5. Allowed floor: -3.
    state = {
        "corporate_funds": 100,
        "net_worth_level": 0,
        "reputation": -2, # -2 - 2 = -4 (< -3) -> FAIL
        "presence_regions": [1]
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()
    
    assert report["increase_net_worth"]["available"] is False
    assert report["increase_net_worth"]["reason"] == "Reputation Too Low"
    
    # Increase rep to -1. (-1 - 2 = -3) -> OK
    state["reputation"] = -1
    validator = ActionValidator(state)
    report = validator.get_availability_report()
    assert report["increase_net_worth"]["available"] is True

def test_scale_presence_adjacencies():
    """Verify Scale Presence availability based on valid targets."""
    # Case 1: Has money, adjacent options exist -> Available
    state = {
        "corporate_funds": 100,
        "presence_count": 1, 
        "presence_regions": [1], # Adjacent: 2, 6
        "net_worth_level": 0
    }
    validator = ActionValidator(state)
    report = validator.get_availability_report()
    assert report["scale_presence"]["available"] is True
    
    # Case 2: ALL neighbors owned -> depends on logic.
    # If 1 is active, neighbors are [2, 6]. If we own 1, 2, 6...
    # Then we check neighbors of 2 (1,3,7) and 6 (1,7).
    # So we'd have 3, 7 as new neighbors.
    # It only fails if map is full or isolated.
    # Let's test isolation if map logic allows it (it doesn't, graph is connected).
    # Test Max Presence.
    state["presence_count"] = 10
    validator = ActionValidator(state)
    assert validator.get_availability_report()["scale_presence"]["available"] is False
    assert validator.get_availability_report()["scale_presence"]["reason"] == "Max Presence Reached"

def test_train_model_compute_limitation():
    """Verify model cannot exceed compute level."""
    state = {
        "corporate_funds": 100,
        "net_worth_level": 2, # Billionaire, money no issue
        "compute_level": 2,
        "model_version": 2, # Next is 3
        "presence_regions": [1]
    }
    # Compute 2 < Target 3 -> Fail
    validator = ActionValidator(state)
    res = validator.can_train_model()
    assert res["available"] is False
    assert res["reason"] == "Compute Level 3 Required"
    
    # Upgrade compute -> Pass
    state["compute_level"] = 3
    validator = ActionValidator(state)
    res = validator.can_train_model()
    assert res["available"] is True
