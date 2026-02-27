// @ts-ignore
import { describe, it, expect } from 'vitest';
import {
    normalizePlayerProfile,
    normalizeVanguardIncidentList,
    normalizeSimulationResult,
    normalizeMatchupResult
} from '../normalizers';

describe('API Normalizers', () => {

    describe('normalizePlayerProfile', () => {
        it('maps "id" field correctly based on live endpoint structure', () => {
            const raw = {
                id: '2544',
                name: 'LeBron James',
                stats: { ppg: 25.4, trend: [-1, 0, 1] }
            };
            const result = normalizePlayerProfile(raw);
            expect(result.id).toBe('2544');
            expect(result.name).toBe('LeBron James');
            expect(result.stats.ppg).toBe(25.4);
            expect(result.stats.trend).toEqual([-1, 0, 1]);
        });

        it('provides safe defaults for empty profile payload', () => {
            const result = normalizePlayerProfile(null);
            expect(result.id).toBe('unknown');
            expect(result.name).toBe('Unknown Player');
            expect(result.stats.trend).toEqual([]);
        });
    });

    describe('normalizeVanguardIncidentList', () => {
        it('unwraps .incidents nested array and maps occurrence_count', () => {
            const raw = {
                total: 1,
                active: 1,
                incidents: [
                    {
                        fingerprint: '123_abc',
                        occurrence_count: 5,
                        status: 'ACTIVE'
                    }
                ]
            };
            const result = normalizeVanguardIncidentList(raw);
            expect(Array.isArray(result)).toBe(true);
            expect(result.length).toBe(1);
            expect(result[0].fingerprint).toBe('123_abc');
            expect(result[0].occurrence_count).toBe(5);
        });

        it('returns empty array when .incidents is missing or malformed', () => {
            expect(normalizeVanguardIncidentList({ total: 0 })).toEqual([]);
            expect(normalizeVanguardIncidentList(null)).toEqual([]);
            expect(normalizeVanguardIncidentList({ incidents: "not_an_array" })).toEqual([]);
        });
    });

    describe('normalizeSimulationResult', () => {
        it('handles case 1: 503 error body with detail.code FEATURE_DISABLED', () => {
            const raw = {
                detail: {
                    status: 'unavailable',
                    code: 'FEATURE_DISABLED',
                    feature: 'FEATURE_AEGIS_SIM_ENABLED'
                }
            };
            const result = normalizeSimulationResult(raw);
            expect(result.available).toBe(false);
            expect(result.reason).toBe('simulation_disabled');
            expect(result.feature_flag).toBe('FEATURE_AEGIS_SIM_ENABLED');
            expect(result.projections).toBeNull();
        });

        it('handles case 2: real data with expected field', () => {
            const raw = {
                projection: {
                    floor: 18.5,
                    expected: 22.1,
                    ceiling: 28.0,
                    variance: 1.1
                }
            };
            const result = normalizeSimulationResult(raw);
            expect(result.available).toBe(true);
            expect(result.reason).toBeNull();
            expect(result.projections?.expected).toBe(22.1);
            expect(result.projections?.floor).toBe(18.5);
            expect(result.projections?.ceiling).toBe(28.0);
            expect(result.projections?.variance).toBe(1.1);
        });

        it('handles case 3: unknown error or totally stub result', () => {
            const result = normalizeSimulationResult({});
            expect(result.available).toBe(false);
            expect(result.reason).toBe('unknown_error');
            expect(result.projections).toBeNull();

            const result2 = normalizeSimulationResult(null);
            expect(result2.available).toBe(false);
        });
    });

    describe('normalizeMatchupResult', () => {
        it('returns safe defaults with empty trend array on 404 or empty response', () => {
            const raw404 = { detail: 'Not Found' };
            const result404 = normalizeMatchupResult(raw404);
            expect(result404.trend).toEqual([]);
            expect(result404.defense_matrix.paoa).toBe(0);

            const resultNull = normalizeMatchupResult(null);
            expect(resultNull.trend).toEqual([]);
        });

        it('handles partial incoming data gracefully if/when fixed', () => {
            const raw = {
                trend: [1.2, -0.5],
                defense_matrix: { paoa: -2.3 }
            };
            const result = normalizeMatchupResult(raw);
            expect(result.trend).toEqual([1.2, -0.5]);
            expect(result.defense_matrix.paoa).toBe(-2.3);
            expect(result.nemesis_vector.avg_vs_opponent).toBe(0);
        });
    });

});
