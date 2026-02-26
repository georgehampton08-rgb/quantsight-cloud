import fetch from 'node-fetch';

const BASE_URL = process.env.VITE_API_URL || 'http://localhost:8000';

async function verifyEndpoint(name: string, path: string, expectedKeys: string[]) {
    console.log(`Verifying [${name}] -> ${path}`);
    try {
        const response = await fetch(`${BASE_URL}${path}`);
        if (!response.ok) {
            console.error(`❌ [${name}] HTTP Error: ${response.status}`);
            return false;
        }

        const data = await response.json();
        const targetObj = Array.isArray(data) ? (data.length > 0 ? data[0] : null) : data;

        if (!targetObj && expectedKeys.length > 0) {
            console.warn(`⚠️ [${name}] Returned empty data. Cannot verify keys.`);
            return true;
        }

        if (targetObj) {
            const missing = expectedKeys.filter(key => !(key in targetObj));
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

async function runSmokeTest() {
    console.log("=== QuantSight Frontend Contract Verification ===");
    console.log(`Targeting API: ${BASE_URL}\n`);

    let passed = true;

    passed = await verifyEndpoint('Teams', '/teams', ['teams']) && passed;
    passed = await verifyEndpoint('System Health', '/vanguard/admin/stats', ['health_score', 'active_incidents']) && passed;
    // We can add more specific endpoint checks like Player Search, Roster, etc., given actual player/team IDs

    if (passed) {
        console.log("\n✅ All tested frontend contracts verified against the backend.");
        process.exit(0);
    } else {
        console.error("\n❌ Contract violations detected. Frontend may break if deployed.");
        process.exit(1);
    }
}

runSmokeTest();
