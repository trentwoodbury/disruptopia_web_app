const GAME_ID = 1;
const PLAYER_ID = 1;
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
    renderWorldMap();
    connectWebSocket();
    refreshData();
}

function connectWebSocket() {
    socket = new WebSocket(`ws://localhost:8000/ws/${GAME_ID}`);
    socket.onmessage = () => refreshData();
}

async function refreshData() {
    try {
        const response = await fetch(`http://localhost:8000/game/${GAME_ID}/state`);
        currentGameState = await response.json();

        // DEBUG: See who is actually in the database
        console.log("Players found in DB:", currentGameState.players);

        // If PLAYER_ID 1 isn't found, let's grab the first player available
        // just so the MVP works while we're testing.
        const me = currentGameState.players.find(p => p.id === PLAYER_ID) || currentGameState.players[0];

        if (me) {
            // Update the global PLAYER_ID to match the actual ID from the DB
            // (Only do this for the MVP skeleton)
            // PLAYER_ID = me.id;
            updateUI(me);
        } else {
            addLog("Error: No players found in this game.");
        }
    } catch (err) {
        console.error("Sync Error:", err);
        addLog("Error: Could not connect to backend.");
    }
}

function updateUI(me) {
    // me is the player object we found in refreshData
    document.getElementById('user-name').innerText = me.name;
    document.getElementById('stat-power').innerText = me.power;
    document.getElementById('stat-income').innerText = me.income;
    document.getElementById('stat-total-workers').innerText = me.total_worker_count;

    // Check placed workers
    const placedCount = me.placed_worker_numbers.length;
    document.getElementById('stat-avail-workers').innerText = me.total_worker_count - placedCount;

    // Refresh the Strategy Board counts
    ACTIONS.forEach(action => {
        const slug = action.toLowerCase().replace(/ /g, "_");
        // Count how many workers (from ANY player) are in this slot
        const count = currentGameState.placements.filter(p => p.action_type === slug).length;
        const cell = document.getElementById(`count-${action.toLowerCase().replace(/ /g, '-')}`);
        if (cell) cell.innerText = count;
    });
}

async function placeWorker(actionName) {
    if (!currentGameState) return;

    const me = currentGameState.players.find(p => p.id === PLAYER_ID);

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
            console.error("422 Details:", errorData.detail); // This helps see exactly what failed
            addLog(`Error: ${response.status} - Check console for details.`);
        }
    } catch (err) {
        addLog("Network Error: Connectivity lost.");
    }
}

// --- RENDER HELPERS (Keep these the same) ---

function renderStrategyBoard() {
    const container = document.getElementById('strategy-rows');
    container.innerHTML = ACTIONS.map(action => `
        <tr>
            <td>${action}</td>
            <td id="count-${action.toLowerCase().replace(/ /g, '-')}">0</td>
            <td><button onclick="placeWorker('${action}')">Assign Tech Worker</button></td>
        </tr>
    `).join('');
}

function renderWorldMap() {
    const container = document.getElementById('world-rows');
    container.innerHTML = REGIONS.map((name, index) => `
        <tr>
            <td>${name}</td>
            <td id="subsidy-${index+1}">0</td>
            <td><button onclick="addPresence(${index+1})">Deploy Presence</button></td>
        </tr>
    `).join('');
}

function addLog(msg) {
    const log = document.getElementById('log');
    log.innerHTML += `<div>> ${msg}</div>`;
    log.scrollTop = log.scrollHeight;
}

document.addEventListener('DOMContentLoaded', init);