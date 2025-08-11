"""
This module contains functions for interacting with the generative language model.
"""
import re
from src.config import gemini_model

async def generate_single_page_app(user_prompt: str) -> str:
    """
    Generates a single-file, self-contained web application from a user's prompt.

    Args:
        user_prompt: The user's description of the web application to create.

    Returns:
        The HTML content of the web application as a string.
    """
    if not gemini_model:
        return "<h1>Error: Gemini model not initialized</h1>"
    try:
        system_prompt = """You are an expert web developer. Your task is to create a complete, single-file, self-contained web application based on a user's prompt.

IMPORTANT CONSTRAINTS:
- You MUST return a single HTML file.
- All CSS and JavaScript MUST be included inline within the HTML file using `<style>` and `<script>` tags.
- Do NOT use any external frameworks or libraries unless you can include them from a CDN.
- The application must be fully functional as a single `.html` file.
- The code should be clean, well-formatted, and modern.
- Focus on functionality over complex design, but make it look presentable.
- Do NOT include any explanations, comments, or markdown formatting around the code. ONLY return the raw HTML code."""
        prompt = f"{system_prompt}\n\nNow, create a single-file web application for the following prompt: '{user_prompt}'"
        print(f"🔨 Generating single-page app for: {user_prompt}...")
        response = await gemini_model.generate_content_async(prompt)
        html_content = response.text or ""
        if "```html" in html_content:
            m = re.search(r"```html\n(.*?)\n```", html_content, re.DOTALL)
            if m:
                html_content = m.group(1)
        print("✅ HTML content generated.")
        return html_content.strip()
    except Exception as e:
        print(f"❌ Single-page app generation error: {e}")
        return f"<h1>Error generating app</h1><p>{e}</p>"

async def modify_single_page_app(current_html: str, user_feedback: str) -> str:
    """
    Modifies an existing single-file HTML application based on user feedback.

    Args:
        current_html: The current HTML content of the application.
        user_feedback: The user's instructions for what to change.

    Returns:
        The complete, modified HTML code.
    """
    if not gemini_model:
        return "<h1>Error: Gemini model not initialized</h1>"
    try:
        system_prompt = """You are an expert web developer. Your task is to modify an existing single-file HTML application based on user feedback.

IMPORTANT CONSTRAINTS:
- You will be given the current HTML code and a user's request for a change.
- You MUST return the complete, modified HTML code.
- All CSS and JavaScript MUST remain included inline within the HTML file.
- The application must remain fully functional as a single `.html` file.
- Do NOT include any explanations, comments, or markdown formatting around the code. ONLY return the raw HTML code."""
        prompt = f"{system_prompt}\n\nHere is the current HTML code:\n```html\n{current_html}\n```\n\nHere is the user's feedback on what to change:\n'{user_feedback}'\n\nNow, please provide the complete, updated HTML code with the requested changes."
        print(f"🔨 Applying modifications for: {user_feedback}...")
        response = await gemini_model.generate_content_async(prompt)
        html_content = response.text or ""
        if "```html" in html_content:
            m = re.search(r"```html\n(.*?)\n```", html_content, re.DOTALL)
            if m:
                html_content = m.group(1)
        print("✅ HTML content modified.")
        return html_content.strip()
    except Exception as e:
        print(f"❌ App modification error: {e}")
        return f"<h1>Error modifying app</h1><p>{e}</p>"
