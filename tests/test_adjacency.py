import pytest
from backend.database import SessionLocal, engine
from backend.models import Base, Player, Presence
from backend.seed import seed_initial_game

@pytest.fixture
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_initial_game()
    db = SessionLocal()
    yield db
    db.close()

def test_presence_adjacency_filtering(db_session):
    """
    Simulate the logic used in frontend (but in python) to verify adjacency calculations.
    """
    player = db_session.get(Player, 1)
    
    # 1. Verify Initial Seed
    # Player 1 should be at Region 1.
    initial_presence = [p.region_id for p in player.presence]
    # NOTE: The seed might randomize or set specific. 
    # Current seed code: db.add(Presence(player_id=p1.id, region_id=1...))
    assert 1 in initial_presence
    
    # 2. Calculate Neighbors (Frontend Logic Simulation)
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
    
    current_regions = initial_presence
    neighbor_ids = set()
    for r_id in current_regions:
        neighbors = WORLD_MAP.get(r_id, [])
        for n in neighbors:
            neighbor_ids.add(n)
            
    # Remove own regions
    for r_id in current_regions:
        if r_id in neighbor_ids:
            neighbor_ids.remove(r_id)
            
    valid_options = sorted(list(neighbor_ids))
    
    # Region 1 neighbors are 2 and 6.
    assert 2 in valid_options
    assert 6 in valid_options
    assert 3 not in valid_options # Not adjacent to 1
    assert len(valid_options) == 2
    
    # 3. Simulate Expansion
    # Add Region 2
    db_session.add(Presence(player_id=player.id, region_id=2))
    db_session.commit()
    db_session.refresh(player)
    
    current_regions = [p.region_id for p in player.presence] # [1, 2]
    neighbor_ids = set()
    for r_id in current_regions:
        neighbors = WORLD_MAP.get(r_id, [])
        for n in neighbors:
            neighbor_ids.add(n)
            
    for r_id in current_regions:
        if r_id in neighbor_ids:
            neighbor_ids.remove(r_id)
            
    valid_options = sorted(list(neighbor_ids))
    # Neighbors of 1: [2, 6]
    # Neighbors of 2: [1, 3, 7]
    # total: {1, 2, 3, 6, 7}
    # minus own {1, 2}
    # result: {3, 6, 7}
    
    assert 3 in valid_options
    assert 6 in valid_options
    assert 7 in valid_options
    assert 1 not in valid_options
    assert 2 not in valid_options
