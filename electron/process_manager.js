const { spawn, exec } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');
const os = require('os');
const EventEmitter = require('events');
const util = require('util');
const execPromise = util.promisify(exec);

/**
 * SystemSupervisor
 * 
 * A robust Process Manager for the Python Backend.
 * Responsibilities:
 * 1. Spawn and Guard the Python Process.
 * 2. Monitor Health via /health endpoint.
 * 3. Handle Auto-Restarts on crash.
 * 4. Manage clean shutdown (Zombie Killing).
 * 5. Singleton Lock to prevent multiple instances.
 * 
 * States: STOPPED, STARTING, RUNNING, ERROR, RESTARTING
 */
class SystemSupervisor extends EventEmitter {
    constructor(config) {
        super();
        this.config = {
            pythonPort: config.pythonPort || 5000,
            isPackaged: config.isPackaged || false,
            resourcesPath: config.resourcesPath || __dirname,
            appDataPath: config.appDataPath || '',
            maxRetries: 5,
            retryDelay: 2000,
        };

        this.process = null;
        this.status = 'STOPPED'; // Initial State
        this.retryCount = 0;
        this.healthCheckInterval = null;
        this.lockFilePath = path.join(
            config.appDataPath || os.homedir(),
            '.quantsight_backend.lock'
        );
    }

    /**
     * Start the backend process.
     * Handles both Development and Production (Packaged) modes.
     */
    async start() {
        if (this.status === 'RUNNING' || this.status === 'STARTING') return;

        console.log('[SUPERVISOR] Starting Backend...');
        this.updateStatus('STARTING');

        // 1. Check and clean up stale lock file
        await this._cleanStaleLock();

        // 2. Check if server is already running and healthy
        const alreadyHealthy = await this.checkHealth();
        if (alreadyHealthy) {
            console.log('[SUPERVISOR] ✅ Backend already running and healthy on port ' + this.config.pythonPort);
            console.log('[SUPERVISOR] Attaching to existing process instead of spawning new one');
            this.updateStatus('RUNNING');
            this._startHealthBeat();
            return;
        }

        // 3. Kill potential zombies
        await this.killOldProcesses();

        // 4. Wait for port to become available (max 10s)
        const portAvailable = await this._waitForPort(10);
        if (!portAvailable) {
            console.error('[SUPERVISOR] Port still occupied after cleanup. Aborting.');
            this._handleError(new Error('Port unavailable'));
            return;
        }

        // 5. Spawn
        try {
            const { cmd, args, cwd } = this._getSpawnConfig();
            console.log(`[SUPERVISOR] Spawning: ${cmd} ${args.join(' ')} (CWD: ${cwd})`);

            this.process = spawn(cmd, args, {
                cwd: cwd,
                stdio: ['ignore', 'pipe', 'pipe'],
                windowsHide: true,
                env: { ...process.env, PYTHONUNBUFFERED: '1' }
            });

            this._attachListeners();
            this._acquireLock();

        } catch (error) {
            console.error('[SUPERVISOR] Spawn failed:', error);
            this._handleError(error);
        }
    }

    /**
     * Stop the backend execution and clear intervals.
     */
    async stop() {
        console.log('[SUPERVISOR] Stopping Backend...');
        this.updateStatus('STOPPED');

        if (this.healthCheckInterval) clearInterval(this.healthCheckInterval);

        if (this.process) {
            this.process.kill(); // SIGTERM
            this.process = null;
        }

        // Release lock and force kill to be sure
        this._releaseLock();
        await this.killOldProcesses();
    }

    /**
     * Check /health endpoint.
     * Returns true if healthy (200 OK), false otherwise.
     */
    checkHealth() {
        return new Promise((resolve) => {
            const req = http.get(`http://127.0.0.1:${this.config.pythonPort}/health`, (res) => {
                if (res.statusCode === 200) {
                    this.retryCount = 0; // Reset retries on success
                    resolve(true);
                } else {
                    resolve(false);
                }
            });
            req.on('error', () => resolve(false));
            req.setTimeout(2000, () => req.abort()); // 2s Timeout
            req.end();
        });
    }

    /**
     * Clean up any previous 'api.exe' or python processes.
     */
    async killOldProcesses() {
        if (process.platform === 'win32') {
            try {
                // Kill packaged backend
                await execPromise('taskkill /F /IM api.exe /T 2>nul');
            } catch (e) { /* ignore */ }

            // In dev mode, kill python processes that are using our port
            if (!this.config.isPackaged) {
                try {
                    const { stdout } = await execPromise(`netstat -ano | findstr :${this.config.pythonPort}`);
                    const lines = stdout.split('\n');
                    const pids = new Set();

                    for (const line of lines) {
                        const match = line.match(/LISTENING\s+(\d+)/);
                        if (match) pids.add(match[1]);
                    }

                    for (const pid of pids) {
                        try {
                            await execPromise(`taskkill /F /PID ${pid}`);
                            console.log(`[SUPERVISOR] Killed process ${pid} holding port ${this.config.pythonPort}`);
                        } catch (e) { /* ignore */ }
                    }
                } catch (e) { /* No processes found */ }
            }
        }
    }

    updateStatus(newStatus) {
        this.status = newStatus;
        this.emit('status-change', this.status);
    }

    // --- Private Helpers ---

    _getSpawnConfig() {
        let cmd, args, cwd;

        if (this.config.isPackaged) {
            // Production: /resources/backend/api.exe
            cmd = path.join(this.config.resourcesPath, 'backend', 'api.exe');
            args = ['--port', this.config.pythonPort.toString()];
            cwd = path.dirname(cmd);
        } else {
            // Development: python server.py
            // Assumes we are in /electron, needs to go up to /backend
            // Correction: resourcesPath passed in should be root of project in dev
            cmd = 'python';
            const scriptPath = path.join(this.config.resourcesPath, 'backend', 'server.py');
            args = [scriptPath, '--port', this.config.pythonPort.toString()];
            cwd = path.dirname(scriptPath);
        }

        return { cmd, args, cwd };
    }

    _attachListeners() {
        if (!this.process) return;

        this.process.stdout.on('data', (data) => {
            const msg = data.toString().trim();
            console.log(`[PYTHON]: ${msg}`);
            this.emit('stdout', msg);

            // Health Signal
            if (msg.includes('AEGIS-ENGINE: Started')) {
                this.updateStatus('RUNNING');
                this._startHealthBeat();
            }
        });

        this.process.stderr.on('data', (data) => {
            const msg = data.toString().trim();
            console.error(`[PYTHON ERR]: ${msg}`);
            this.emit('stderr', msg);
        });

        this.process.on('close', (code) => {
            console.log(`[SUPERVISOR] Process exited with code ${code}`);
            if (this.status !== 'STOPPED') {
                this._handleCrash();
            }
        });
    }

    _handleCrash() {
        console.warn(`[SUPERVISOR] Unexpected Crash! Retrying... (${this.retryCount}/${this.config.maxRetries})`);
        this.updateStatus('ERROR');

        if (this.retryCount < this.config.maxRetries) {
            this.retryCount++;
            setTimeout(() => {
                this.updateStatus('RESTARTING');
                this.start();
            }, this.config.retryDelay * this.retryCount); // Exponential backoff
        } else {
            console.error('[SUPERVISOR] Max retries exceeded. Manual intervention required.');
            this.emit('fatal-error', 'Max retries exceeded');
        }
    }

    _handleError(err) {
        this.updateStatus('ERROR');
        this.emit('fatal-error', err.message);
    }

    _startHealthBeat() {
        if (this.healthCheckInterval) clearInterval(this.healthCheckInterval);

        // Check health every 30 seconds
        this.healthCheckInterval = setInterval(async () => {
            if (this.status !== 'RUNNING') return;

            const isHealthy = await this.checkHealth();
            if (!isHealthy) {
                console.warn('[SUPERVISOR] Heartbeat missed!');
                // Wait for one more check before declaring crash? 
                // For now, let's just log. If process dies, 'close' event handles it.
                // If process is zombie (running but stuck), we might need logic here to kill and restart.
            }
        }, 30000);
    }

    /**
     * Acquire lock file to mark this instance as active.
     */
    _acquireLock() {
        try {
            const lockData = {
                pid: process.pid,
                port: this.config.pythonPort,
                timestamp: new Date().toISOString()
            };
            fs.writeFileSync(this.lockFilePath, JSON.stringify(lockData));
            console.log(`[SUPERVISOR] Lock acquired: ${this.lockFilePath}`);
        } catch (e) {
            console.warn('[SUPERVISOR] Failed to write lock file:', e.message);
        }
    }

    /**
     * Release lock file on shutdown.
     */
    _releaseLock() {
        try {
            if (fs.existsSync(this.lockFilePath)) {
                fs.unlinkSync(this.lockFilePath);
                console.log('[SUPERVISOR] Lock released');
            }
        } catch (e) {
            console.warn('[SUPERVISOR] Failed to remove lock file:', e.message);
        }
    }

    /**
     * Clean up stale lock file if process no longer exists.
     */
    async _cleanStaleLock() {
        try {
            if (!fs.existsSync(this.lockFilePath)) return;

            const lockData = JSON.parse(fs.readFileSync(this.lockFilePath, 'utf8'));
            const lockPid = lockData.pid;

            // Check if process is still running (Windows)
            if (process.platform === 'win32') {
                try {
                    await execPromise(`tasklist /FI "PID eq ${lockPid}" 2>nul | find "${lockPid}"`);
                    console.log(`[SUPERVISOR] Lock file exists for running process ${lockPid}. Will attempt cleanup.`);
                } catch (e) {
                    // Process not found, lock is stale
                    console.log(`[SUPERVISOR] Stale lock detected (PID ${lockPid} not running). Cleaning up.`);
                    fs.unlinkSync(this.lockFilePath);
                }
            }
        } catch (e) {
            console.warn('[SUPERVISOR] Error checking lock file:', e.message);
            // If we can't read it, just delete it
            try {
                fs.unlinkSync(this.lockFilePath);
            } catch (e2) { /* ignore */ }
        }
    }

    /**
     * Wait for port to become available.
     * Returns true if port is free, false if still occupied after timeout.
     */
    async _waitForPort(maxSeconds) {
        for (let i = 0; i < maxSeconds; i++) {
            const isFree = await this._isPortFree();
            if (isFree) {
                console.log(`[SUPERVISOR] Port ${this.config.pythonPort} is now available`);
                return true;
            }
            console.log(`[SUPERVISOR] Waiting for port ${this.config.pythonPort}... (${i + 1}/${maxSeconds}s)`);
            await new Promise(r => setTimeout(r, 1000));
        }
        return false;
    }

    /**
     * Check if port is free (not in LISTENING state).
     */
    async _isPortFree() {
        if (process.platform === 'win32') {
            try {
                const { stdout } = await execPromise(`netstat -ano | findstr :${this.config.pythonPort}`);
                const hasListener = stdout.includes('LISTENING');
                return !hasListener;
            } catch (e) {
                return true; // netstat found nothing, port is free
            }
        }
        return true; // Assume free on non-Windows
    }
}

module.exports = SystemSupervisor;
