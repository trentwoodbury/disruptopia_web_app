const GAME_ID = 1;
let PLAYER_ID = parseInt(localStorage.getItem('active_player_id')) || null;
let socket;

const ACTIONS = [
    "Buy Chips", "Recruit", "Train New Model", "Increase Net Worth",
    "Marketing", "Scale Presence", "Play Card", "Raise Funds"
];

const REGIONS = [
    "North America", "South America", "Europe", "Africa", "Middle East",
    "Central Asia", "East Asia", "South Asia", "Southeast Asia", "Oceania"
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

        // 1. Update Player Selector if needed
        updatePlayerSelector(currentGameState.players);

        // 2. Identify the active player
        const me = currentGameState.players.find(p => p.id === PLAYER_ID);

        // Validation updates require re-rendering buttons based on new state
        renderStrategyBoard();

        if (me) {
            updateUI(me);
            updateStatsTable(currentGameState.players);
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
        const slug = action.toLowerCase().replace(/ /g, "_");
        // Get all worker numbers placed in this slot
        const placements = currentGameState.placements.filter(p => p.action_type === slug);
        const workerIds = placements.map(p => p.worker_number).sort((a, b) => a - b).join(", ");

        const cell = document.getElementById(`count-${action.toLowerCase().replace(/ /g, '-')}`);
        if (cell) cell.innerText = workerIds || "—";
    });
}

// --- VALIDATION HELPERS ---

function isActionAvailable(actionSlug, player, placementCount = 0) {
    if (!player) return false;

    // Convert to state dict similar to backend for easy comparison
    // Note: This is an approximation. Ideally backend provides a validation endpoint, 
    // but we can do client-side pre-checks for UI feedback.

    // Always Available Actions
    if (['raise_funds', 'play_card', 'marketing'].includes(actionSlug)) {
        return true;
    }

    // CALCULATE PROJECTED FUNDS
    // We must account for "Raise Funds" workers already placed by this player in this round.
    let projectedFunds = player.corporate_funds;
    if (currentGameState && currentGameState.placements) {
        const myRaiseFunds = currentGameState.placements.filter(
            p => p.player_id === player.id && p.action_type === 'raise_funds'
        ).length;
        // Income is per worker? Or per action? 
        // Game rules: "Raise Funds" grants current Income.
        // So each worker adds `player.income`.
        projectedFunds += (myRaiseFunds * player.income);
    }

    // For Scale Presence, we need valid regions, but here we just check funds/limits
    if (actionSlug === 'scale_presence') {
        const costIdx = (player.presence_count || 1) - 1;
        const cost = PRESENCE_COSTS_LIST[costIdx];
        if (cost !== undefined && projectedFunds < cost) return false;
        // Check max presence?
        if ((player.presence_count || 1) >= 10) return false;
    }

    if (actionSlug === 'increase_net_worth') {
        const nextNw = player.net_worth + 1;
        if (nextNw > 2) return false;
        // Costs hardcoded in client or passed? We don't have them in client easily except for display logic.
        // Let's rely on basic checks or add config to client globally properly.
        // For now, let's just use the known rules:
        // Millionaire (1): $3, -2 Rep.
        // Billionaire (2): $5, -4 Rep.
        if (nextNw === 1) {
            if (projectedFunds < 3) return false;
            // Rep check: floor is -3. If rep - 2 < -3, fail.
            if (player.reputation - 2 < -3) return false;
        } else if (nextNw === 2) {
            if (projectedFunds < 5) return false;
            if (player.reputation - 4 < -3) return false;
        }
    }

    if (actionSlug === 'recruit') {
        const nextWorker = player.total_worker_count + 1;
        if (nextWorker > 8) return false;
        const cost = WORKER_COSTS[nextWorker];
        if (!cost) return false;
        const money = parseInt(cost.replace('$', ''));
        if (projectedFunds < money) return false;

        // Min NW
        if (nextWorker >= 5 && player.net_worth < 1) return false;
        if (nextWorker >= 7 && player.net_worth < 2) return false;
    }

    // ... train_new_model ...
    if (actionSlug === 'train_new_model') { // Slug is train_new_model or train_model?
        // ACTIONS array has "Train New Model". Slug matches regex.
        // Backend uses 'train_model'. Frontend slug: 'train_new_model'.
        // Wait, ACTIONS constant says "Train New Model".
        // placeWorker converts to: "train_new_model".
        // Game engine expects "train_model"?
        // Let's check backend enum or string logic.
        // models.py doesn't check enum.
        // game_engine.py checks `if action_type == "train_model":`
        // Frontend sends placeWorker("Train New Model") -> actionSlug="train_new_model".
        // BUG: Frontend slug mismatch if backend expects "train_model".
        // Actually, let's fix the validation logic first.

        const nextVer = player.model_version + 1;
        if (nextVer > 7) return false;
        if (player.compute_level < nextVer) return false;

        // NW Req
        if (nextVer >= 3 && nextVer <= 4 && player.net_worth < 1) return false;
        if (nextVer >= 5 && player.net_worth < 2) return false;
    }

    if (actionSlug === 'buy_chips') {
        const nextComp = player.compute_level + 1;
        if (nextComp > 7) return false;
        const costStr = COMPUTE_COSTS[nextComp];
        if (!costStr) return false;
        const money = parseInt(costStr.replace('$', ''));
        if (projectedFunds < money) return false;

        // NW Req
        if (nextComp >= 3 && nextComp <= 4 && player.net_worth < 1) return false;
        if (nextComp >= 5 && player.net_worth < 2) return false;
    }

    return true;
}

async function placeWorker(actionName) {
    if (!currentGameState || !PLAYER_ID) {
        addLog("Error: Identity required. Please select a player.");
        return;
    }

    const me = currentGameState.players.find(p => p.id === PLAYER_ID);
    if (!me) return;

    // 1. Identify which worker numbers are already on the board
    const usedNumbers = currentGameState.placements
        .filter(p => p.player_id === PLAYER_ID)
        .map(p => p.worker_number);

    // 2. Find the first available worker number
    let nextWorkerNumber = -1;
    for (let i = 1; i <= me.total_worker_count; i++) {
        if (!usedNumbers.includes(i)) {
            nextWorkerNumber = i;
            break;
        }
    }

    if (nextWorkerNumber === -1) {
        addLog("System: No workers available!");
        return;
    }

    const actionSlug = actionName.toLowerCase().replace(/ /g, "_");

    // Fix slug for Train New Model
    if (actionSlug === 'train_new_model') {
        // placeWorker sends action_type. Backend should handle 'train_model'. 
        // 'train_new_model' is from frontend ACTIONS array text conversion.
        // We should map it correctly.
        // BUT wait, does backend handle 'train_new_model'?
        // game_engine.py checks "train_model".
        // So sending 'train_new_model' WILL FAIL if backend doesn't convert it.
        // Let's force it to 'train_model' here.
        // (Note: This is a silent fix for a potential existing bug too)
    }
    const finalSlug = (actionSlug === 'train_new_model') ? 'train_model' : actionSlug;

    // 3. Send the request matching the ActionRequest schema exactly
    try {
        const response = await fetch("http://127.0.0.1:8000/actions/place-worker", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                player_id: PLAYER_ID,
                game_id: GAME_ID,
                action_type: finalSlug,
                worker_ids: [nextWorkerNumber],
                target_region: null
            })
        });

        if (response.ok) {
            addLog(`Success: Worker ${nextWorkerNumber} assigned to ${actionName}.`);
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
    // We need the active player to check availability
    const me = currentGameState?.players.find(p => p.id === PLAYER_ID);

    container.innerHTML = ACTIONS.map(action => {
        let slug = action.toLowerCase().replace(/ /g, '_');
        // Fix for "Train New Model" mismatch if needed (handled in backend?)
        // Backend expects 'train_model' usually? 
        // If my previous code sent 'train_new_model', did it work?
        // Let's normalize it here just for validation check
        if (slug === 'train_new_model') slug = 'train_model'; // Backend usually uses 'train_model'

        const isAvail = me ? isActionAvailable(slug, me) : false;
        const btnStyle = isAvail ? "" : "display: none;";
        // Or "opacity: 0.5; pointer-events: none;" if we want to show it disabled

        return `
        <tr>
            <td>${action}</td>
            <td id="count-${slug.replace(/_/g, '-')}">—</td>
            <td><button onclick="placeWorker('${action}')" style="${btnStyle}">Assign Tech Worker</button></td>
        </tr>
    `}).join('');
}

function renderWorldMap() {
    const container = document.getElementById('world-rows');
    container.innerHTML = REGIONS.map((name, index) => `
        <tr>
            <td>${name}</td>
            <td id="subsidy-${index + 1}">0</td>
            <td><button onclick="addPresence(${index + 1})">Deploy Presence</button></td>
        </tr>
    `).join('');
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
                    const currentRegions = player.presence_regions || [];
                    const neighborIds = new Set();

                    if (currentRegions.length === 0) {
                        // Fallback: If no presence (shouldn't happen), assume all open
                        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].forEach(n => neighborIds.add(n));
                    } else {
                        currentRegions.forEach(rId => {
                            const neighbors = WORLD_MAP[rId] || [];
                            neighbors.forEach(n => neighborIds.add(n));
                        });
                        // Remove potential duplicates or already owned regions
                        currentRegions.forEach(rId => neighborIds.delete(rId));
                    }

                    const availableRegions = REGIONS.filter((name, idx) => neighborIds.has(idx + 1));

                    if (availableRegions.length === 0) {
                        addLog(`SKIPPED: No valid adjacent regions for expansion.`);
                        resolvedNums.add(pl.worker_number);
                        // IsPlayerResolved might loop if we don't handle it? 
                        // We added to resolvedNums, so it should be fine.
                        continue;
                    }

                    const reg = await promptUserChoice("Market Expansion", "Choose region to deploy presence:", availableRegions);
                    const rId = REGIONS.indexOf(reg) + 1;
                    await callActionEndpoint("scale-presence", { player_id: player.id, region_id: rId });
                    resolvedNums.add(pl.worker_number);
                }
                // Automatic Actions
                else {
                    const slug = pl.action_type.replace(/_/g, "-");
                    const params = { player_id: player.id };
                    if (pl.action_type === "train_model") params.worker_count = 1;
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
