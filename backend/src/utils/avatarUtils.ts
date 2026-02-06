/**
 * Utility function to get player avatar URL
 * Uses NBA CDN directly for reliable photo loading
 */

/**
 * Get player avatar URL from NBA CDN
 * @param playerId - NBA player ID
 * @param size - 'large' (260x190) or 'small' (65x48)
 * @returns NBA CDN avatar URL
 */
export function getPlayerAvatarUrl(playerId: string | undefined, size: 'large' | 'small' = 'small'): string {
    if (!playerId) {
        // Return a placeholder/fallback for unknown players
        return 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"%3E%3Ccircle cx="50" cy="50" r="50" fill="%23374151"/%3E%3Ctext x="50" y="55" font-size="40" text-anchor="middle" fill="%239CA3AF"%3E?%3C/text%3E%3C/svg%3E';
    }
    // Use NBA CDN directly - same pattern that works in MatchupLabPage
    const dimensions = size === 'large' ? '260x190' : '65x48';
    return `https://cdn.nba.com/headshots/nba/latest/${dimensions}/${playerId}.png`;
}

/**
 * Preload player avatar for faster display
 * @param playerId - NBA player ID
 */
export function preloadPlayerAvatar(playerId: string) {
    const img = new Image();
    img.src = getPlayerAvatarUrl(playerId, 'small');
}
