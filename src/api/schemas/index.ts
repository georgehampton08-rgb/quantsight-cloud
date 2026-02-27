import { z } from 'zod';

// Helper to asynchronously report schema validation failures to Vanguard
async function reportSchemaMismatch(endpoint: string, zError: z.ZodError) {
    try {
        const base = import.meta.env?.VITE_API_URL || 'https://quantsight-cloud-458498663186.us-central1.run.app';

        // Use the CI ingestion endpoint for silent system incidents
        await fetch(`${base}/vanguard/admin/incidents/ingest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fingerprint: `zod_mismatch_${endpoint.replace(/\//g, '_')}_${Date.now()}`,
                severity: 'YELLOW',
                error_type: 'FRONTEND_SCHEMA_MISMATCH',
                error_message: `Zod Validation Failed precisely on ${endpoint}`,
                metadata: {
                    zod_issues: zError.issues,
                    endpoint: endpoint
                }
            })
        });
    } catch (e) {
        console.warn('[Zod] Failed to report schema mismatch to Vanguard', e);
    }
}

/**
 * Validates data against a schema. Does NOT mutate the payload or block the UI.
 * Reports mismatch incidents to Vanguard directly.
 */
export function validateWithVanguard<T>(schema: z.ZodType<T>, data: any, endpointName: string): void {
    const result = schema.safeParse(data);
    if (!result.success) {
        console.warn(`[Zod] Validation mismatch on ${endpointName}:`, result.error.format());
        reportSchemaMismatch(endpointName, result.error);
    }
}

// 1. Player Profile Schema
export const PlayerProfileSchema = z.object({
    id: z.string().optional().or(z.number()), // Note based on actual live test, it was string "2544"
    name: z.string().optional(),
    team: z.string().optional(),
    position: z.string().optional(),
    avatar: z.string().optional(),
    height: z.string().optional(),
    weight: z.string().optional(),
    experience: z.string().optional(),
    narrative: z.string().optional(),
    hitProbability: z.number().optional(),
    impliedOdds: z.union([z.number(), z.string()]).optional(),
    stats: z.object({
        ppg: z.number().optional(),
        rpg: z.number().optional(),
        apg: z.number().optional(),
        confidence: z.number().optional(),
        trend: z.array(z.number()).nullable().optional()
    }).optional()
}).passthrough();

// 2. Vanguard Incident List Schema
export const VanguardIncidentListSchema = z.object({
    total: z.number().optional(),
    active: z.number().optional(),
    resolved: z.number().optional(),
    incidents: z.array(z.object({
        fingerprint: z.string().optional(),
        error_type: z.string().optional(),
        endpoint: z.string().optional(),
        occurrence_count: z.number().optional(),  // The key finding from live test!
        severity: z.string().optional(),
        status: z.string().optional(),
        first_seen: z.string().optional(),
        last_seen: z.string().optional(),
        labels: z.record(z.string(), z.any()).optional()
    })).optional()
}).passthrough();

// 3. Aegis Simulation Result Schema
// NOTE: 503 FEATURE_DISABLED responses are
// handled in the catch block before this
// schema is ever evaluated. This schema
// only runs on successful 200 responses.
export const SimulationResultSchema = z.object({
    projection: z.object({
        floor: z.number(),
        expected: z.number(), // The key finding from live test!
        ceiling: z.number(),
        variance: z.number().optional()
    }).optional()
}).passthrough();

// 4. Matchup Result Schema
// NOTE: Currently 404, when it goes live its expected properties:
export const MatchupResultSchema = z.object({
    defense_matrix: z.object({
        paoa: z.number().optional(),
        rebound_resistance: z.string().optional(),
        profile: z.record(z.string(), z.number()).optional()
    }).optional(),
    nemesis_vector: z.object({
        grade: z.string().optional(),
        status: z.string().optional(),
        avg_vs_opponent: z.number().optional(),
        delta_percent: z.number().optional()
    }).optional(),
    pace_friction: z.object({
        multiplier: z.number().optional(),
        projected_pace: z.string().optional()
    }).optional(),
    insight: z.object({
        text: z.string().optional(),
        type: z.enum(['success', 'warning', 'neutral']).optional()
    }).optional(),
    trend: z.array(z.number()).optional() // Absent safely from 404 test
}).passthrough();
