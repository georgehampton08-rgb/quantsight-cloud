/**
 * Vanguard + Vanguard/Admin Smoke Test
 * =====================================
 * Tests every Vanguard endpoint against the live Cloud Run API.
 * Run with: npx tsx scripts/smoke_vanguard.ts
 *
 * Exit 0 = all critical endpoints pass
 * Exit 1 = one or more critical endpoints failed
 */

const BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

interface TestResult {
    name: string;
    path: string;
    method: string;
    critical: boolean;
    status?: number;
    ok: boolean;
    note?: string;
    duration?: number;
}

async function probe(
    name: string,
    path: string,
    method = 'GET',
    body?: object,
    critical = true
): Promise<TestResult> {
    const url = `${BASE}/${path}`;
    const start = Date.now();
    try {
        const res = await fetch(url, {
            method,
            headers: body ? { 'Content-Type': 'application/json' } : {},
            body: body ? JSON.stringify(body) : undefined,
        });
        const duration = Date.now() - start;
        const ok = res.status >= 200 && res.status < 400;
        let note = '';
        if (ok) {
            try {
                const json = await res.json();
                // Spot-check key fields
                if (name === 'Stats' && typeof json.health_score !== 'number') {
                    return { name, path, method, critical, status: res.status, ok: false, note: 'Missing health_score field', duration };
                }
                if (name === 'Incidents List' && !Array.isArray(json.incidents) && !Array.isArray(json)) {
                    return { name, path, method, critical, status: res.status, ok: false, note: 'incidents field is not an array', duration };
                }
                if (name === 'Learning Status' && typeof json.total_resolutions !== 'number') {
                    return { name, path, method, critical, status: res.status, ok: false, note: 'Missing total_resolutions', duration };
                }
                if (name === 'Vanguard Health' && !json.status) {
                    return { name, path, method, critical, status: res.status, ok: false, note: 'Missing status field', duration };
                }
                note = `data=${JSON.stringify(json).slice(0, 80)}…`;
            } catch {
                note = 'Non-JSON response';
            }
        }
        return { name, path, method, critical, status: res.status, ok, note, duration };
    } catch (e: any) {
        return { name, path, method, critical, ok: false, note: `Network error: ${e.message}` };
    }
}

async function main() {
    console.log('\n╔══════════════════════════════════════════════════════╗');
    console.log('║         VANGUARD SMOKE TEST — Cloud Run API          ║');
    console.log(`╚══════════════════════════════════════════════════════╝\n`);
    console.log(`Target: ${BASE}\n`);

    // Capture a real fingerprint for per-incident tests
    let sampleFingerprint = '';

    const tests: TestResult[] = [];

    // ── Core Health ───────────────────────────────────────────────────────────
    tests.push(await probe('Root Health Check', 'health', 'GET', undefined, true));
    tests.push(await probe('Vanguard Health', 'vanguard/health', 'GET', undefined, true));

    // ── Admin Stats (the main one that was broken) ────────────────────────────
    tests.push(await probe('Stats', 'vanguard/admin/stats', 'GET', undefined, true));

    // ── Incident CRUD ─────────────────────────────────────────────────────────
    const incRes = await probe('Incidents List', 'vanguard/admin/incidents?limit=5', 'GET', undefined, true);
    tests.push(incRes);
    if (incRes.ok && incRes.status === 200) {
        // Grab a fingerprint for per-incident tests
        try {
            const raw = await fetch(`${BASE}/vanguard/admin/incidents?limit=5`).then(r => r.json());
            const list = Array.isArray(raw) ? raw : (raw.incidents || []);
            if (list.length > 0) sampleFingerprint = list[0].fingerprint;
        } catch { /* ignore */ }
    }

    tests.push(await probe('Active Incidents Filter', 'vanguard/admin/incidents?status=active&limit=5', 'GET', undefined, true));

    // ── Per-incident operations (optional but validated) ──────────────────────
    if (sampleFingerprint) {
        tests.push(await probe(
            'AI Analysis Fetch',
            `vanguard/admin/incidents/${sampleFingerprint}/analysis`,
            'GET', undefined, false
        ));
        tests.push(await probe(
            'AI Analyze Trigger',
            `vanguard/admin/incidents/${sampleFingerprint}/analyze`,
            'POST', undefined, false
        ));
    } else {
        tests.push({ name: 'AI Analysis Fetch', path: 'n/a', method: 'GET', critical: false, ok: false, note: 'SKIPPED — no incidents available' });
        tests.push({ name: 'AI Analyze Trigger', path: 'n/a', method: 'POST', critical: false, ok: false, note: 'SKIPPED — no incidents available' });
    }

    // ── Learning Status ───────────────────────────────────────────────────────
    tests.push(await probe('Learning Status', 'vanguard/admin/learning/status', 'GET', undefined, true));
    tests.push(await probe('Learning Export', 'vanguard/admin/learning/export', 'GET', undefined, false));

    // ── Archives ──────────────────────────────────────────────────────────────
    tests.push(await probe('Archives List', 'vanguard/admin/archives', 'GET', undefined, false));

    // ── Cron Endpoint ─────────────────────────────────────────────────────────
    tests.push(await probe('Cron Archive', 'vanguard/admin/cron/archive', 'POST', undefined, false));

    // ── Public Routes ─────────────────────────────────────────────────────────
    tests.push(await probe('Teams Endpoint', 'teams', 'GET', undefined, true));
    tests.push(await probe('Schedule Endpoint', 'schedule', 'GET', undefined, false));

    // ── Print Results ─────────────────────────────────────────────────────────
    let criticalFailed = 0;
    let passed = 0;

    console.log('┌───────────────────────────────────────────────────────────┐');
    console.log('│ ENDPOINT TEST RESULTS                                     │');
    console.log('└───────────────────────────────────────────────────────────┘\n');

    for (const t of tests) {
        const icon = t.ok ? '✅' : (t.critical ? '❌' : '⚠️ ');
        const tag = t.critical ? '[CRITICAL]' : '[optional]';
        const ms = t.duration ? ` ${t.duration}ms` : '';
        const status = t.status ? ` HTTP ${t.status}` : '';
        console.log(`${icon} ${tag} ${t.name}`);
        console.log(`   ${t.method} /${t.path}${status}${ms}`);
        if (t.note) console.log(`   ${t.note}`);
        console.log('');

        if (t.ok) passed++;
        else if (t.critical) criticalFailed++;
    }

    const total = tests.length;
    const failed = tests.filter(t => !t.ok).length;

    console.log('═══════════════════════════════════════════════════════════');
    console.log(`  ✅ Passed:  ${passed} / ${total}`);
    console.log(`  ❌ Failed:  ${failed} (${criticalFailed} critical)`);
    console.log('═══════════════════════════════════════════════════════════\n');

    if (criticalFailed > 0) {
        console.error(`RESULT: FAIL — ${criticalFailed} critical endpoint(s) down. Do NOT deploy frontend.\n`);
        process.exit(1);
    } else {
        console.log('RESULT: PASS — All critical endpoints are operational. Safe to deploy.\n');
        process.exit(0);
    }
}

main().catch(e => {
    console.error('Smoke test crashed:', e);
    process.exit(1);
});
