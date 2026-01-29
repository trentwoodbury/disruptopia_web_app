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

function updateStatsTable(players) {
    const container = document.getElementById('stats-rows');
    if (!container) return;

    container.innerHTML = players.map(p => {
        const nwLabel = p.net_worth === 0 ? "Startup" : p.net_worth === 1 ? "Millionaire" : "Billionaire";
        const isMe = p.id === PLAYER_ID ? 'style="background: #004d1a"' : '';
        return `
            <tr ${isMe}>
                <td>${p.id === PLAYER_ID ? '<strong>(YOU)</strong> ' : ''}${p.name}</td>
                <td><strong>${nwLabel}</strong></td>
                <td>${p.reputation}</td>
                <td>Lvl ${p.compute_level}</td>
                <td>v${p.model_version}.0</td>
                <td>${p.total_worker_count}</td>
            </tr>
        `;
    }).join('');
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

    // Check placed workers
    const placedCount = me.placed_worker_numbers.length;
    document.getElementById('stat-avail-workers').innerText = me.total_worker_count - placedCount;

    // Refresh the Strategy Board counts (now worker IDs)
    ACTIONS.forEach(action => {
        const slug = action.toLowerCase().replace(/ /g, "_");
        // Get all worker numbers placed in this slot
        const placements = currentGameState.placements.filter(p => p.action_type === slug);
        const workerIds = placements.map(p => p.worker_number).sort((a, b) => a - b).join(", ");

        const cell = document.getElementById(`count-${action.toLowerCase().replace(/ /g, '-')}`);
        if (cell) cell.innerText = workerIds || "—";
    });
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

    // 3. Send the request matching the ActionRequest schema exactly
    try {
        const response = await fetch("http://127.0.0.1:8000/actions/place-worker", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                player_id: PLAYER_ID,
                game_id: GAME_ID,
                action_type: actionSlug,
                worker_ids: [nextWorkerNumber],
                target_region: null
            })
        });

        if (response.ok) {
            addLog(`Success: Worker ${nextWorkerNumber} assigned to ${actionName}.`);
        } else {
            const errorData = await response.json();
            addLog(`Error: ${response.status} - ${errorData.detail}`);
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
    container.innerHTML = ACTIONS.map(action => `
        <tr>
            <td>${action}</td>
            <td id="count-${action.toLowerCase().replace(/ /g, '-')}">—</td>
            <td><button onclick="placeWorker('${action}')">Assign Tech Worker</button></td>
        </tr>
    `).join('');
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
                    const target = await promptUserChoice("Dynamic Recruitment", "Select destination for the new tech talent:", ACTIONS);
                    await callActionEndpoint("recruit", { player_id: player.id, target_action: target.toLowerCase().replace(/ /g, "_") });
                    resolvedNums.add(pl.worker_number);
                }
                // Handle Interactive: Scale Presence
                else if (pl.action_type === "scale_presence") {
                    const reg = await promptUserChoice("Market Expansion", "Choose region to deploy presence:", REGIONS);
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

function promptUserChoice(title, desc, options) {
    return new Promise((resolve) => {
        const modal = document.getElementById('choice-modal');
        const titleEl = document.getElementById('modal-title');
        const descEl = document.getElementById('modal-desc');
        const optionsEl = document.getElementById('modal-options');

        titleEl.innerText = title;
        descEl.innerText = desc;
        optionsEl.innerHTML = "";

        options.forEach(opt => {
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

        modal.style.display = "flex";
    });
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

function addLog(msg) {
    const log = document.getElementById('log');
    if (!log) return;
    log.innerHTML += `<div>> ${msg}</div>`;
    log.scrollTop = log.scrollHeight;
}

document.addEventListener('DOMContentLoaded', init);
