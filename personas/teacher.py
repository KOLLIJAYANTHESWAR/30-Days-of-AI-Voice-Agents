def teacher_prompt(user_message: str) -> str:
    """
    Generates a teacher persona prompt for the LLM.

    Args:
        user_message (str): The latest user message.

    Returns:
        str: Prompt text with a knowledgeable, clear, and explanatory AI tone.
    """
    return (
        f"You are a knowledgeable teacher AI assistant. "
        f"Explain concepts clearly, patiently, and informatively.\n\n"
        f"User: {user_message}\n"
        f"Assistant:"
    )
