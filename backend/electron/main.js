const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const SystemSupervisor = require('./process_manager');
const http = require('http');

// Setup Supervisor
const supervisor = new SystemSupervisor({
    pythonPort: 5000,
    isPackaged: app.isPackaged,
    resourcesPath: app.isPackaged ? process.resourcesPath : path.join(__dirname, '../'),
    appDataPath: (process.env.APPDATA || process.env.HOME) + '/QuantSight'
});

// --- Helper: Request to Python ---
// Now uses Supervisor for readiness check
// --- Helper: Request to Python ---
// Now uses Supervisor for readiness check
async function fetchFromBackend(endpoint, method = 'GET', body = null) {
    if (supervisor.status !== 'RUNNING' && supervisor.status !== 'STARTING') {
        console.warn(`[IPC] Backend not ready (Status: ${supervisor.status}), returning null`);
        return null;
    }

    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            return await new Promise((resolve, reject) => {
                const options = {
                    hostname: '127.0.0.1',
                    port: 5000,
                    path: endpoint,
                    method: method,
                    headers: { 'Content-Type': 'application/json' }
                };

                const req = http.request(options, (res) => {
                    let data = '';
                    res.on('data', chunk => data += chunk);
                    res.on('end', () => {
                        try {
                            resolve(JSON.parse(data));
                        } catch (e) {
                            console.error("Failed to parse backend response", data);
                            resolve(null);
                        }
                    });
                });

                req.on('error', (e) => reject(e));

                if (body) req.write(JSON.stringify(body));
                req.end();
            });
        } catch (e) {
            console.warn(`[IPC] Request to ${endpoint} failed (Attempt ${attempt + 1}/${maxRetries}):`, e.message);
            if (attempt === maxRetries - 1) {
                console.error(`[IPC] Final failure for ${endpoint}`);
                return null; // Resolve null instead of throwing to prevent frontend crash
            }
            // Wait 500ms before retry
            await new Promise(r => setTimeout(r, 500));
        }
    }
}

function getAppDataPath() {
    const appDataDir = process.env.APPDATA || process.env.HOME;
    return path.join(appDataDir, 'QuantSight');
}

function ensureFirstRunMigration() {
    const appDataPath = getAppDataPath();
    const migratedMarker = path.join(appDataPath, '.migrated_v1');
    const fs = require('fs');

    if (!fs.existsSync(migratedMarker)) {
        console.log('[MIGRATION] First run detected. Initializing user directories...');
        try {
            const dirs = ['data', 'cache', 'logs'];
            dirs.forEach(dir => {
                const dirPath = path.join(appDataPath, dir);
                if (!fs.existsSync(dirPath)) fs.mkdirSync(dirPath, { recursive: true });
            });

            // Copy Data Logic (Simplified for brevity, assumes same logic as before)
            const isPackaged = app.isPackaged;
            let sourceDataPath = isPackaged
                ? path.join(process.resourcesPath, 'data')
                : path.join(__dirname, '../../nba_data'); // Strict dev path expectation

            if (fs.existsSync(sourceDataPath)) {
                console.log(`[MIGRATION] Copying data from ${sourceDataPath}`);
                const files = fs.readdirSync(sourceDataPath);
                files.forEach(file => {
                    if (file.endsWith('.csv') || file.endsWith('.json') || file.endsWith('.db')) {
                        fs.copyFileSync(path.join(sourceDataPath, file), path.join(appDataPath, 'data', file));
                    }
                });
            }
            fs.writeFileSync(migratedMarker, `Migrated on ${new Date().toISOString()}`);
        } catch (error) {
            console.error('[MIGRATION] Failed:', error);
        }
    }
    return appDataPath;
}

function createWindow() {
    const win = new BrowserWindow({
        width: 1280,
        height: 800,
        backgroundColor: '#0a192f',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
        },
        titleBarStyle: 'hiddenInset',
    });

    const isDev = process.env.npm_lifecycle_event === 'electron:dev';

    if (isDev) {
        win.loadURL('http://localhost:5173');
        win.webContents.openDevTools();
    } else {
        win.loadFile(path.join(__dirname, '../dist/index.html'));
    }
}

// --- IPC Handlers ---
ipcMain.handle('ping', () => 'pong');

ipcMain.handle('search-players', async (event, query) => {
    return await fetchFromBackend(`/players/search?q=${encodeURIComponent(query)}`) || [];
});

ipcMain.handle('get-player-profile', async (event, id) => {
    return await fetchFromBackend(`/players/${id}`);
});

ipcMain.handle('check-system-health', async () => {
    const status = await fetchFromBackend('/health');
    if (!status) {
        return {
            nba: 'critical',
            gemini: 'critical',
            database: 'critical',
            supervisor: supervisor.status
        };
    }
    return { ...status, supervisor: supervisor.status };
});

ipcMain.handle('analyze-matchup', async (event, playerId, opponent) => {
    return await fetchFromBackend(`/matchup/analyze?player_id=${playerId}&opponent=${opponent}`);
});

ipcMain.handle('save-keys', async (event, apiKey) => {
    return await fetchFromBackend('/settings/keys', 'POST', { gemini_api_key: apiKey });
});

ipcMain.handle('purge-db', async () => {
    return await fetchFromBackend('/system/purge', 'POST');
});

ipcMain.handle('get-schedule', async () => {
    return await fetchFromBackend('/schedule');
});

ipcMain.handle('save-kaggle-keys', async (event, username, key) => {
    return await fetchFromBackend('/settings/kaggle', 'POST', { username, key });
});

ipcMain.handle('sync-kaggle', async () => {
    return await fetchFromBackend('/sync/kaggle', 'POST', {});
});

ipcMain.handle('force-refresh', async (event, playerId, playerName, cachedLastGame) => {
    return await fetchFromBackend(`/sync/force-fetch?player_id=${playerId}&player_name=${encodeURIComponent(playerName)}&cached_last_game=${cachedLastGame}`, 'POST');
});

// New NBA Data IPC handlers
ipcMain.handle('get-teams', async () => { return await fetchFromBackend('/teams'); });
ipcMain.handle('get-roster', async (event, teamId) => { return await fetchFromBackend(`/roster/${teamId}`); });
ipcMain.handle('get-injuries', async () => { return await fetchFromBackend('/injuries'); });
ipcMain.handle('get-player-stats', async (event, playerId, season) => { return await fetchFromBackend(`/player/${playerId}/stats?season=${season}`); });
ipcMain.handle('get-player-career', async (event, playerId) => { return await fetchFromBackend(`/player/${playerId}/career`); });
ipcMain.handle('get-radar-dimensions', async (event, playerId, opponentId) => {
    const endpoint = opponentId ? `/radar/${playerId}?opponent_id=${opponentId}` : `/radar/${playerId}`;
    return await fetchFromBackend(endpoint);
});

// --- App Lifecycle ---

app.whenReady().then(async () => {
    ensureFirstRunMigration();

    // Start Supervisor
    await supervisor.start();

    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('will-quit', async () => {
    await supervisor.stop();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
