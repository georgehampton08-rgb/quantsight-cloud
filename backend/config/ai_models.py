"""
QuantSight AI Model Configuration
=================================
Central configuration for all Gemini model usage across the system.
Edit this file to change models across all services at once.

AVAILABLE STABLE MODELS (as of Feb 2026):
- gemini-2.5-flash-lite  : Cheapest, GA since July 2025, good for simple tasks
- gemini-2.5-flash       : Fast, stable since June 2025
- gemini-2.0-flash       : Default since Jan 2025, stable
- gemini-1.5-flash       : Most reliable, stable since May 2024

RECOMMENDED:
- For cost optimization: gemini-2.5-flash-lite
- For reliability:       gemini-1.5-flash
- For balanced:          gemini-2.0-flash
"""
import os

# ============================================================================
# CENTRAL MODEL CONFIGURATION - EDIT THIS TO CHANGE ALL MODELS
# ============================================================================
# NOTE: New google-genai SDK requires 'models/' prefix!
DEFAULT_MODEL = os.getenv('GEMINI_MODEL', 'models/gemini-2.0-flash-lite')

# Alternative models for specific use cases
MODELS = {
    # Primary model for all AI operations (cheapest stable)
    'default': DEFAULT_MODEL,
    
    # Fast, cheap model for simple tasks (injuries, quick insights)
    'lite': os.getenv('GEMINI_MODEL_LITE', 'models/gemini-2.0-flash-lite'),
    
    # More capable model for complex analysis (Vanguard AI, deep analysis)
    'advanced': os.getenv('GEMINI_MODEL_ADVANCED', 'models/gemini-2.0-flash'),
}

def get_model(use_case: str = 'default') -> str:
    """
    Get the appropriate model for the use case.
    
    Args:
        use_case: 'default', 'lite', or 'advanced'
    
    Returns:
        Model name string
    """
    return MODELS.get(use_case, DEFAULT_MODEL)


# ============================================================================
# LEGACY COMPATIBILITY - Deprecated model mappings
# ============================================================================
DEPRECATED_MODELS = {
    'gemini-2.0-flash-exp': 'gemini-1.5-flash',      # Experimental, 404s
    'gemini-pro': 'gemini-1.5-flash',                 # Old, slower
    'gemini-2.0-flash': 'gemini-1.5-flash',           # May have issues
    'gemini-2.5-flash-lite': 'gemini-1.5-flash',      # Use if stable
}
