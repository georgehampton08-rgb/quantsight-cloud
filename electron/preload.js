const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    ping: () => ipcRenderer.invoke('ping'),
    searchPlayers: (query) => ipcRenderer.invoke('search-players', query),
    getPlayerProfile: (id) => ipcRenderer.invoke('get-player-profile', id),
    checkSystemHealth: () => ipcRenderer.invoke('check-system-health'),
    analyzeMatchup: (playerId, opponent) => ipcRenderer.invoke('analyze-matchup', playerId, opponent),
    saveKeys: (apiKey) => ipcRenderer.invoke('save-keys', apiKey),
    saveKaggleKeys: (username, key) => ipcRenderer.invoke('save-kaggle-keys', username, key),
    syncKaggle: () => ipcRenderer.invoke('sync-kaggle'),
    purgeDb: () => ipcRenderer.invoke('purge-db'),
    getSchedule: () => ipcRenderer.invoke('get-schedule'),
    forceRefresh: (playerId, playerName, cachedLastGame) => ipcRenderer.invoke('force-refresh', playerId, playerName, cachedLastGame),
    // New NBA Data endpoints
    getTeams: () => ipcRenderer.invoke('get-teams'),
    getRoster: (teamId) => ipcRenderer.invoke('get-roster', teamId),
    getInjuries: () => ipcRenderer.invoke('get-injuries'),
    getPlayerStats: (playerId, season) => ipcRenderer.invoke('get-player-stats', playerId, season),
    getPlayerCareer: (playerId) => ipcRenderer.invoke('get-player-career', playerId),
    // Radar dimensions (real math, not hardcoded!)
    getRadarDimensions: (playerId, opponentId) => ipcRenderer.invoke('get-radar-dimensions', playerId, opponentId),
});
