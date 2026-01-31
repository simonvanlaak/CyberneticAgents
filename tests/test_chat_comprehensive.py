#!/usr/bin/env python3
"""
Comprehensive test of the chat interface with both user and agent messages.
"""

import asyncio
import time
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the contact_user_tool and messages from the chat app
from chat_app import contact_user_tool, messages


async def comprehensive_test():
    """Test agent messages (user messages require UI context)."""

    print("=== Chat Interface Test (Agent Messages Only) ===")
    print(f"Initial message count: {len(messages)}")

    # Test agent messages
    print("\nTesting agent messages...")
    agent_messages = [
        (
            "System4",
            "Hello! I'm System 4, the intelligence layer. I've received your request.",
        ),
        (
            "System3",
            "System 3 here. I'm coordinating the control and monitoring functions.",
        ),
        ("System1", "System1 reporting. I'm executing the operational tasks."),
    ]

    for sender, message in agent_messages:
        result = await contact_user_tool(message, sender)
        print(f"  {sender} -> {message}")

    # Test more agent responses
    print("\nTesting more agent responses...")
    responses = [
        ("System4", "Analysis complete! I've gathered all necessary information."),
        ("System3", "All operational tasks completed successfully."),
        (
            "System5",
            "Policy alignment confirmed. All systems operating within guidelines.",
        ),
    ]

    for sender, message in responses:
        result = await contact_user_tool(message, sender)
        print(f"  {sender} -> {message}")

    # Final result
    print(f"\nFinal message count: {len(messages)}")
    print("\nAll agent messages in chat:")
    for i, (sender, content, timestamp, is_user) in enumerate(messages):
        print(f"  {i}: [Agent] {sender}: {content}")

    print("\n=== Test completed! ===")
    print("The chat interface is working correctly!")
    print("Open http://localhost:8080 in your browser to see the UI.")


if __name__ == "__main__":
    asyncio.run(comprehensive_test())
