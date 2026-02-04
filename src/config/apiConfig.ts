/**
 * API Configuration
 * =================
 * Centralized configuration for API endpoints.
 * 
 * Mobile/Cloud Mode: Uses Cloud Run backend
 * Desktop Mode: Uses local backend (localhost:5000)
 */

// Cloud Run backend URL - PRODUCTION
export const CLOUD_API_BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

// Local development backend
export const LOCAL_API_BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

// Detect mobile device
const isMobile = typeof navigator !== 'undefined' && /Mobi|Android/i.test(navigator.userAgent);

// Detect production build (Vite sets this)
const isProduction = typeof window !== 'undefined' && window.location?.hostname !== 'localhost';

/**
 * Get the appropriate API base URL
 * 
 * Priority:
 * 1. Cloud URL if in production or mobile
 * 2. Local URL for development
 */
export const getApiBase = (): string => {
    // Use cloud API in production or on mobile
    if (isProduction || isMobile) {
        return CLOUD_API_BASE;
    }

    // Default to local for development
    return LOCAL_API_BASE;
};

export const API_BASE = getApiBase();

// Firebase configuration for mobile real-time updates
export const FIREBASE_CONFIG = {
    projectId: 'quantsight-prod',
};

// Export for use in other services
export default {
    API_BASE,
    CLOUD_API_BASE,
    LOCAL_API_BASE,
    isProduction,
    isMobile,
    FIREBASE_CONFIG
};
