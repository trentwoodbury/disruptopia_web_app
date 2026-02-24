import pytest
import subprocess
import time
import os
import requests
from playwright.sync_api import Page, expect
import re

# Use a specific port for testing if 8000 is occupied, 
# but frontend app.js expects 8000. 
TEST_PORT = 8000

@pytest.fixture(scope="module", autouse=True)
def api_server():
    # Attempt to kill anything on port 8000 (standard for this project)
    try:
        subprocess.run(["taskkill", "/F", "/IM", "uvicorn.exe"], capture_output=True)
    except:
        pass

    # Start the FastAPI server
    cmd = [os.path.abspath(".venv/Scripts/python.exe"), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(TEST_PORT)]
    proc = subprocess.Popen(cmd, cwd=os.path.abspath("."))
    
    # Wait for server to be ready
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
        pytest.fail("FastAPI server failed to start for frontend tests")

    yield f"http://127.0.0.1:{TEST_PORT}"
    
    proc.terminate()
    proc.wait()

def test_net_worth_progression_ui(page: Page, api_server):
    """
    Test that Net Worth level markers (X) move correctly when upgrading.
    """
    requests.post(f"{api_server}/game/reset")
    
    page.set_viewport_size({"width": 1280, "height": 1024})
    page.goto(api_server)
    
    page.wait_for_selector("#player-select option[value='1']", state="attached", timeout=10000)
    page.select_option("#player-select", "1")
    page.wait_for_selector("#user-name:has-text('Player One')")

    expect(page.get_by_text("STARTUP (X)")).to_be_visible()
    
    # Upgrade to Millionaire
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    page.evaluate("refreshData()")
    
    expect(page.get_by_text("MILLIONAIRE (X)")).to_be_visible()
    expect(page.get_by_text("STARTUP (X)")).not_to_be_visible()
    
    # Upgrade to Billionaire (Needs Funds & Rep)
    for _ in range(6):
        requests.post(f"{api_server}/actions/execute/marketing?player_id=1")

    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1]})
    
    res = requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    if res.status_code != 200:
        print(f"DEBUG: Billionaire upgrade failed: {res.text}")
    
    page.evaluate("refreshData()")
    
    expect(page.get_by_text("BILLIONAIRE (X)")).to_be_visible()
    expect(page.get_by_text("MILLIONAIRE (X)")).not_to_be_visible()

def test_increase_net_worth_available_on_start(page: Page, api_server):
    """Verify that Increase Net Worth is available on turn 1."""
    requests.post(f"{api_server}/game/reset")
    page.goto(api_server)
    
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    page.wait_for_selector("#user-name:has-text('Player One')")
    
    increase_nw_row = page.locator("tr:has-text('Increase Net Worth')")
    button = increase_nw_row.get_by_role("button", name="Assign Tech Worker")
    
    expect(button).to_be_visible()
    expect(button).to_have_class(re.compile("btn-worker"))

def test_train_model_worker_ids_display(page: Page, api_server):
    """Verify that worker IDs show up in the Train New Model row."""
    requests.post(f"{api_server}/game/reset")
    page.goto(api_server)
    
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    button.click()
    
    count_cell = page.locator("#count-train-new-model")
    expect(count_cell).to_have_text("1")

def test_train_model_multi_worker_placement(page: Page, api_server):
    """Verify that Train New Model places multiple workers if cost > 1."""
    requests.post(f"{api_server}/game/reset")
    
    # Needs NW 1 for Compute 3+.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    
    # Upgrade Compute to 3
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1")
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1")
    
    # Train to v2
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1")
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1")
    
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



def test_train_model_projected_compute(page: Page, api_server):
    """Verify Train New Model becomes available if Compute upgrade is pending."""
    requests.post(f"{api_server}/game/reset")
    
    # Setup: Model 2, Compute 2.
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1")
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1")
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1")
    
    # Give money for C3
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1]})
    
    page.goto(api_server)
    page.wait_for_selector("#player-select option[value='1']", state="attached")
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    train_button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    
    # Initially hidden because Compute is 2
    expect(train_button).not_to_be_visible()
    
    # Place worker on Buy Chips
    buy_chips_row = page.locator("tr:has-text('Buy Chips')")
    buy_chips_btn = buy_chips_row.get_by_role("button", name="Assign Tech Worker")
    buy_chips_btn.click()
    
    expect(train_button).to_be_visible()

def test_train_model_projected_workers(page: Page, api_server):
    """Verify Train New Model becomes available if Recruitment is pending."""
    requests.post(f"{api_server}/game/reset")
    requests.post(f"{api_server}/actions/execute/marketing?player_id=1")
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1, 1, 1]})
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1")
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1")
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1")
    requests.post(f"{api_server}/actions/execute/train-model?player_id=1&worker_count=1")
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    train_model_row = page.locator("tr:has-text('Train New Model')")
    train_button = train_model_row.get_by_role("button", name="Assign Tech Worker")
    
    marketing_row = page.locator("tr:has-text('Marketing')")
    m_btn = marketing_row.get_by_role("button", name="Assign Tech Worker")
    
    # Place 1 worker on Marketing.
    m_btn.click()
    page.wait_for_timeout(500)
    
    # Now 2 workers left (2, 3). Train (needs 2) is VISIBLE.
    expect(train_button).to_be_visible()
    
    # Place worker 2 on Recruit.
    recruit_row = page.locator("tr:has-text('Recruit')")
    r_btn = recruit_row.get_by_role("button", name="Assign Tech Worker")
    r_btn.click()
    page.wait_for_timeout(500)
    
    # Handle the target sub-action modal for Recruit
    # We want to deploy the new worker to "Train New Model"
    page.locator("#choice-modal button:has-text('Train New Model')").click()
    page.wait_for_timeout(500)
    
    # Placements: M1, R2. Total 2.
    # Projected total: 4. Available: 4 - 2 = 2.
    # Train (needs 2) should be VISIBLE.
    expect(train_button).to_be_visible()
    
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
    requests.post(f"{api_server}/actions/execute/buy-chips?player_id=1")
    
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
    expect(button).to_be_visible()
    button.click()
    page.wait_for_timeout(1000)
    expect(count_cell).to_have_text("1, 2")
    
    # 3. Third upgrade (v2 -> v3, cost 2) -- Should Hide
    expect(button).not_to_be_visible()
