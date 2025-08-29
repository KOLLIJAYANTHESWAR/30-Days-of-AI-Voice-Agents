def funny_prompt(user_message: str) -> str:
    """
    Generates a funny/sarcastic persona prompt for the LLM.

    Args:
        user_message (str): The latest user message.

    Returns:
        str: Prompt text with a humorous, witty AI assistant tone.
    """
    return (
        f"You are a funny and sarcastic AI assistant. "
        f"Respond to the user's message with humor, wit, or playful sarcasm.\n\n"
        f"User: {user_message}\n"
        f"Assistant:"
    )
