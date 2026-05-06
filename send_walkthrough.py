import os
from dotenv import load_dotenv
from email_utils import send_email_report

# Load credentials from .env
load_dotenv()

# Load the walkthrough content
walkthrough_path = r"C:\Users\kevin\.gemini\antigravity\brain\e74ccdb6-848e-42de-9679-b4121d5415ab\code_walkthrough.md"

with open(walkthrough_path, "r", encoding="utf-8") as f:
    content = f.read()

# Convert markdown-ish to simple HTML for the email
html_content = content.replace("\n", "<br>").replace("## ", "<h2>").replace("### ", "<h3>").replace("```python", "<pre>").replace("```", "</pre>")

# Send it
print("Sending walkthrough email...")
send_email_report("Code Walkthrough", html_content, "")
print("Done!")
