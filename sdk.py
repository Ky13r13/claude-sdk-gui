
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ResultError,
)


async def run_agent(cwd, turns, prompt, output):
    options = ClaudeAgentOptions(
        cwd=cwd,
        tools=["Read", "Glob", "Grep",
               "Edit", "Write", "Bash"],
        allowed_tools=["Read", "Glob", "Grep",
                       "Edit", "Write"],
        max_turns=turns,
        permission_mode="acceptEdits",
    )

    try:
        async for message in query(
            prompt=prompt,
            options=options
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        output(f"CLAUDE: {block.text}\n\n")

                    elif isinstance(block, ToolUseBlock):
                        output(f"TOOL: {block.name}\n")

            elif isinstance(message, ResultMessage):
                output(f"\nSTATUS: {message.subtype}\n")
                output(f"RESULT: {message.result}\n")
                output(f"TURNS: {message.num_turns}\n")

    except ResultError as error:
        output(f"AGENT STOPPED: {error}\n")
