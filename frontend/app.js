const GAME_ID = 1;
let PLAYER_ID = parseInt(localStorage.getItem('active_player_id')) || null;
let socket;

const ACTIONS = [
    "Buy Chips", "Recruit", "Train New Model", "Increase Net Worth",
    "Marketing", "Scale Presence", "Play Card", "Raise Funds"
];

const REGIONS = [
    "Northwest Americas", "Northeast Americas", "Western Europe", "Eastern Europe", "Northeast Asia",
    "Western Americas", "South America", "Africa", "Middle East", "Southeast Asia"
];

const WORLD_MAP = {
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
};

const PLAYER_COLORS = {
    1: "#ff0000",
    2: "#ffffff",
    3: "#ffff00",
    4: "#0000ff",
    5: "#ffc0cb"
};

// This variable will store the latest state from the server
let currentGameState = null;

async function init() {
    renderStrategyBoard();
    renderPlayerStats();
    renderWorldMap();
    connectWebSocket();
    refreshData();
}

function connectWebSocket() {
    if (socket) socket.close();
    socket = new WebSocket(`ws://127.0.0.1:8000/ws/${GAME_ID}`);
    socket.onmessage = () => refreshData();
}

function switchPlayer(newId) {
    if (!newId) return;
    PLAYER_ID = parseInt(newId);
    localStorage.setItem('active_player_id', PLAYER_ID);
    refreshData();
}

async function refreshData() {
    try {
        const response = await fetch(`http://127.0.0.1:8000/game/${GAME_ID}/state`);
        currentGameState = await response.json();

        // [NEW] Fetch Accessibility Report
        if (PLAYER_ID) {
            try {
                const availRes = await fetch(`http://127.0.0.1:8000/game/${GAME_ID}/player/${PLAYER_ID}/availability`);
                if (availRes.ok) {
                    currentGameState.availability = await availRes.json();
                }
            } catch (e) { console.warn("Availability fetch failed", e); }
        }

        // 1. Update Player Selector if needed
        updatePlayerSelector(currentGameState.players);

        // 2. Identify the active player
        const me = currentGameState.players.find(p => p.id === PLAYER_ID);

        // Validation updates require re-rendering buttons based on new state
        renderStrategyBoard();

        if (me) {
            updateUI(me);
            updateStatsTable(currentGameState.players);
            renderWorldMap();
        } else {
            document.getElementById('user-name').innerText = "NOT_SELECTED";
            addLog("System: Please select an identity from the ACT_AS menu.");
        }
    } catch (err) {
        console.error("Sync Error:", err);
        addLog(`Error: Could not connect to backend at 127.0.0.1:8000. (${err.message})`);

        // If it's a TypeError, it might be a CORS issue or the server is down
        if (err instanceof TypeError) {
            console.warn("Possible CORS or Server Down. Check if 'run.bat' terminal is active.");
        }
    }
}

function updatePlayerSelector(players) {
    const select = document.getElementById('player-select');
    if (!select || select.options.length > 1) return; // Only populate once

    players.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.id;
        opt.innerText = p.name;
        if (p.id === PLAYER_ID) opt.selected = true;
        select.appendChild(opt);
    });
}

const COMPUTE_COSTS = { 2: "$2", 3: "$3", 4: "$4", 5: "$5", 6: "$6", 7: "$7" };
const MODEL_COSTS = { 1: "1w", 2: "1w", 3: "2w", 4: "2w", 5: "3w", 6: "4w", 7: "4w" };
const WORKER_COSTS = { 4: "$2", 5: "$3", 6: "$4", 7: "$5", 8: "$6" };
const PRESENCE_COSTS_LIST = [1, 3, 4, 5, 6, 8, 10, 12, 14];

function updateStatsTable(players) {
    const container = document.getElementById('player-dashboard');
    if (!container) return;

    // Find the active player, or default to the first one for viewing if no player selected
    const me = players.find(p => p.id === PLAYER_ID) || players[0];
    if (!me) {
        container.innerHTML = "Select a player to view dashboard.";
        return;
    }

    renderPlayerDashboard(me, container);
}

function renderPlayerDashboard(player, container) {
    // Helper to generate cells for a specific row type across the 3 sections
    const generateCells = (type, section) => {
        let values = []; // Array of values to render. null means empty spacer.

        if (section === 'startup') {
            if (type === 'compute') values = [null, 1, 2];
            if (type === 'model') values = [0, 1, 2];
            if (type === 'presence') values = [2]; // 1 starting, next is 2
            if (type === 'workers') values = [3, 4]; // 3 starting
        } else if (section === 'millionaire') {
            if (type === 'compute') values = [3, 4];
            if (type === 'model') values = [3, 4];
            if (type === 'presence') values = [3, 4, 5, 6];
            if (type === 'workers') values = [5, 6];
        } else if (section === 'billionaire') {
            if (type === 'compute') values = [5, 6, 7];
            if (type === 'model') values = [5, 6, 7];
            if (type === 'presence') values = [7, 8, 9, 10];
            if (type === 'workers') values = [7, 8];
        }

        return values.map(val => {
            if (val === null) {
                // Invisible spacer
                return `<div style="min-width: 40px; margin: 0 2px; visibility: hidden;">X</div>`;
            }

            let content = "";
            let isOwned = false;
            let showX = false;

            if (type === 'compute') {
                isOwned = player.compute_level >= val;
                content = isOwned ? "X" : COMPUTE_COSTS[val] || "-";
                showX = isOwned;
            } else if (type === 'model') {
                isOwned = player.model_version >= val;
                content = isOwned ? "X" : MODEL_COSTS[val] || "-";
                showX = isOwned;
            } else if (type === 'workers') {
                isOwned = player.total_worker_count >= val;
                content = isOwned ? "X" : (val === 3 ? "X" : WORKER_COSTS[val] || "-");
                showX = isOwned;
            } else if (type === 'presence') {
                const costIndex = val - 2;
                const cost = PRESENCE_COSTS_LIST[costIndex];

                // Ensure presence_count is read validly
                const currentCount = player.presence_count || 0;
                isOwned = currentCount >= val;
                content = isOwned ? "X" : (cost !== undefined ? `$${cost}` : "-");
                showX = isOwned;
            }

            const bg = showX ? "#004d1a" : "#111";
            const color = showX ? "#00ff41" : "#888";

            return `<div style="
                background: ${bg}; 
                color: ${color}; 
                border: 1px solid #333; 
                padding: 10px; 
                text-align: center; 
                min-width: 40px; 
                margin: 0 2px;
                font-weight: bold;
            ">${content}</div>`;
        }).join('');
    };

    const styleSection = "flex: 1; border: 1px solid #00ff41; margin: 0 5px; padding: 5px; min-width: 200px;";
    const styleHeader = "text-align: center; font-weight: bold; border-bottom: 1px solid #00ff41; margin-bottom: 10px; padding-bottom: 5px;";
    const styleRow = "display: flex; justify-content: center; margin-bottom: 5px; align-items: center;";
    const styleLabel = "width: 80px; font-size: 0.8em; color: #aaa; text-align: right; padding-right: 10px;";

    const renderSection = (title, slug) => {
        let isAchieved = false;
        if (slug === 'startup') isAchieved = (player.net_worth === 0);
        if (slug === 'millionaire') isAchieved = (player.net_worth === 1);
        if (slug === 'billionaire') isAchieved = (player.net_worth === 2);

        const checkMark = isAchieved ? " (X)" : "";

        return `
        <div style="${styleSection}">
            <div style="${styleHeader}">${title}${checkMark}</div>
            
            <div style="${styleRow}">
                <div style="${styleLabel}">COMPUTE</div>
                ${generateCells('compute', slug)}
            </div>
            
            <div style="${styleRow}">
                <div style="${styleLabel}">MODEL</div>
                ${generateCells('model', slug)}
            </div>
            
            <div style="${styleRow}">
                <div style="${styleLabel}">PRESENCE</div>
                ${generateCells('presence', slug)}
            </div>

            <div style="${styleRow}">
                <div style="${styleLabel}">WORKERS</div>
                ${generateCells('workers', slug)}
            </div>
        </div>
    `;
    };

    container.innerHTML = `
        <div style="display: flex; width: 100%; justify-content: space-between; align-items: flex-start;">
            ${renderSection("STARTUP", "startup")}
            ${renderSection("MILLIONAIRE", "millionaire")}
            ${renderSection("BILLIONAIRE", "billionaire")}
        </div>
    `;
}

function updateUI(me) {
    // me is the player object we found in refreshData
    document.getElementById('user-name').innerText = me.name;
    document.getElementById('stat-power').innerText = me.power;
    document.getElementById('stat-income').innerText = me.income;
    document.getElementById('stat-subsidies').innerText = me.subsidy_tokens;
    document.getElementById('stat-corp-funds').innerText = `$${me.corporate_funds}`;
    document.getElementById('stat-pers-funds').innerText = `$${me.personal_funds}`;
    document.getElementById('stat-total-workers').innerText = me.total_worker_count;

    document.getElementById('stat-reputation').innerText = me.reputation;

    // Refresh the Strategy Board counts
    ACTIONS.forEach(action => {
        let slug = action.toLowerCase().replace(/ /g, "_");
        if (slug === 'train_new_model') slug = 'train_model'; // Normalize to backend slug

        // Get all worker numbers placed in this slot
        const placements = currentGameState.placements.filter(p => p.action_type === slug);
        const workerIds = placements.map(p => p.worker_number).sort((a, b) => a - b).join(", ");

        const cell = document.getElementById(`count-${action.toLowerCase().replace(/ /g, '-')}`);
        if (cell) cell.innerText = workerIds || "—";
    });

    renderPlayerHand(me);
    checkHandLimit(me);
}

let isDiscarding = false;
function checkHandLimit(player) {
    if (isDiscarding) return; // Prevent multiple modals
    const limit = player.hand_limit || 5;
    if (player.hand && player.hand.length > limit) {
        promptDiscardModal(player, limit);
    }
}

function promptDiscardModal(player, limit) {
    isDiscarding = true;
    const modal = document.getElementById('choice-modal');
    const titleEl = document.getElementById('modal-title');
    const descEl = document.getElementById('modal-desc');
    const optionsEl = document.getElementById('modal-options');

    titleEl.innerText = "Hand Limit Exceeded";
    descEl.innerText = `You have ${player.hand.length} cards, but your limit is ${limit}. Please select a card to discard.`;
    optionsEl.innerHTML = "";

    player.hand.forEach(card => {
        const btn = document.createElement('button');
        const displayName = card.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        btn.innerText = `Discard: ${displayName}`;
        btn.style.padding = "10px";
        btn.style.marginTop = "5px";
        btn.style.cursor = "pointer";
        btn.style.background = "#222";
        btn.style.color = "#ff0000";
        btn.style.border = "1px solid #ff0000";

        btn.onclick = async () => {
            modal.style.display = "none";
            // Call API to discard
            try {
                const response = await fetch(`http://127.0.0.1:8000/actions/discard?player_id=${PLAYER_ID}&card_id=${card.id}`, { method: "POST" });
                if (response.ok) {
                    addLog(`Discarded ${displayName}.`);
                    isDiscarding = false;
                    refreshData(); // this will re-trigger limit check if still over
                } else {
                    const err = await response.json();
                    showErrorModal("Discard Failed", err.detail || "Unknown error");
                    isDiscarding = false;
                }
            } catch (err) {
                showErrorModal("Error", err.message);
                isDiscarding = false;
            }
        };
        optionsEl.appendChild(btn);
    });

    modal.style.display = "flex";
}

function renderPlayerHand(player) {
    const container = document.getElementById('player-hand');
    if (!container) return;

    if (!player.hand || player.hand.length === 0) {
        container.innerHTML = '<div style="color: #888; font-style: italic;">Hand is empty.</div>';
        return;
    }

    container.innerHTML = player.hand.map(card => {
        const costStr = card.cost > 0 ? `Cost: ${card.cost}W` : "Free";
        const typeStr = card.is_effect ? "EFFECT" : "ACTION";
        const imgPath = card.image_file ? `assets/${card.image_file}` : '';
        const displayName = card.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

        return `
        <div style="border: 1px solid #00ff41; background: #111; width: 160px; height: 260px; padding: 10px; display: flex; flex-direction: column; align-items: center; border-radius: 5px; box-sizing: border-box;">
            <div style="font-weight: bold; font-size: 0.8rem; text-align: center; margin-bottom: 5px; height: 35px; display: flex; align-items: center; justify-content: center;">${displayName}</div>
            <img src="${imgPath}" alt="${displayName}" style="width: 120px; height: 90px; object-fit: cover; margin-bottom: 5px; border: 1px solid #333;" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMjAiIGhlaWdodD0iOTAiPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9IiMzMzMiLz48dGV4dCB4PSI2MCIgeT0iNDUiIGZvbnQtZmFtaWx5PSJDb3VyaWVyIE5ldyIgZm9udC1zaXplPSIxMiIgZmlsbD0iIzg4OCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZG9taW5hbnQtYmFzZWxpbmU9Im1lZGlhbGUiPk5PIElNRzwvdGV4dD48L3N2Zz4='">
            <div style="font-size: 0.7rem; color: #00ff41; margin-bottom: 5px; border-bottom: 1px solid #333; width: 100%; text-align: center; padding-bottom: 3px;">${typeStr} | ${costStr}</div>
            <div style="font-size: 0.65rem; color: #ddd; text-align: center; overflow-y: auto; flex-grow: 1; width: 100%;">
                ${card.requirements ? `<div style="color: #ffcc00; margin-bottom: 3px;">[Req: ${card.requirements}]</div>` : ''}
                ${card.description || 'No description available.'}
            </div>
        </div>
        `;
    }).join('');
}

// --- VALIDATION HELPERS ---

function isActionAvailable(actionSlug, player, placementCount = 0) {
    if (!currentGameState || !currentGameState.availability) {
        // Fallback to optimistic logic if API not yet fetched
        return true;
    }

    // The API uses specific slugs. map them.
    // raise_funds, play_card, marketing, buy_chips, recruit, train_model, increase_net_worth, scale_presence

    let key = actionSlug;
    if (key === 'train_new_model') key = 'train_model';

    const report = currentGameState.availability[key];
    if (!report) return true; // Default to true if missing

    return report.available;
}
async function placeWorker(actionName) {
    if (!currentGameState || !PLAYER_ID) {
        addLog("Error: Identity required. Please select a player.");
        return;
    }

    const me = currentGameState.players.find(p => p.id === PLAYER_ID);
    if (!me) return;

    let actionSlashSlug = actionName.toLowerCase().replace(/ /g, "_");
    const actionSlug = (actionSlashSlug === 'train_new_model') ? 'train_model' : actionSlashSlug;

    // Calculate count needed for Train Model
    let workersToPlaceCount = 1;
    if (actionSlug === 'train_model') {
        const myTrainPlacements = currentGameState.placements.filter(
            p => p.player_id === PLAYER_ID && p.action_type === 'train_model'
        );
        let workersUsedForTraining = myTrainPlacements.length;
        let pVersion = me.model_version;
        while (pVersion < 7) {
            const nextV = pVersion + 1;
            const costStr = MODEL_COSTS[nextV] || "1w";
            const cost = parseInt(costStr.replace('w', ''));
            if (workersUsedForTraining >= cost) {
                workersUsedForTraining -= cost;
                pVersion++;
            } else { break; }
        }
        const nextTargetV = pVersion + 1;
        const costStr = MODEL_COSTS[nextTargetV] || "1w";
        workersToPlaceCount = parseInt(costStr.replace('w', ''));
    }

    // 1. Identify which worker numbers are already on the board
    const usedNumbers = currentGameState.placements
        .filter(p => p.player_id === PLAYER_ID)
        .map(p => p.worker_number);

    // 2. Find the required number of available worker numbers
    let workersToPlace = [];
    const myRecruits = currentGameState.placements.filter(
        p => p.player_id === PLAYER_ID && p.action_type === 'recruit'
    ).length;
    const projectedTotalWorkers = me.total_worker_count + myRecruits;

    for (let i = 1; i <= projectedTotalWorkers; i++) {
        if (!usedNumbers.includes(i)) {
            workersToPlace.push(i);
            if (workersToPlace.length === workersToPlaceCount) break;
        }
    }

    if (workersToPlace.length < workersToPlaceCount) {
        addLog("System: Not enough workers available!");
        return;
    }

    let targetRegion = null;
    let targetCardId = null;

    if (actionSlug === 'play_card') {
        if (!me.hand || me.hand.length === 0) {
            showErrorModal("Play Card", "You have no cards in your hand to play.");
            return;
        }

        const playerOptions = me.hand.map(card => {
            const displayName = card.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            const costStr = card.cost > 0 ? ` [Cost: ${card.cost}W]` : " [Free]";
            return displayName + costStr;
        });

        const choice = await promptUserChoice("Select Card", "Which card would you like to verify resources for?", playerOptions);
        if (!choice) return;

        const selectedCard = me.hand.find(card => {
            const displayName = card.name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            const costStr = card.cost > 0 ? ` [Cost: ${card.cost}W]` : " [Free]";
            return (displayName + costStr) === choice;
        });
        targetCardId = selectedCard.id;
    }

    if (actionSlug === 'scale_presence') {
        const myPresence = new Set([...me.presence_regions]);

        // Add pending expansions from currentGameState
        currentGameState.placements
            .filter(p => p.player_id === PLAYER_ID && p.action_type === 'scale_presence' && p.target_region)
            .forEach(p => {
                myPresence.add(p.target_region);
            });

        // Adjacency Check: Any region adjacent to ANY OF our current or pending presence
        const neighbors = new Set();
        myPresence.forEach(rId => {
            const adj = WORLD_MAP[rId] || [];
            adj.forEach(aId => {
                if (!myPresence.has(aId)) {
                    neighbors.add(aId);
                }
            });
        });

        const playerOptions = Array.from(neighbors).map(id => REGIONS[id - 1]).sort();
        if (playerOptions.length === 0) {
            addLog("Error: No adjacent regions available for expansion.");
            showErrorModal("Scale Presence", "No adjacent regions available to expand into.");
            return;
        }

        const choice = await promptUserChoice("Expand Presence", "Select a region to expand into:", playerOptions);
        if (!choice) return;

        targetRegion = REGIONS.indexOf(choice) + 1;
    }

    // 3. Send the request matching the ActionRequest schema exactly
    try {
        const response = await fetch("http://127.0.0.1:8000/actions/place-worker", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                player_id: PLAYER_ID,
                game_id: GAME_ID,
                action_type: actionSlug,
                worker_ids: workersToPlace,
                target_region: targetRegion,
                target_card_id: targetCardId
            })
        });

        if (response.ok) {
            addLog(`Success: Workers ${workersToPlace.join(", ")} assigned to ${actionName}.`);
        } else {
            const errorData = await response.json();
            const errorMsg = errorData.detail || "Unknown error";
            addLog(`Error: ${response.status} - ${errorMsg}`);
            showErrorModal("Action Unavailable", errorMsg);
        }
    } catch (err) {
        addLog("Network Error: Connectivity lost.");
    }
}

// --- RENDER HELPERS (Keep these the same) ---

function renderPlayerStats() {
    const container = document.getElementById('stats-rows');
    if (container) container.innerHTML = '<tr><td colspan="6">Establishing Uplink...</td></tr>';
}

function renderStrategyBoard() {
    const container = document.getElementById('strategy-rows');
    if (!container) return;
    const me = currentGameState?.players.find(p => p.id === PLAYER_ID);

    container.innerHTML = ACTIONS.map(action => {
        let actionSlug = action.toLowerCase().replace(/ /g, '_');
        if (actionSlug === 'train_new_model') actionSlug = 'train_model';

        const isAvail = me ? isActionAvailable(actionSlug, me) : false;
        const btnStyle = isAvail ? "" : "display: none;";

        // Calculate Display Cost
        let displayCost = "—";
        if (me) {
            if (actionSlug === 'buy_chips') {
                displayCost = COMPUTE_COSTS[me.compute_level + 1] || "MAX";
            } else if (actionSlug === 'recruit') {
                displayCost = WORKER_COSTS[me.total_worker_count + 1] || "MAX";
            } else if (actionSlug === 'train_model') {
                // Calculate projected version to show next cost
                const myTrainPlacements = currentGameState.placements.filter(
                    p => p.player_id === PLAYER_ID && p.action_type === 'train_model'
                );
                let workersUsedForTraining = myTrainPlacements.length;
                let pVersion = me.model_version;
                while (pVersion < 7) {
                    const nextV = pVersion + 1;
                    const costStr = MODEL_COSTS[nextV] || "1w";
                    const cost = parseInt(costStr.replace('w', ''));
                    if (workersUsedForTraining >= cost) {
                        workersUsedForTraining -= cost;
                        pVersion++;
                    } else { break; }
                }
                displayCost = (pVersion < 7) ? MODEL_COSTS[pVersion + 1].toUpperCase() : "MAX";
            } else if (actionSlug === 'increase_net_worth') {
                displayCost = (me.net_worth === 0) ? "$3 (-2 REP)" : (me.net_worth === 1) ? "$5 (-4 REP)" : "MAX";
            } else if (actionSlug === 'scale_presence') {
                displayCost = `$${PRESENCE_COSTS_LIST[me.presence_count - 1] || 14}`;
            } else if (['marketing', 'play_card', 'raise_funds'].includes(actionSlug)) {
                displayCost = "FREE";
            }
        }

        const idSuffix = action.toLowerCase().replace(/ /g, '-');
        return `
        <tr>
            <td>${action}</td>
            <td>${displayCost}</td>
            <td id="count-${idSuffix}">—</td>
            <td><button onclick="placeWorker('${action}')" class="btn-worker" style="${btnStyle}">Assign Tech Worker</button></td>
        </tr>
    `}).join('');
}

function renderWorldMap() {
    const overlay = document.getElementById('presence-overlay');
    if (!overlay || !currentGameState) return;

    overlay.innerHTML = ''; // Clear existing bubbles

    const regionLayout = [
        // Top Row (IDs 1-5, left to right)
        { id: 1, x: 5, y: 5 }, // North America / Arctic
        { id: 2, x: 25, y: 5 }, // North Atlantic / Greenland
        { id: 3, x: 40, y: 5 }, // Europe / North Africa
        { id: 4, x: 60, y: 5 }, // Northern Asia
        { id: 5, x: 80, y: 5 }, // NE Asia / Pacific

        // Bottom Row (IDs 6-10, left to right)
        { id: 6, x: 5, y: 50 }, // South Pacific / West Americas
        { id: 7, x: 25, y: 50 }, // South America
        { id: 8, x: 40, y: 50 }, // Africa / South Atlantic
        { id: 9, x: 60, y: 50 }, // SE Asia / Indian Ocean
        { id: 10, x: 80, y: 50 } // Australia / Oceania
    ];

    regionLayout.forEach(layout => {
        const region = currentGameState.regions?.find(r => r.id === layout.id);
        if (!region || !region.presence_players) return;

        // Create a wrapper for this region's markers
        const markerContainer = document.createElement('div');
        markerContainer.className = 'region-marker';
        markerContainer.style.left = `${layout.x}%`;
        markerContainer.style.top = `${layout.y}%`;

        region.presence_players.forEach(playerName => {
            // Find player number from name "Player X" or "Player One"
            // Actually, the backend sends names like "Player One". 
            // We need the player ID to get the color.
            // Let's find the player object.
            const playerObj = currentGameState.players.find(p => p.name === playerName);
            if (!playerObj) return;

            const bubble = document.createElement('div');
            bubble.className = 'presence-bubble';
            bubble.innerText = `PLAYER ${playerObj.id}`; // Full text as requested
            bubble.style.backgroundColor = PLAYER_COLORS[playerObj.id] || "#888";
            // If background is white or yellow, text should be black; else white? 
            // The user wanted a bubble matching player's color.
            if ([2, 3].includes(playerObj.id)) {
                bubble.style.color = "#000";
            } else {
                bubble.style.color = "#fff";
            }
            markerContainer.appendChild(bubble);
        });

        overlay.appendChild(markerContainer);
    });
}

// --- Strategy Execution Loop ---

async function startStrategyExecution() {
    addLog("SYSTEM: Initiating Quarterly Strategy Resolution Flow...");
    console.log("EXECUTION START: refreshData...");

    try {
        await refreshData();
        if (!currentGameState) {
            addLog("CRITICAL: Could not fetch game state from server.");
            return;
        }

        // 1. Establish Resolution Order
        const p1Index = currentGameState.p1_index ?? 0;
        const playersByOrder = [...currentGameState.players].sort((a, b) => a.id - b.id);

        if (playersByOrder.length === 0) {
            addLog("SYSTEM: No players found in game state.");
            return;
        }

        const sortedPlayers = [];
        for (let i = 0; i < playersByOrder.length; i++) {
            const p = playersByOrder[(p1Index + i) % playersByOrder.length];
            if (p) sortedPlayers.push(p);
        }

        console.log("Sorted Players Mapping:", sortedPlayers.map(p => `ID:${p.id} Name:${p.name}`));
        addLog(`SEQUENCE: [${sortedPlayers.map(p => p.name).join(" -> ")}]`);

        // 2. Resolve Players Individually
        for (const player of sortedPlayers) {
            addLog(`RESOLUTION: Resolving Strategy for [${player.name}]...`);
            console.log(`Processing Player: ${player.name} (ID: ${player.id})`);

            let resolvedNums = new Set();
            let isPlayerResolved = false;

            while (!isPlayerResolved) {
                // Re-fetch placements to catch dynamic hires
                const pPlacements = currentGameState.placements
                    .filter(p => p.player_id === player.id && !resolvedNums.has(p.worker_number))
                    .sort((a, b) => a.worker_number - b.worker_number);

                console.log(`Queue for ${player.name}:`, pPlacements.map(pl => pl.worker_number));

                if (pPlacements.length === 0) {
                    isPlayerResolved = true;
                    continue;
                }

                const pl = pPlacements[0];
                addLog(`STEP: [${player.name}] resolving ${pl.action_type}...`);

                // Handle Raise Funds Aggregation (all at once for grouping bonus)
                if (pl.action_type === "raise_funds") {
                    const rfPlacements = pPlacements.filter(p => p.action_type === "raise_funds");
                    // We send the count as a single chunk to the current backend implementation
                    // which treats each chunk as a source of income.
                    await callActionEndpoint("raise-funds", {
                        player_id: player.id,
                        chunks: [rfPlacements.length]
                    });
                    rfPlacements.forEach(p => resolvedNums.add(p.worker_number));
                }
                // Handle Interactive: Recruit
                else if (pl.action_type === "recruit") {
                    // Fetch optimistic availability (ignoring that we currently have 0 workers left in the strict sense)
                    // so that the UI knows what we CAN afford with this NEW worker.
                    try {
                        const availRes = await fetch(`http://127.0.0.1:8000/game/${GAME_ID}/player/${player.id}/availability?ignore_workers_check=true`);
                        if (availRes.ok) {
                            currentGameState.availability = await availRes.json();
                        }
                    } catch (e) {
                        console.warn("Optimistic availability fetch failed", e);
                    }

                    const validateRecruitTarget = (opt) => {
                        let s = opt.toLowerCase().replace(/ /g, '_');
                        if (s === 'train_new_model') s = 'train_model';
                        return isActionAvailable(s, player);
                    };

                    const target = await promptUserChoice("Dynamic Recruitment",
                        "Select destination for the new tech talent:",
                        ACTIONS,
                        validateRecruitTarget
                    );

                    if (target) {
                        let s = target.toLowerCase().replace(/ /g, "_");
                        if (s === 'train_new_model') s = 'train_model';
                        await callActionEndpoint("recruit", { player_id: player.id, target_action: s });
                        resolvedNums.add(pl.worker_number);
                    } else {
                        addLog("SKIPPED: No valid target for recruited worker.");
                        resolvedNums.add(pl.worker_number);
                    }
                }
                // Handle Interactive: Scale Presence
                else if (pl.action_type === "scale_presence") {
                    let rId = pl.target_region;

                    if (!rId) {
                        // RE-FETCH the latest player state to avoid stale data during resolution
                        const latestPlayer = currentGameState.players.find(p => p.id === player.id);
                        const currentRegions = new Set(latestPlayer?.presence_regions || []);
                        const neighbors = new Set();

                        if (currentRegions.size === 0) {
                            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].forEach(n => neighbors.add(n));
                        } else {
                            currentRegions.forEach(rId => {
                                const adj = WORLD_MAP[rId] || [];
                                adj.forEach(n => {
                                    if (!currentRegions.has(n)) {
                                        neighbors.add(n);
                                    }
                                });
                            });
                        }

                        const availableRegions = REGIONS.filter((name, idx) => neighbors.has(idx + 1));

                        if (availableRegions.length === 0) {
                            addLog(`SKIPPED: No valid adjacent regions for expansion.`);
                            resolvedNums.add(pl.worker_number);
                            continue;
                        }

                        const reg = await promptUserChoice("Market Expansion", "Choose region to deploy presence:", availableRegions);
                        if (!reg) {
                            addLog(`SKIPPED: Expansion cancelled.`);
                            resolvedNums.add(pl.worker_number);
                            continue;
                        }
                        rId = REGIONS.indexOf(reg) + 1;
                    }

                    await callActionEndpoint("scale-presence", { player_id: player.id, region_id: rId });
                    resolvedNums.add(pl.worker_number);
                }
                // Handle Train Model Aggregation
                else if (pl.action_type === "train_model") {
                    const tmPlacements = pPlacements.filter(p => p.action_type === "train_model");
                    // We need to know the cost of the NEXT upgrade to know how many workers to use
                    // But actually, the backend might just resolve one upgrade if we send sufficient count.
                    // Let's assume we use ALL currently grouped workers for this action if they match.
                    const costStr = MODEL_COSTS[player.model_version + 1] || "1w";
                    const req = parseInt(costStr.replace('w', ''));

                    if (tmPlacements.length >= req) {
                        const usedWorkers = tmPlacements.slice(0, req);
                        await callActionEndpoint("train-model", {
                            player_id: player.id,
                            worker_count: req
                        });
                        usedWorkers.forEach(p => resolvedNums.add(p.worker_number));
                    } else {
                        addLog(`SKIPPED: Insufficient group size for [${player.name}] Train Model.`);
                        tmPlacements.forEach(p => resolvedNums.add(p.worker_number));
                    }
                }
                // Automatic Actions
                else {
                    const slug = pl.action_type.replace(/_/g, "-");
                    const params = { player_id: player.id };
                    await callActionEndpoint(slug, params);
                    resolvedNums.add(pl.worker_number);
                }

                await refreshData();
                // We don't increment i manually here because we use resolvedNums 
                // and re-filter pPlacements in the next iteration of the while loop.
            }
        }

        addLog("SYSTEM: All strategies resolved. Finalizing round...");
        await finishRound();

    } catch (err) {
        console.error("Resolution Loop Crash:", err);
        addLog(`SYSTEM FATAL: ${err.message}`);
    }
}

async function callActionEndpoint(slug, params) {
    console.log(`Calling Endpoint: ${slug} with params`, params);
    try {
        let url = `http://127.0.0.1:8000/actions/execute/${slug}`;
        let options = {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        };

        if (slug === "raise-funds") {
            options.body = JSON.stringify(params);
        } else {
            const query = new URLSearchParams(params).toString();
            url += `?${query}`;
        }

        const res = await fetch(url, options);
        const data = await res.json();

        if (res.ok) {
            addLog(`SUCCESS: ${JSON.stringify(data)}`);
        } else {
            addLog(`ERROR: ${data.detail || "Unknown Server Error"}`);
        }
    } catch (err) {
        addLog("ERROR: Request timed out or network lost.");
    }
}

async function finishRound() {
    console.log("Finalizing Round...");
    try {
        const res = await fetch(`http://127.0.0.1:8000/game/${GAME_ID}/finish-round`, { method: "POST" });
        if (res.ok) {
            const data = await res.json();
            addLog(`ROUND COMPLETE. Board reset. Next P1: Player Index ${data.new_p1_index}`);
            await refreshData();
            renderStrategyBoard(); // Reset UI IDs
        }
    } catch (err) {
        addLog("ERROR: Post-round cleanup failed.");
    }
}

// --- Modal Helper ---

// --- Modal Helper ---

function promptUserChoice(title, desc, options, validator = null) {
    return new Promise((resolve) => {
        const modal = document.getElementById('choice-modal');
        const titleEl = document.getElementById('modal-title');
        const descEl = document.getElementById('modal-desc');
        const optionsEl = document.getElementById('modal-options');

        titleEl.innerText = title;
        descEl.innerText = desc;
        optionsEl.innerHTML = "";

        options.forEach(opt => {
            // Check validation if validator provided
            if (validator && !validator(opt)) {
                return; // Skip invalid options
            }

            const btn = document.createElement('button');
            btn.innerText = opt;
            btn.style.padding = "10px";
            btn.style.margin = "5px";
            btn.style.cursor = "pointer";
            btn.style.background = "#444";
            btn.style.color = "#fff";
            btn.style.border = "1px solid #00ff41";
            btn.onclick = () => {
                modal.style.display = "none";
                resolve(opt);
            };
            optionsEl.appendChild(btn);
        });

        // Loop detection: if no options are valid, we might be stuck?
        // Add a 'Cancel' or 'Pass' option if nothing else?
        // Or if empty, resolve null
        if (optionsEl.children.length === 0) {
            const btn = document.createElement('button');
            btn.innerText = "No Valid Actions Available";
            btn.disabled = true;
            optionsEl.appendChild(btn);
            // Auto-close after delay? Or just stuck.
        }

        modal.style.display = "flex";
    });
}

function showErrorModal(title, message) {
    const modal = document.getElementById('choice-modal');
    const titleEl = document.getElementById('modal-title');
    const descEl = document.getElementById('modal-desc');
    const optionsEl = document.getElementById('modal-options');

    titleEl.innerText = title;
    descEl.innerText = message;
    optionsEl.innerHTML = "";

    const btn = document.createElement('button');
    btn.innerText = "OK";
    btn.style.padding = "10px";
    btn.style.marginTop = "20px";
    btn.style.cursor = "pointer";
    btn.style.background = "#8b0000"; // Red for error
    btn.style.color = "#fff";
    btn.style.border = "1px solid #ff0000";

    btn.onclick = () => {
        modal.style.display = "none";
    };

    optionsEl.appendChild(btn);
    modal.style.display = "flex";
}

async function undoPlacement() {
    if (!PLAYER_ID) {
        addLog("Error: Identity required.");
        return;
    }

    try {
        const response = await fetch(`http://127.0.0.1:8000/actions/undo-placement?player_id=${PLAYER_ID}`, {
            method: "POST"
        });

        if (response.ok) {
            const data = await response.json();
            addLog(`Undo: Worker ${data.worker_number} removed from ${data.from_action}.`);
            await refreshData();
        } else {
            const err = await response.json();
            addLog(`Error: ${err.detail}`);
        }
    } catch (err) {
        addLog(`System Error: ${err.message}`);
    }
}

async function resetGame() {
    if (!confirm("Are you sure you want to RESET the entire game? This cannot be undone.")) return;

    try {
        addLog("SYSTEM: Resetting Game State...");
        const response = await fetch("http://127.0.0.1:8000/game/reset", { method: "POST" });
        if (response.ok) {
            addLog("SYSTEM: Game Reset Complete. Reloading data...");
            // Clear identity
            localStorage.removeItem('active_player_id');
            PLAYER_ID = null;
            document.getElementById('user-name').innerText = "IDENTIFYING...";
            await init();
        } else {
            addLog("SYSTEM: Reset Failed.");
        }
    } catch (err) {
        addLog(`SYSTEM: Error during reset - ${err.message}`);
    }
}

function addLog(msg) {
    const log = document.getElementById('log');
    if (!log) return;
    log.innerHTML += `<div>> ${msg}</div>`;
    log.scrollTop = log.scrollHeight;
}

document.addEventListener('DOMContentLoaded', init);
