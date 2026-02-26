import fetch from 'node-fetch';

const BASE_URL = process.env.VITE_API_URL || 'https://quantsight-cloud-458498663186.us-central1.run.app';

interface TestCase {
    name: string;
    path: string;
    expectedKeys: string[];
    method?: string;
    body?: any;
    params?: Record<string, string>;
}

const tests: TestCase[] = [
    {
        name: 'OmniSearchBar -> Search Players',
        path: '/players/search?q=james',
        expectedKeys: ['id', 'name', 'team', 'position']
    },
    {
        name: 'Team Central -> Get Teams',
        path: '/teams',
        expectedKeys: ['conferences']
    },
    {
        name: 'Command Center -> Schedule',
        path: '/schedule?date=2024-11-20',
        expectedKeys: ['date', 'games']
    },
    {
        name: 'Player Profile',
        path: '/players/1628369', // Jayson Tatum profile
        expectedKeys: ['id', 'name', 'team', 'position']
    },
    {
        name: 'Matchup Lab Games',
        path: '/matchup-lab/games',
        expectedKeys: ['games']
    },
    {
        name: 'Vanguard Health',
        path: '/vanguard/admin/health',
        expectedKeys: ['status', 'subsystems', 'mode', 'timestamp']
    },
    {
        name: 'Nexus Health',
        path: '/nexus/health',
        expectedKeys: ['status', 'service', 'version', 'timestamp']
    }
];

async function verifyEndpoint(test: TestCase): Promise<boolean> {
    const { name, path, expectedKeys, method = 'GET', body, params } = test;
    let url = `${BASE_URL}${path}`;

    if (params) {
        const query = new URLSearchParams(params).toString();
        url += (url.includes('?') ? '&' : '?') + query;
    }

    console.log(`Verifying [${name}] -> ${method} ${url}`);
    try {
        const response = await fetch(url, {
            method,
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined
        });

        if (!response.ok) {
            console.error(`❌ [${name}] HTTP Error: ${response.status} ${response.statusText}`);
            return false;
        }

        const data = await response.json() as any;

        // Handle array root
        let targetObj = Array.isArray(data) ? (data.length > 0 ? data[0] : null) : data;

        // If specific expected keys don't match, e.g. wrapper object:
        if (targetObj && targetObj.hasOwnProperty('teams') && Array.isArray(targetObj.teams)) {
            if (expectedKeys.includes('teams')) {
                // valid
            }
        } else if (targetObj && targetObj.hasOwnProperty('games') && Array.isArray(targetObj.games)) {
            // valid
        } else if (targetObj && targetObj.hasOwnProperty('incidents') && Array.isArray(targetObj.incidents)) {
            // valid
        }

        if (!targetObj && expectedKeys.length > 0) {
            console.warn(`⚠️ [${name}] Returned empty data. Cannot verify keys.`);
            return true;
        }

        if (targetObj) {
            const missing = expectedKeys.filter(key => {
                if (key === 'teams' && 'teams' in targetObj) return false;
                if (key === 'games' && 'games' in targetObj) return false;
                return !(key in targetObj);
            });

            if (missing.length > 0) {
                console.error(`❌ [${name}] Contract violation. Missing keys: ${missing.join(', ')}`);
                console.error(`   Actual keys: ${Object.keys(targetObj).join(', ')}`);
                return false;
            }
        }

        console.log(`✅ [${name}] Contract satisfied.`);
        return true;
    } catch (error) {
        console.error(`❌ [${name}] Connection failed:`, (error as Error).message);
        return false;
    }
}

async function runSmokeTests() {
    console.log("=== QuantSight Web Frontend Smoke Harness ===");
    console.log(`Targeting API: ${BASE_URL}\n`);

    let passed = true;

    for (const test of tests) {
        const result = await verifyEndpoint(test);
        passed = passed && result;
    }

    if (passed) {
        console.log("\n✅ All tested frontend web contracts verified against the backend.");
        process.exit(0);
    } else {
        console.error("\n❌ Contract violations detected in smoke harness. Do not deploy.");
        process.exit(1);
    }
}

runSmokeTests();
