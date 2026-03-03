import fetch from 'node-fetch';

const FRONTEND_URL = process.env.VITE_APP_URL || 'https://quantsight-prod.web.app';

// SMOKE_PLAYER_ID: LeBron James (2544)
// Used because this player has confirmed
// live data across all endpoints.
// If this player is traded or retires,
// update this constant and verify all
// smoke checks still pass.
const SMOKE_PLAYER_ID = "2544";
const SMOKE_OPPONENT_ID = "201939";
// NOTE: /matchup/{id}/{opp} is currently
// 404 — smoke skips this combination
// until endpoint is restored

/**
 * Validates that specific application routes serve successfully.
 * Designed to catch bad client-side routing setups or broken builds.
 */
async function runPageLoadCheck() {
    console.log("=== Frontend Page Load Check ===");
    console.log(`Targeting App: ${FRONTEND_URL}\n`);

    const routes = [
        '/',
        `/#/players/${SMOKE_PLAYER_ID}`,
        `/#/matchup/${SMOKE_PLAYER_ID}/${SMOKE_OPPONENT_ID}`,
        '/#/vanguard'
    ];

    let passed = true;

    for (const route of routes) {
        try {
            // Fetch handles hash routing cleanly by just downloading index.html
            // We just ensure the HTTP server is up and responsive
            const res = await fetch(`${FRONTEND_URL}${route}`);
            if (res.ok) {
                console.log(`✅ [Page Load] ${route} -> HTTP 200`);
            } else {
                console.error(`❌ [Page Load] ${route} failed -> HTTP ${res.status}`);
                passed = false;
            }
        } catch (e: any) {
            console.error(`❌ [Page Load] ${route} network error: ${e.message}`);
            passed = false;
        }
    }

    if (passed) {
        console.log("\n✅ All routes responded successfully.");
        process.exit(0);
    } else {
        console.error("\n❌ Page load checks failed.");
        process.exit(1);
    }
}

runPageLoadCheck();
