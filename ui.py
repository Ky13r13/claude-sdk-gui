
import asyncio
import json
import queue
import threading
import tkinter as tk

from collections import deque
from concurrent.futures import Future
from pathlib import Path
from tkinter import scrolledtext, messagebox

from sdk import run_agent


events = queue.Queue()
pending_approvals = deque()
active_approval = None


# ---------- AGENT EXECUTION ----------

def start_agent():
    cwd = Path(cwd_entry.get()).expanduser()
    prompt = prompt_entry.get("1.0", tk.END).strip()

    try:
        turns = int(turns_entry.get())

        if turns < 1:
            raise ValueError("Turns must be positive")
        if not cwd.is_dir():
            raise ValueError("Invalid working directory")
        if not prompt:
            raise ValueError("Prompt cannot be empty")

    except ValueError as error:
        messagebox.showerror("Invalid input", str(error))
        return

    output.delete("1.0", tk.END)
    run_button.config(state="disabled")

    # Called from the SDK's asyncio worker
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
                    output=lambda text: events.put(
                        ("output", text)
                    ),
                    ask_permission=ask_permission,
                )
            )
        except Exception as error:
            events.put(("output", f"ERROR: {error}\n"))
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
        text="Review the complete tool input before approving."
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


# ---------- EVENT HANDLING ----------

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

    root.after(100, update_gui)


def on_close():
    if run_button["state"] == "disabled":
        messagebox.showwarning(
            "Agent running",
            "Finish the agent run before closing the GUI."
        )
        return

    root.destroy()


# ---------- TKINTER WINDOW ----------

root = tk.Tk()
root.title("Claude Agent")
root.geometry("700x600")

tk.Label(root, text="Working Directory").pack(pady=4)

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

tk.Label(root, text="Agent Prompt").pack()

prompt_entry = scrolledtext.ScrolledText(
    root, height=7
)
prompt_entry.pack(
    fill="x", padx=12, pady=6
)

run_button = tk.Button(
    root,
    text="Run Agent",
    command=start_agent
)
run_button.pack(pady=10)

tk.Label(root, text="Agent Output").pack()

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
