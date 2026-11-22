
import asyncio
import json
import queue
import threading
import tkinter as tk

from collections import deque
from concurrent.futures import Future
from pathlib import Path
from tkinter import scrolledtext, messagebox, ttk

from sdk import run_agent


events = queue.Queue()
pending_approvals = deque()
active_approval = None

SESSION_FILE = (
    Path.home() / ".config" /
    "claude-sdk-gui" / "sessions.json"
)


# ---------- SESSION STORAGE ----------

def load_sessions():
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return {}


def write_sessions(sessions):
    SESSION_FILE.parent.mkdir(
        parents=True, exist_ok=True
    )

    # Atomic replacement avoids incomplete JSON writes
    temporary = SESSION_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(sessions, indent=2))
    temporary.replace(SESSION_FILE)


def save_session(cwd, session_id):
    sessions = load_sessions()
    sessions[cwd] = session_id
    write_sessions(sessions)


def new_session():
    if run_button["state"] == "disabled":
        messagebox.showwarning(
            "Agent running",
            "Finish the current run first."
        )
        return

    cwd = str(
        Path(cwd_entry.get()).expanduser().resolve()
    )

    sessions = load_sessions()
    sessions.pop(cwd, None)
    write_sessions(sessions)

    output.delete("1.0", tk.END)
    output.insert(
        tk.END,
        "New session started. Previous history "
        "is no longer selected.\n"
    )


# ---------- AGENT EXECUTION ----------

def start_agent():
    cwd = Path(cwd_entry.get()).expanduser().resolve()
    prompt = prompt_entry.get("1.0", tk.END).strip()
    selected_model = model_var.get()

    model = (
        None if selected_model == "Default"
        else selected_model.lower()
            )

    allow_writes = allow_writes_var.get()
    try:
        turns = int(turns_entry.get())

        if turns < 1:
            raise ValueError("Turns must be positive")

        if not cwd.is_dir():
            raise ValueError("Invalid working directory")

        if not prompt:
            raise ValueError("Prompt cannot be empty")

        session_id = load_sessions().get(str(cwd))

    except (ValueError, OSError) as error:
        messagebox.showerror("Invalid input", str(error))
        return

    # Keep the existing visible conversation
    output.insert(tk.END, f"\nYOU: {prompt}\n\n")
    output.see(tk.END)

    if session_id:
        output.insert(tk.END, "Resuming saved session...\n")
    else:
        output.insert(tk.END, "Starting new session...\n")

    prompt_entry.delete("1.0", tk.END)
    run_button.config(state="disabled")
    new_button.config(state="disabled")

    # Permission requests from the SDK worker
    async def ask_permission(tool_name, tool_input):
        decision = Future()

        events.put((
            "permission",
            (tool_name, tool_input, decision)
        ))

        return await asyncio.wrap_future(decision)

    def worker():
        try:
            asyncio.run(
                run_agent(
                    cwd=str(cwd),
                    turns=turns,
                    prompt=prompt,
                    model=model,
                    allow_writes=allow_writes,
                    output=lambda text: events.put(
                        ("output", text)
                    ),
                    ask_permission=ask_permission,
                    session_id=session_id,
                    save_session=lambda sid: save_session(
                        str(cwd), sid
                    ),
                )
            )

        except Exception as error:
            events.put((
                "output",
                f"ERROR: {error}\n"
            ))

        finally:
            events.put(("done", None))

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


# ---------- PERMISSION DIALOG ----------

def show_next_approval():
    global active_approval

    if active_approval is not None:
        return

    if not pending_approvals:
        return

    tool, tool_input, decision = pending_approvals.popleft()
    active_approval = decision

    dialog = tk.Toplevel(root)
    dialog.title("Claude Permission Request")
    dialog.geometry("650x420")
    dialog.transient(root)
    dialog.grab_set()

    tk.Label(
        dialog,
        text=f"Claude requests: {tool}",
        font=("Arial", 13, "bold")
    ).pack(pady=12)

    tk.Label(
        dialog,
        text="Review the tool input before approving."
    ).pack()

    details = scrolledtext.ScrolledText(
        dialog,
        wrap="word",
        height=15
    )
    details.pack(
        fill="both",
        expand=True,
        padx=12,
        pady=10
    )

    details.insert(
        "1.0",
        json.dumps(tool_input, indent=2, default=str)
    )
    details.config(state="disabled")

    buttons = tk.Frame(dialog)
    buttons.pack(pady=12)

    def respond(approved):
        global active_approval

        if not decision.done():
            decision.set_result(approved)

        active_approval = None
        dialog.grab_release()
        dialog.destroy()
        show_next_approval()

    tk.Button(
        buttons,
        text="Allow once",
        width=16,
        command=lambda: respond(True)
    ).pack(side="left", padx=8)

    tk.Button(
        buttons,
        text="Deny",
        width=16,
        command=lambda: respond(False)
    ).pack(side="left", padx=8)

    dialog.protocol(
        "WM_DELETE_WINDOW",
        lambda: respond(False)
    )


# ---------- GUI EVENT LOOP ----------

def update_gui():
    while True:
        try:
            event, data = events.get_nowait()
        except queue.Empty:
            break

        if event == "output":
            output.insert(tk.END, data)
            output.see(tk.END)

        elif event == "permission":
            pending_approvals.append(data)
            show_next_approval()

        elif event == "done":
            run_button.config(state="normal")
            new_button.config(state="normal")

    root.after(100, update_gui)


def on_close():
    if run_button["state"] == "disabled":
        messagebox.showwarning(
            "Agent running",
            "Finish the agent run before closing."
        )
        return

    root.destroy()


# ---------- TKINTER WINDOW ----------

root = tk.Tk()
root.title("Claude Agent")
root.geometry("700x600")

tk.Label(
    root, text="Working Directory"
).pack(pady=4)

cwd_entry = tk.Entry(root, width=75)
cwd_entry.insert(
    0, str(Path.home() / "Documents/testing")
)
cwd_entry.pack(pady=4)

tk.Label(root, text="Max Turns").pack()

turns_entry = tk.Spinbox(
    root, from_=1, to=200, width=10
)
turns_entry.delete(0, tk.END)
turns_entry.insert(0, "30")
turns_entry.pack(pady=4)
tk.Label(root, text="Claude Model").pack(pady=(10, 2))

model_var = tk.StringVar(value="Default")

model_selector = ttk.Combobox(
    root,
    textvariable=model_var,
    values=["Default", "Opus", "Sonnet", "Haiku"],
    state="readonly",
    width=20,
)
model_selector.pack(pady=4)


# ---------- WRITE PERMISSIONS ----------

allow_writes_var = tk.BooleanVar(value=False)

write_check = ttk.Checkbutton(
    root,
    text="Enable edits and Bash (GUI approval required)",
    variable=allow_writes_var,
)
write_check.pack(pady=8)

tk.Label(root, text="Agent Prompt").pack()

prompt_entry = scrolledtext.ScrolledText(
    root, height=7
)
prompt_entry.pack(
    fill="x", padx=12, pady=6
)

buttons = tk.Frame(root)
buttons.pack(pady=10)

run_button = tk.Button(
    buttons,
    text="Run Agent",
    command=start_agent,
    width=16
)
run_button.pack(side="left", padx=5)

new_button = tk.Button(
    buttons,
    text="New Session",
    command=new_session,
    width=16
)
new_button.pack(side="left", padx=5)

tk.Label(root, text="Conversation").pack()

output = scrolledtext.ScrolledText(
    root, height=14
)
output.pack(
    fill="both",
    expand=True,
    padx=12,
    pady=8
)

root.protocol("WM_DELETE_WINDOW", on_close)
root.after(100, update_gui)
root.mainloop()
