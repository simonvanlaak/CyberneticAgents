#!/usr/bin/env python3
"""
Test script to verify the chat interface and contact_user_tool integration.
"""

import asyncio
import time
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the contact_user_tool directly from the chat app
from chat_app import contact_user_tool


async def test_with_real_ui():
    """Test the contact_user_tool with the actual NiceGUI chat interface."""

    print("Testing contact_user_tool with real UI...")

    # Test sending messages to the UI
    messages = [
        (
            "System4",
            "Hello! I'm System 4. I've analyzed your request and I'm working on it.",
        ),
        (
            "System3",
            "System 3 here. I'm coordinating the task execution across all systems.",
        ),
        ("System1", "System 1 reporting. I'm executing the operational tasks."),
        ("System4", "Analysis complete! I've gathered all the necessary information."),
        (
            "System5",
            "System 5 here. The overall policy and strategy are aligned with your request.",
        ),
    ]

    for sender, message in messages:
        print(f"Sending: {sender} -> User: {message}")
        result = await contact_user_tool(message, sender)
        print(f"Result: {result}")
        await asyncio.sleep(1)  # Small delay between messages

    print("Test completed! Check your browser at http://localhost:8080")


if __name__ == "__main__":
    print("Make sure the chat app is running: python3 chat_app_fixed.py")
    print("Then open http://localhost:8080 in your browser")
    print("Starting test in 3 seconds...")
    time.sleep(3)

    asyncio.run(test_with_real_ui())
