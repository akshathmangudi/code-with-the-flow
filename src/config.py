"""
This module handles the configuration for the Vibe Coder application.
It loads environment variables and initializes the Google Vertex AI client.
"""
import os
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel

# Load environment variables from a .env file.
load_dotenv()

# --- Environment Variables ---
TOKEN = os.environ.get("PUCH_AI_API_KEY", "28faaaa48cb3")
MY_NUMBER = os.environ.get("MY_NUMBER", "918106200629")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "refrakt-xai")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Ensure that the required environment variables are set.
assert TOKEN is not None, "PUCH_AI_API_KEY must be set."
assert MY_NUMBER is not None, "MY_NUMBER must be set."

# --- Global State ---
# A dictionary to store active user sessions.
SESSIONS = {}

# --- Vertex AI Initialization ---
gemini_model = None
try:
    # Initialize the Vertex AI client.
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    gemini_model = GenerativeModel("gemini-2.5-flash")
    print(f"✅ Vertex AI initialized with project: {PROJECT_ID}")
except Exception as e:
    print(f"⚠️ Vertex AI initialization failed: {e}")
