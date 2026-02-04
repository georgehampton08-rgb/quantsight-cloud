"""
List Available Gemini Models
============================
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except:
    pass

import google.generativeai as genai

api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    print("❌ GEMINI_API_KEY not set!")
    exit(1)

genai.configure(api_key=api_key)

print("="*70)
print("AVAILABLE GEMINI MODELS")
print("="*70)

try:
    models = genai.list_models()
    
    print("\n📋 Models that support generateContent:\n")
    
    for model in models:
        if 'generateContent' in model.supported_generation_methods:
            print(f"   ✓ {model.name}")
            print(f"      Display Name: {model.display_name}")
            print(f"      Description: {model.description[:100]}...")
            print()
    
    print("="*70)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
