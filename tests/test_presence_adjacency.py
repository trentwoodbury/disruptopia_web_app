import pytest
import requests
from playwright.sync_api import Page, expect

import subprocess
import time
import os

TEST_PORT = 8000

@pytest.fixture(scope="module", autouse=True)
def api_server():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "uvicorn.exe"], capture_output=True)
    except:
        pass

    # Start the FastAPI server
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
        pytest.fail("FastAPI server failed to start for adjacency tests")

    yield f"http://127.0.0.1:{TEST_PORT}"
    
    proc.terminate()
    proc.wait()

def test_union_adjacency_presence(page: Page, api_server):
    """Verify that expansion options are derived from ALL current regions."""
    requests.post(f"{api_server}/game/reset")
    
    # Setup Player 1 with presence in 1, 2, 3
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [3, 3, 3]})
    
    # Manually execute scale presence for 2 and 3 via API
    requests.post(f"{api_server}/actions/execute/scale-presence?player_id=1&region_id=2")
    requests.post(f"{api_server}/actions/execute/scale-presence?player_id=1&region_id=3")
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    # Now Player 1 has regions [1, 2, 3]
    # 1 (Northwest Americas) -> [2 (Northeast Americas), 6 (Western Americas)]
    # 2 (Northeast Americas) -> [1, 3 (Western Europe), 7 (South America)]
    # 3 (Western Europe) -> [2, 4 (Eastern Europe), 8 (Africa)]
    # Union minus current [1, 2, 3] = [4, 6, 7, 8]
    # Names: Eastern Europe, Western Americas, South America, Africa
    
    scale_presence_row = page.locator("tr:has-text('Scale Presence')")
    button = scale_presence_row.get_by_role("button", name="Assign Tech Worker")
    button.click()
    
    modal = page.locator("#choice-modal")
    expect(modal).to_be_visible()
    
    options = modal.locator("button")
    print(f"DEBUG: Found {options.count()} options: {options.all_text_contents()}")
    
    texts = options.all_text_contents()
    texts.sort()
    expected = ["Africa", "Eastern Europe", "South America", "Western Americas"]
    expected.sort()
    assert texts == expected

def test_union_adjacency_with_pending_placements(page: Page, api_server):
    """Verify that expansion options include regions adjacent to PENDING expansions."""
    requests.post(f"{api_server}/game/reset")
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [3, 3, 3]})
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    scale_presence_row = page.locator("tr:has-text('Scale Presence')")
    button = scale_presence_row.get_by_role("button", name="Assign Tech Worker")
    
    # 1. Expand from 1 (Northwest Americas) to 6 (Western Americas)
    button.click()
    modal = page.locator("#choice-modal")
    expect(modal).to_be_visible()
    
    options_1 = modal.locator("button")
    print(f"DEBUG (1): Found {options_1.count()} options: {options_1.all_text_contents()}")
    
    # Select Western Americas (ID 6)
    page.get_by_role("button", name="Western Americas").click()
    page.wait_for_selector("#choice-modal", state="hidden")
    
    # 2. Expand again. Options should include adjacents to 1 AND 6.
    # 1 -> [2 (Northeast Americas), 6 (Pending)]
    # 6 -> [1 (Owned), 7 (South America)]
    # Expected: [Northeast Americas, South America]
    button.click()
    expect(modal).to_be_visible()
    
    options_2 = modal.locator("button")
    print(f"DEBUG (2): Found {options_2.count()} options: {options_2.all_text_contents()}")
    
    texts = options_2.all_text_contents()
    texts.sort()
    expected = ["Northeast Americas", "South America"]
    expected.sort()
    assert texts == expected
