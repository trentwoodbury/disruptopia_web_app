import pytest
import subprocess
import time
import os
import requests
from playwright.sync_api import Page, expect

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
    # 1. Reset Game to clean state
    # Use the reset endpoint which seeds everything
    requests.post(f"{api_server}/game/reset")
    
    # Load the page and point it to our test server
    page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
    page.on("requestfailed", lambda req: print(f"BROWSER REQUEST FAILED: {req.url} - {req.failure}"))
    page.set_viewport_size({"width": 1280, "height": 1024})
    page.goto(api_server)
    
    # 3. Select Player One (ID 1)
    # Wait for options to load
    page.wait_for_selector("#player-select option[value='1']", state="attached", timeout=10000)
    page.select_option("#player-select", "1")
    
    # Wait for stats to load
    page.wait_for_selector("#user-name:has-text('Player One')")

    # 4. Verify STARTUP has (X) and others don't
    expect(page.get_by_text("STARTUP (X)")).to_be_visible()
    expect(page.get_by_text("MILLIONAIRE (X)")).not_to_be_visible()
    expect(page.get_by_text("BILLIONAIRE (X)")).not_to_be_visible()
    
    # 5. Increase Net Worth to Millionaire (Level 1)
    # Costs $3, -2 Rep. Player starts with $3, 0 Rep.
    requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    
    # Trigger refresh in UI
    page.evaluate("refreshData()")
    
    # 6. Verify X has moved to MILLIONAIRE
    expect(page.get_by_text("MILLIONAIRE (X)")).to_be_visible()
    expect(page.get_by_text("STARTUP (X)")).not_to_be_visible()
    
    # 7. Increase Net Worth to Billionaire (Level 2)
    # Costs $5, -4 Rep. Min Rep -3.
    # Currently: $0, -2 Rep.
    
    # Boost reputation and power (income) via Marketing
    # Millionaire marketing: +1 Rep, +1 Power.
    # We do it 6 times: Rep -2 -> 4, Power 3 -> 9. Income -> 9.
    for _ in range(6):
        requests.post(f"{api_server}/actions/execute/marketing?player_id=1")

    # Get money (Income 9, Cap 8)
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [1]})
    
    # Now upgrade to Billionaire
    # Costs $5, -4 Rep. Current: $8, 4 Rep.
    # Outcome: $3, 0 Rep.
    res = requests.post(f"{api_server}/actions/execute/increase-net-worth?player_id=1")
    if res.status_code != 200:
        print(f"DEBUG: Billionaire upgrade failed: {res.text}")
    
    page.evaluate("refreshData()")
    
    # 8. Verify X has moved to BILLIONAIRE
    expect(page.get_by_text("BILLIONAIRE (X)")).to_be_visible()
    expect(page.get_by_text("MILLIONAIRE (X)")).not_to_be_visible()
    expect(page.get_by_text("STARTUP (X)")).not_to_be_visible()
