import pytest
import subprocess
import time
import os
import requests
import re
from playwright.sync_api import Page, expect

TEST_PORT = 8000

@pytest.fixture(scope="module", autouse=True)
def api_server():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "uvicorn.exe"], capture_output=True)
    except:
        pass

    cmd = [os.path.abspath(".venv/Scripts/python.exe"), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(TEST_PORT)]
    proc = subprocess.Popen(cmd, cwd=os.path.abspath("."))
    
    ready = False
    for i in range(20):
        try:
            res = requests.get(f"http://127.0.0.1:{TEST_PORT}/")
            if res.status_code == 200:
                ready = True
                break
        except:
            time.sleep(0.5)
    
    if not ready:
        proc.terminate()
        pytest.fail("FastAPI server failed to start")

    yield f"http://127.0.0.1:{TEST_PORT}"
    
    proc.terminate()
    proc.wait()

def test_increase_net_worth_available_on_start(page: Page, api_server):
    """Verify that Increase Net Worth is available on turn 1 with $3, 0 Rep."""
    requests.post(f"{api_server}/game/reset")
    page.goto(api_server)
    
    # Select Player 1
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    page.wait_for_selector("#user-name:has-text('Player One')")
    
    # Check if Increase Net Worth button is enabled (not hidden)
    increase_nw_row = page.locator("tr:has-text('Increase Net Worth')")
    button = increase_nw_row.get_by_role("button", name="Assign Tech Worker")
    
    expect(button).to_be_visible()
    expect(button).to_have_class(re.compile("btn-worker"))

def test_train_model_worker_ids_display(page: Page, api_server):
    """Verify that worker IDs show up in the Train New Model row."""
    requests.post(f"{api_server}/game/reset")
    page.goto(api_server)
    
    # Select Player 1
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    button.click()
    
    # Worker number 1 should show up in the count cell (column 3, index 2)
    # The ID suffix is train-new-model
    count_cell = page.locator("#count-train-new-model")
    expect(count_cell).to_have_text("1")

def test_train_model_multi_worker_placement(page: Page, api_server):
    """Verify that Train New Model places multiple workers if cost > 1."""
    requests.post(f"{api_server}/game/reset")
    
    # Need NW 1 for Compute 3+.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    
    # Upgrade Compute to 3
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C2
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C3
    
    # Train to v2
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v1
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v2
    
    page.goto(api_server)
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    
    # Verify we are at v2 via state probe
    page.wait_for_timeout(1000)
    state = page.evaluate("currentGameState.players.find(p => p.id === 1)")
    assert state['model_version'] == 2
    assert state['compute_level'] >= 3
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    button.click()
    
    # Should show "1, 2"
    count_cell = page.locator("#count-train-new-model")
    page.wait_for_timeout(1000)
    expect(count_cell).to_have_text("1, 2")

def test_train_model_button_disappears_if_insufficient_workers(page: Page, api_server):
    """Verify that Train New Model button disappears if not enough workers remain."""
    requests.post(f"{api_server}/game/reset")
    
    # Needs C3 and v2.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # c2
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # c3
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v1
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v2
    
    page.goto(api_server)
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    
    # Total workers: 3. v3 requires 2.
    # Initially visible (3 > 2).
    train_model_row = page.locator("tr:has-text('Train New Model')")
    train_button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    expect(train_button).to_be_visible()
    
    # Place 2 workers on "Marketing"
    marketing_row = page.locator("tr:has-text('Marketing')")
    m_btn = marketing_row.get_by_role("button", name="Assign Tech Worker")
    m_btn.click() # Worker 1
    page.wait_for_timeout(500)
    m_btn.click() # Worker 2
    page.wait_for_timeout(1000)
    
    # Left: 1 worker. Needs 2. Hide.
    expect(train_button).not_to_be_visible()

def test_train_model_projected_compute(page: Page, api_server):
    """Verify Train New Model becomes available if Compute upgrade is pending."""
    requests.post(f"{api_server}/game/reset")
    
    # Setup: Model 2, Compute 2. Millionaire.
    # We need NW1 for C3.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C2
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v1
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v2
    
    # Give money for C3
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1]})
    
    page.goto(api_server)
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    train_button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    
    # Initially hidden because Compute is 2, need 3 for v3.
    expect(train_button).not_to_be_visible()
    
    # Place worker on Buy Chips
    buy_chips_row = page.locator("tr:has-text('Buy Chips')")
    buy_chips_btn = buy_chips_row.get_by_role("button", name="Assign Tech Worker")
    buy_chips_btn.click()
    
    # Now Train New Model should be visible
    expect(train_button).to_be_visible()

def test_train_model_projected_workers(page: Page, api_server):
    """Verify Train New Model becomes available if Recruitment is pending."""
    requests.post(f"{api_server}/game/reset")
    
    # Setup: Model 2, Compute 3. Workers 3.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C2
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C3
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v1
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v2
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    train_button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    
    # v3 requires 2 workers. Only 3 total workers, all unplaced. Available: 3.
    # Wait, it SHOULD be visible initially because 3 > 2.
    # Let's place 2 workers elsewhere.
    marketing_row = page.locator("tr:has-text('Marketing')")
    m_btn = marketing_row.get_by_role("button", name="Assign Tech Worker")
    m_btn.click()
    page.wait_for_timeout(500)
    m_btn.click()
    page.wait_for_timeout(500)
    
    # Now 1 worker left. Train Model (v3) requires 2. Button should hide.
    expect(train_button).not_to_be_visible()
    
    # Now place a worker on Recruit (needs NW1 which we have).
    # Worker 3 is the only one left.
    recruit_row = page.locator("tr:has-text('Recruit')")
    r_btn = recruit_row.get_by_role("button", name="Assign Tech Worker")
    r_btn.click() # Placed worker 3 on Recruit. Remaining: 0 real, 1 projected (worker 4). Total avail: 1.
    
    # Still not enough? Wait. 
    # Current placements: M1, M2, R3. Total: 3.
    # Projected total: 4.
    # Available for Train: projected(4) - unplaced(0) ... no.
    # availableWorkers = projectedTotalWorkers - placedCount.
    # placedCount = 3. projectedTotalWorkers = 4. available = 1.
    # Still not enough for v3 (requires 2).
    
    # Let's undo one marketing.
    # Actually, let's just place only 1 on marketing.
    # Placement 1: Marketing.
    # Remaining: 2 real. 
    # Action Train (needs 2) -> available.
    
    # OK, let's restart the scenario.
    requests.post(f"{api_server}/game/reset")
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C2
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C3
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v1
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v2
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    # Place 2 workers on Marketing.
    m_btn.click()
    page.wait_for_timeout(500)
    m_btn.click()
    page.wait_for_timeout(500)
    # Available: 1. Hide Train.
    expect(train_button).not_to_be_visible()
    
    # Recruit.
    r_btn.click()
    # Available: 1 real + 1 projected = 2. 
    # BUT worker 3 is ALREADY placed on Recruit.
    # So availableWorkers = 4 (projected) - 3 (placed) = 1.
    # STILL 1. 
    # Ah! If worker 3 is on Recruit, it produces worker 4.
    # So I have worker 4 available.
    # But Train needs 2. 
    
    # Let's make it simpler:
    # 3 workers total. v1->v2 (cost 1).
    # Current: v0.
    # Place 3 workers on Marketing.
    # Available: 0. Train hidden.
    # Place 1 on Recruit (oops, no workers left).
    
    # Scenario:
    # 3 workers. v3 requires 2.
    # Place 1 on Recruit.
    # Now I have 2 workers left (2, 3) PLUS projected 1 (4). Total available: 3.
    # NO. Workers 2 and 3 are REAL. Worker 4 is FUTURE.
    # If I place 2 and 3 on something else, I have 1 projected left.
    
    # Let's use the USER's example:
    # "worker 1 is on recruit, workers 2 and 3 are on Train... 3 required"
    # Cost 3. Workers 1, 2, 3 used. Worker 4 from recruit will be used for Train.
    # Available = 4 (proj) - 3 (placed) = 1.
    # If I click Train, it should take workers 2, 3 (already there?) No.
    
    # Interaction:
    # 1. Place worker 1 on Recruit.
    # 2. Assign balance to Train Model.
    
    # Let's try:
    # 3 workers. Cost for next model is 2.
    # Place 2 workers on Marketing.
    # 1 worker left. Train hidden.
    # Place worker 3 on Recruit.
    # Now projected total is 4. Placed is 3. 
    # Available is 1. Still hidden.
    
    # WAIT. If I place worker 2 on Recruit.
    # Placed: 1(M), 2(R). Total 2 placed.
    # Projected total: 4.
    # Available: 4 - 2 = 2.
    # Train (needs 2) should be VISIBLE.
    
    # Let's test this.
    requests.post(f"{api_server}/game/reset")
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C2
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C3
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v1
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1") # v2
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    marketing_row = page.locator("tr:has-text('Marketing')")
    m_btn = marketing_row.get_by_role("button", name="Assign Tech Worker")
    m_btn.click() # Worker 1
    page.wait_for_timeout(500)
    
    # Now 2 workers left (2, 3). Train (needs 2) is VISIBLE.
    expect(train_button).to_be_visible()
    
    # Place worker 2 on Recruit.
    recruit_row = page.locator("tr:has-text('Recruit')")
    r_btn = recruit_row.get_by_role("button", name="Assign Tech Worker")
    r_btn.click() # Worker 2
    page.wait_for_timeout(500)
    
    # Placements: M1, R2. Total 2.
    # Projected total: 4.
    # Available: 4 - 2 = 2.
    # Train (needs 2) should be VISIBLE.
    expect(train_button).to_be_visible()
    
    # Click Train Model.
    train_button.click()
    
    # Should assign workers 3 and 4!
    count_cell = page.locator("#count-train-new-model")
    page.wait_for_timeout(1000)
    expect(count_cell).to_have_text("3, 4")

def test_train_model_sequential_upgrades(page: Page, api_server):
    """Verify that multiple separate upgrades can be assigned in one turn."""
    requests.post(f"{api_server}/game/reset")
    
    # Setup: 5 workers, Compute 2. Millionaire.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1") # C2
    
    # Total workers: 3 + 0 (Startup starts with 3). 
    # Current model v0. Compute 2.
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    count_cell = page.locator("#count-train-new-model")
    
    # 1. First upgrade (v0 -> v1, cost 1)
    button.click()
    page.wait_for_timeout(1000)
    expect(count_cell).to_have_text("1")
    
    # 2. Second upgrade (v1 -> v2, cost 1)
    # Button should STILL be visible because Compute is 2.
    expect(button).to_be_visible()
    button.click()
    page.wait_for_timeout(1000)
    expect(count_cell).to_have_text("1, 2")
    
    # 3. Third upgrade (v2 -> v3, cost 2)
    # Compute is only 2. Button should HIDE.
    expect(button).not_to_be_visible()

