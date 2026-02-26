// scripts/trace_calls.ts
// Node-based verification harness for testing the isolated Phase 1A ApiContract layer.

// Polyfill missing Browser APIs for Node environment
if (typeof (global as any).window === 'undefined') {
    (global as any).window = {
        electronAPI: undefined, // Start in pure Web mode
        dispatchEvent: (event: any) => {
            console.log(`\x1b[36m[DOM Event Emitted] \x1b[35m${event.type}\x1b[0m`, event.detail ? `requestId: ${event.detail.requestId}` : '');
        }
    };
}
if (typeof (global as any).CustomEvent === 'undefined') {
    (global as any).CustomEvent = class CustomEvent {
        type: string;
        detail: any;
        constructor(type: string, options?: any) {
            this.type = type;
            this.detail = options?.detail;
        }
    };
}
if (typeof (global as any).import === 'undefined' || !(global as any).import?.meta) {
    (global as any).import = { meta: { env: { VITE_API_URL: 'https://quantsight-cloud-458498663186.us-central1.run.app' } } };
}

import { PlayerApi } from '../src/services/playerApi';
import { AegisApi } from '../src/services/aegisApi';
import { NexusApi } from '../src/services/nexusApi';

/**
 * Traces a promise execution and logs the shape of the resolved payload.
 */
async function trace<T>(name: string, fn: () => Promise<T>): Promise<T | null> {
    console.log(`\n\x1b[33m--- Executing: ${name} ---\x1b[0m`);
    try {
        const start = Date.now();
        const res = await fn();
        const elapsed = Date.now() - start;
        console.log(`\x1b[32m[SUCCESS] \x1b[0m${elapsed}ms`);

        // Print top-level keys to verify safe normalizers didn't invent random stuff
        if (typeof res === 'object' && res !== null) {
            console.log('\x1b[90mPayload Shape:\x1b[0m', Object.keys(res).join(', '));
            // Print _meta if it leaked (it shouldn't, services unwrap it)
            if ('_meta' in res) {
                console.warn('\x1b[31m[WARNING] _meta leaked into final payload!\x1b[0m');
            }
        }
        return res;
    } catch (err: any) {
        console.error(`\x1b[31m[FAILED]\x1b[0m ${err.message}`);
        return null;
    }
}

async function runTrace() {
    console.log("=========================================");
    console.log(" Phase 1A Verification: ApiContract Trace");
    console.log("=========================================\n");

    console.log("MODE 1: Pure Web (No window.electronAPI)");

    // 1. PlayerApi search (should fallback to web gracefully)
    await trace('PlayerApi.search("curry")', () => PlayerApi.search('curry'));

    // 2. PlayerApi getProfile (should test Normalizer safe logic)
    const profile = await trace('PlayerApi.getProfile("curry_steph")', () => PlayerApi.getProfile('curry_steph_123456'));
    if (profile && profile.id) {
        console.log('   \x1b[32m✓\x1b[0m Normalizer maintained valid ID field:', profile.id);
    }

    // 3. AegisApi getHealth (should execute fallback correctly since Aegis lacks IPC)
    await trace('AegisApi.getHealth()', () => AegisApi.getHealth());

    // 4. NexusApi getOverview (should attach X-Admin-Key cleanly)
    await trace('NexusApi.getOverview()', () => NexusApi.getOverview());

    // 5. Test Shadow Race (critical requirement: emitting late arrival)
    // We pass a ridiculously low patience (1ms) to force a timeout and test the event emission
    console.log(`\n\x1b[33m--- Executing Shadow-Race Trace ---\x1b[0m`);
    const simResult = await trace('AegisApi.runPatientSimulation(patience: 1ms)', () =>
        AegisApi.runPatientSimulation('curry_steph_123456', 'lakers', undefined, 1)
    );
    if (simResult) {
        console.log('   \x1b[32m✓\x1b[0m Shadow Race Resolved Source:', (simResult as any).source);
    }

    // Give background promise 2 seconds to land and trigger the late-arrival event emission
    console.log('\x1b[90mWaiting 2s for background live request to emit nexus:late-arrival ...\x1b[0m');
    await new Promise(r => setTimeout(r, 2000));


    console.log("\n=========================================");
    console.log("MODE 2: Electron Mock (with Fallback enabled)");
    console.log("=========================================");

    // Inject mock electronAPI
    (global as any).window.electronAPI = {
        getPlayerProfile: async (id: string) => {
            return { id, name: "IpcMock Player", stats: { trend: [] } };
        }
    };

    // 6. Test IPC routing
    const mockProfile = await trace('PlayerApi.getProfile("ipc_test_id") [Expect IPC Route]', () => PlayerApi.getProfile('ipc_test_id'));
    if (mockProfile && mockProfile.name === "IpcMock Player") {
        console.log('   \x1b[32m✓\x1b[0m Transport correctly routed to IPC window.electronAPI');
    }

    // 7. Test Aegis fallback in Electron Mode
    console.log('\n\x1b[90mExpect Warning: Desktop is using Cloud fallback for endpoint...\x1b[0m');
    await trace('AegisApi.getHealth() [Expect Web Fallback]', () => AegisApi.getHealth());

    console.log("\n\x1b[32m[✓] Phase 1A Verification Complete.\x1b[0m\n");
}

runTrace();
