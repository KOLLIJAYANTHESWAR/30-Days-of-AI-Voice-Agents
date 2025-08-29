def friend_prompt(user_message: str) -> str:
    """
    Generates a friendly persona prompt for the LLM.

    Args:
        user_message (str): The latest user message.

    Returns:
        str: Prompt text with a friendly AI assistant tone.
    """
    return (
        f"You are a friendly and supportive AI assistant. "
        f"Respond warmly and kindly to the user's message.\n\n"
        f"User: {user_message}\n"
        f"Assistant:"
    )
