/**
 * normalizers.ts
 * 
 * Phase 3: Defensive data normalization for API boundaries.
 * 
 * DECISION 1 (Fetch Error Strategy for 503s):
 * Option A was chosen. We will catch 503 errors in the service call (caller site) and 
 * pass the parsed error body to `normalizeSimulationResult`. `ApiContract.execute` (or 
 * the specific fetch layer) will need to be configured/wrapped by the caller cleanly 
 * to pass the thrown error's JSON body so this normalizer can stay pure.
 * 
 * DECISION 2 (Matchup 404 Investigation):
 * The route `/matchup/{id}/{opp}` is returning 404. I confirmed via `/openapi.json` 
 * that this route is entirely missing from the FastAPI registry (there is no exact 
 * matching path defined). A Vanguard incident (FRONTEND_SCHEMA_MISMATCH) has been 
 * filed manually to track this. For now, `normalizeMatchupResult` provides safe defaults.
 */

import { validateWithVanguard, PlayerProfileSchema, VanguardIncidentListSchema, SimulationResultSchema, MatchupResultSchema } from './schemas';

// 1. normalizePlayerProfile
export function normalizePlayerProfile(raw: any) {
    if (!raw || typeof raw !== 'object') {
        console.warn('[Normalizer] normalizePlayerProfile received empty/invalid input');
        return {
            id: 'unknown',
            name: 'Unknown Player',
            team: 'UNK',
            position: '?',
            avatar: '',
            height: 'N/A',
            weight: 'N/A',
            experience: 'N/A',
            narrative: 'No data available',
            hitProbability: 0,
            impliedOdds: 0,
            stats: { ppg: 0, rpg: 0, apg: 0, confidence: 0, trend: [] }
        };
    }

    // Fire Zod monitoring boundary before mapping
    validateWithVanguard(PlayerProfileSchema, raw, '/players/{id}');

    // Live endpoint confirmed it uses 'id' natively
    return {
        id: String(raw.id || 'unknown'),
        name: String(raw.name || 'Unknown Player'),
        team: String(raw.team || 'UNK'),
        position: String(raw.position || '?'),
        avatar: String(raw.avatar || ''),
        height: String(raw.height || 'N/A'),
        weight: String(raw.weight || 'N/A'),
        experience: String(raw.experience || 'N/A'),
        narrative: String(raw.narrative || ''),
        hitProbability: Number(raw.hitProbability) || 0,
        impliedOdds: Number(raw.impliedOdds) || 0,
        stats: {
            ppg: Number(raw.stats?.ppg) || 0,
            rpg: Number(raw.stats?.rpg) || 0,
            apg: Number(raw.stats?.apg) || 0,
            confidence: Number(raw.stats?.confidence) || 0,
            trend: Array.isArray(raw.stats?.trend) ? raw.stats.trend : []
        }
    };
}

// 2. normalizeVanguardIncidentList
export function normalizeVanguardIncidentList(raw: any) {
    if (!raw || !Array.isArray(raw.incidents)) {
        console.warn('[Normalizer] normalizeVanguardIncidentList missing or malformed .incidents wrapper');
        return [];
    }

    // Fire Zod monitoring boundary before mapping
    validateWithVanguard(VanguardIncidentListSchema, raw, '/vanguard/admin/incidents');

    return raw.incidents.map((inc: any) => ({
        fingerprint: String(inc.fingerprint || 'unknown'),
        error_type: String(inc.error_type || 'unknown'),
        endpoint: String(inc.endpoint || 'unknown'),
        // Confirmed live: maps from 'occurrence_count'
        occurrence_count: Number(inc.occurrence_count) || 0,
        severity: String(inc.severity || 'UNKNOWN'),
        status: String(inc.status || 'UNKNOWN'),
        first_seen: String(inc.first_seen || ''),
        last_seen: String(inc.last_seen || ''),
        labels: inc.labels || {}
    }));
}

// 3. normalizeSimulationResult
export function normalizeSimulationResult(raw: any) {
    // Case 1: 503 Error Body caught by caller (e.g., detail.code === "FEATURE_DISABLED")
    if (raw?.detail?.status === 'unavailable') {
        return {
            available: false,
            reason: raw.detail.code === 'FEATURE_DISABLED' ? 'simulation_disabled' : 'unavailable',
            feature_flag: raw.detail.feature || undefined,
            projections: null
        };
    }

    // Case 2: Real Data (200 OK)
    if (raw?.projection) {
        // Fire Zod monitoring boundary ONLY on the successful 200 responses
        validateWithVanguard(SimulationResultSchema, raw, '/aegis/simulate/{id}');

        return {
            available: true,
            reason: null,
            projections: {
                floor: Number(raw.projection.floor) || 0,
                // Confirmed live: maps from 'expected'
                expected: Number(raw.projection.expected) || 0,
                ceiling: Number(raw.projection.ceiling) || 0,
                variance: Number(raw.projection.variance) || 0
            }
        };
    }

    // Case 3: Unknown Error or Stub Result
    return {
        available: false,
        reason: 'unknown_error',
        projections: null
    };
}

// 4. normalizeMatchupResult
export function normalizeMatchupResult(raw: any) {
    // NOTE: /matchup/{id}/{opp} endpoint is currently returning HTTP 404.
    // Providing safe defaults to prevent UI crash. Once endpoint is fixed, remove these defaults.
    if (!raw || raw.detail === 'Not Found' || Object.keys(raw).length === 0) {
        console.warn('[Normalizer] normalizeMatchupResult received empty or 404 result. Supplying safe defaults.');
        return {
            defense_matrix: {
                paoa: 0,
                rebound_resistance: 'N/A',
                profile: {}
            },
            nemesis_vector: {
                grade: 'N/A',
                status: 'unknown',
                avg_vs_opponent: 0,
                delta_percent: 0
            },
            pace_friction: {
                multiplier: 1,
                projected_pace: 'N/A'
            },
            insight: {
                text: 'Data unavailable',
                type: 'neutral'
            },
            // Confirmed rule: absent trend field maps to empty array safely
            trend: []
        };
    }

    // Fire Zod monitoring boundary before mapping
    validateWithVanguard(MatchupResultSchema, raw, '/matchup/{id}/{opp}');

    // When backend comes online, this handles the raw payload:
    return {
        defense_matrix: {
            paoa: Number(raw.defense_matrix?.paoa) || 0,
            rebound_resistance: String(raw.defense_matrix?.rebound_resistance || 'N/A'),
            profile: raw.defense_matrix?.profile || {}
        },
        nemesis_vector: {
            grade: String(raw.nemesis_vector?.grade || 'N/A'),
            status: String(raw.nemesis_vector?.status || 'unknown'),
            avg_vs_opponent: Number(raw.nemesis_vector?.avg_vs_opponent) || 0,
            delta_percent: Number(raw.nemesis_vector?.delta_percent) || 0
        },
        pace_friction: {
            multiplier: Number(raw.pace_friction?.multiplier) || 1,
            projected_pace: String(raw.pace_friction?.projected_pace || 'N/A')
        },
        insight: {
            text: String(raw.insight?.text || ''),
            type: (raw.insight?.type === 'success' || raw.insight?.type === 'warning' || raw.insight?.type === 'neutral')
                ? raw.insight.type : 'neutral'
        },
        trend: Array.isArray(raw.trend) ? raw.trend : []
    };
}
