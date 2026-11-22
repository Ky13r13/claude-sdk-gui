
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultError,
)


async def run_agent(
    cwd,
    turns,
    prompt,
    output,
    ask_permission,
    session_id=None,
    save_session=None,
):

    async def permission_handler(tool_name, input_data, context):
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
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="default",
        can_use_tool=permission_handler,
        max_turns=turns,

        # Continue the saved conversation
        resume=session_id,
    )

    try:
        async for message in query(
            prompt=prompt,
            options=options,
        ):

            # Capture the session ID when Claude starts
            if isinstance(message, SystemMessage):
                if message.subtype == "init":
                    sid = message.data.get("session_id")
                    if sid and save_session:
                        save_session(sid)
                    output(f"SESSION: {sid}\n")

            elif isinstance(message, AssistantMessage):
                for block in message.content:

                    if isinstance(block, TextBlock):
                        output(f"CLAUDE: {block.text}\n\n")

                    elif isinstance(block, ToolUseBlock):
                        output(f"TOOL: {block.name}\n")

            elif isinstance(message, ResultMessage):
                # Save the session for the next GUI prompt
                if message.session_id and save_session:
                    save_session(message.session_id)

                output(f"\nSTATUS: {message.subtype}\n")

                if message.result is not None:
                    output(f"RESULT: {message.result}\n")

                output(f"TURNS: {message.num_turns}\n")

    except ResultError as error:
        output(f"AGENT STOPPED: {error}\n")
