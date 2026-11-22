
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
    model=None,
    allow_writes=False,
    auto_approve=False,
):

    async def permission_handler(tool_name, input_data, context):

        # Extra protection when read-only
        if not allow_writes and tool_name in (
            "Edit", "Write", "Bash", "NotebookEdit"
        ):
            return PermissionResultDeny(
                message="File modifications are disabled in the GUI."
            )
        if allow_writes and auto_approve:
            output(f"AUTO-APPROVED: {tool_name}\n")
            return PermissionResultAllow()
        approved = await ask_permission(tool_name, input_data)

        if approved:
            output(f"APPROVED: {tool_name}\n")
            return PermissionResultAllow()

        output(f"DENIED: {tool_name}\n")
        return PermissionResultDeny(
            message="User denied the request in the GUI."
        )

    read_tools = ["Read", "Glob", "Grep"]
    write_tools = ["Edit", "Write", "Bash"]

    options = ClaudeAgentOptions(
            cwd=cwd,
            model=model,
            tools=(
                ["Read", "Glob", "Grep", "Edit", "Write", "Bash"]
                if allow_writes
                else ["Read", "Glob", "Grep"]
            ),
            allowed_tools=["Read", "Glob", "Grep"],
            disallowed_tools=(
                [] if allow_writes
                else ["Edit", "Write", "Bash", "NotebookEdit"]
            ),
            permission_mode=(
                "bypassPermissions"
                if allow_writes and auto_approve
                else "default"
            ),
            can_use_tool=permission_handler,
            max_turns=turns,
            resume=session_id,
        )

    reported_model = None

    try:
        async for message in query(
            prompt=prompt,
            options=options,
        ):

            if isinstance(message, SystemMessage):
                if message.subtype == "init":
                    sid = message.data.get("session_id")
                    actual_model = message.data.get("model")

                    if sid and save_session:
                        save_session(sid)

                    output(f"SESSION: {sid}\n")

                    if actual_model:
                        reported_model = actual_model
                        output(f"MODEL: {actual_model}\n")

            elif isinstance(message, AssistantMessage):
                # Detect the actual model, including fallbacks
                if message.model != reported_model:
                    reported_model = message.model
                    output(f"MODEL: {message.model}\n")

                for block in message.content:
                    if isinstance(block, TextBlock):
                        output(f"CLAUDE: {block.text}\n\n")

                    elif isinstance(block, ToolUseBlock):
                        output(f"TOOL: {block.name}\n")

            elif isinstance(message, ResultMessage):
                if message.session_id and save_session:
                    save_session(message.session_id)

                output(f"\nSTATUS: {message.subtype}\n")

                if message.result is not None:
                    output(f"RESULT: {message.result}\n")

                output(f"TURNS: {message.num_turns}\n")

    except ResultError as error:
        output(f"AGENT STOPPED: {error}\n")
