import pytest
import requests
from playwright.sync_api import Page, expect

@pytest.fixture(scope="module")
def api_server():
    return "http://127.0.0.1:8000"

def test_union_adjacency_presence(page: Page, api_server):
    """Verify that expansion options are derived from ALL current regions."""
    requests.post(f"{api_server}/game/reset")
    
    # Setup Player 1 with presence in 1, 2, 3
    # First expansion (Region 1 is default)
    # We need money
    requests.post(f"{api_server}/actions/execute/raise-funds", json={"player_id": 1, "chunks": [3, 3, 3]})
    
    # Manually execute scale presence for 2 and 3 via API to set up the state
    requests.post(f"{api_server}/actions/execute/scale-presence?player_id=1&region_id=2")
    requests.post(f"{api_server}/actions/execute/scale-presence?player_id=1&region_id=3")
    
    page.goto(api_server)
    page.select_option("#player-select", "1")
    
    # Now Player 1 has regions [1, 2, 3]
    # Adjacents:
    # 1: [2, 6]
    # 2: [1, 3, 7]
    # 3: [2, 4, 8]
    # Union minus current [1, 2, 3] = [4, 6, 7, 8]
    
    scale_presence_row = page.locator("tr:has-text('Scale Presence')")
    button = scale_presence_row.get_by_role("button", name="Assign Tech Worker")
    button.click()
    
    modal = page.locator("#choice-modal")
    expect(modal).to_be_visible()
    
    options = modal.locator("button")
    # Should show: Africa (4?), Central Asia (6), East Asia (7), South Asia (8)
    # Wait, check REGIONS array in app.js:
    # 1: North America, 2: South America, 3: Europe, 4: Africa, 5: Middle East, 
    # 6: Central Asia, 7: East Asia, 8: South Asia, 9: Southeast Asia, 10: Oceania
    
    # So [4, 6, 7, 8] -> Africa, Central Asia, East Asia, South Asia
    expect(options).to_have_count(4)
    
    texts = options.all_text_contents()
    texts.sort()
    expected = ["Africa", "Central Asia", "East Asia", "South Asia"]
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
    
    # 1. Expand from 1 to 6 (Central Asia)
    button.click()
    modal = page.locator("#choice-modal")
    expect(modal).to_be_visible()
    
    # Adjacents to 1: [2, 6]
    page.get_by_role("button", name="Central Asia").click()
    page.wait_for_selector("#choice-modal", state="hidden")
    
    # 2. Expand again. Options should include adjacents to 1 AND 6.
    # 1: [2, 6] -> 2 is new
    # 6: [1, 7] -> 7 is new (East Asia)
    # Expected: [2, 7] -> [South America, East Asia]
    button.click()
    expect(modal).to_be_visible()
    
    options = modal.locator("button")
    expect(options).to_have_count(2)
    
    texts = options.all_text_contents()
    texts.sort()
    expected = ["East Asia", "South America"]
    expected.sort()
    assert texts == expected
