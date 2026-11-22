
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultError,
)


async def run_agent(cwd, turns, prompt, output, ask_permission):

    async def permission_handler(tool_name, input_data, context):
        # Wait for the user's decision in Tkinter
        approved = await ask_permission(tool_name, input_data)

        if approved:
            output(f"APPROVED: {tool_name}\n")
            return PermissionResultAllow()

        output(f"DENIED: {tool_name}\n")
        return PermissionResultDeny(
            message="User denied the request in the GUI."
        )

    options = ClaudeAgentOptions(
        cwd=cwd,
        tools=[
            "Read", "Glob", "Grep",
            "Edit", "Write", "Bash"
        ],
        # Read-only operations are automatically approved
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="default",
        can_use_tool=permission_handler,
        max_turns=turns,
    )

    try:
        async for message in query(prompt=prompt, options=options):

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
