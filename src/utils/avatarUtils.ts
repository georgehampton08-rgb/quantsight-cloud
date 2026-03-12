/**
 * Player avatar utilities
 * Primary: ESPN CDN (espnId) — reliable, no auth, fast
 * Fallback: NBA CDN (nbaId) — still works, kept for compatibility
 */

const PLACEHOLDER = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"%3E%3Ccircle cx="50" cy="50" r="50" fill="%23374151"/%3E%3Ctext x="50" y="55" font-size="40" text-anchor="middle" fill="%239CA3AF"%3E?%3C/text%3E%3C/svg%3E';

/**
 * Get player avatar URL.
 * Prefers ESPN CDN when espnId is provided; falls back to NBA CDN via nbaId.
 *
 * ESPN headshot: https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/{espnId}.png&w=96&h=70
 * NBA headshot:  https://cdn.nba.com/headshots/nba/latest/260x190/{nbaId}.png
 */
export function getPlayerAvatarUrl(
    playerId: string | undefined,
    size: 'large' | 'small' = 'small',
    espnId?: string | number,
): string {
    if (!playerId && !espnId) return PLACEHOLDER;

    // ESPN CDN — primary (no CORS issues, fast global CDN)
    if (espnId) {
        const w = size === 'large' ? 200 : 96;
        const h = size === 'large' ? 146 : 70;
        return `https://a.espncdn.com/combiner/i?img=/i/headshots/nba/players/full/${espnId}.png&w=${w}&h=${h}&scale=crop&cquality=40&location=origin`;
    }

    // NBA CDN fallback (works with NBA player IDs)
    const dimensions = size === 'large' ? '260x190' : '65x48';
    return `https://cdn.nba.com/headshots/nba/latest/${dimensions}/${playerId}.png`;
}

/**
 * Return an onError handler that falls back from ESPN → NBA CDN → placeholder.
 */
export function getAvatarFallbackHandler(nbaId?: string) {
    return (e: React.SyntheticEvent<HTMLImageElement>) => {
        const img = e.currentTarget;
        const src = img.src;
        if (src.includes('espncdn') && nbaId) {
            img.src = `https://cdn.nba.com/headshots/nba/latest/65x48/${nbaId}.png`;
        } else {
            img.src = PLACEHOLDER;
        }
    };
}

/**
 * Preload player avatar for faster display
 */
export function preloadPlayerAvatar(playerId: string, espnId?: string) {
    const img = new Image();
    img.src = getPlayerAvatarUrl(playerId, 'small', espnId);
}
