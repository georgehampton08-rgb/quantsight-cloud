/**
 * QuantSight Frontend Text Sanitizer
 * ====================================
 * Strip HTML tags and dangerous characters from any user-supplied string
 * before rendering in the React tree.
 *
 * Usage:
 *   import { sanitizeText } from '../utils/sanitize';
 *   <p>{sanitizeText(injuryDesc)}</p>
 *
 * Apply to: injury_desc, annotation text, search queries rendered in DOM,
 *           any field that comes from user input and is displayed via JSX.
 */

/**
 * Strips HTML tags, script injections, and dangerous characters.
 * Returns a safe, trimmed substring up to maxLength.
 */
export function sanitizeText(input: unknown, maxLength = 2000): string {
    if (typeof input !== 'string') return '';
    return input
        .replace(/<script[\s\S]*?<\/script>/gi, '')  // strip script blocks
        .replace(/<[^>]*>/g, '')                      // strip all HTML tags
        .replace(/[<>&"'`]/g, '')                     // strip remaining dangerous chars
        .trim()
        .slice(0, maxLength);
}

/**
 * Validate that a string is a safe player/entity ID.
 * Returns null if invalid (caller should discard).
 */
export function sanitizeId(input: string): string | null {
    if (!/^[a-zA-Z0-9_\-]{1,128}$/.test(input)) return null;
    return input;
}

/**
 * Validate a date string is YYYY-MM-DD.
 * Returns null if invalid.
 */
export function sanitizeDate(input: string): string | null {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(input)) return null;
    return input;
}
