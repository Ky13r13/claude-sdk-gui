
import asyncio
import threading
import queue
import tkinter as tk

from tkinter import scrolledtext
from pathlib import Path
from sdk import run_agent


messages = queue.Queue()


def start_agent():
    cwd = str(Path(cwd_entry.get()).expanduser())
    prompt = prompt_entry.get("1.0", tk.END).strip()

    try:
        turns = int(turns_entry.get())

        if turns < 1:
            raise ValueError("Turns must be positive")
        if not Path(cwd).is_dir():
            raise ValueError("Invalid directory")
        if not prompt:
            raise ValueError("Prompt cannot be empty")

    except ValueError as error:
        messages.put(f"ERROR: {error}\n")
        return

    output.delete("1.0", tk.END)
    run_button.config(state="disabled")

    def worker():
        try:
            asyncio.run(
                run_agent(
                    cwd=cwd,
                    turns=turns,
                    prompt=prompt,
                    output=messages.put
                )
            )
        except Exception as error:
            messages.put(f"ERROR: {error}\n")
        finally:
            messages.put(None)

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


def update_output():
    while not messages.empty():
        message = messages.get_nowait()

        if message is None:
            run_button.config(state="normal")
        else:
            output.insert(tk.END, message)
            output.see(tk.END)

    root.after(100, update_output)


# ---------- WINDOW ----------

root = tk.Tk()
root.title("Claude Agent")
root.geometry("650x550")


tk.Label(root, text="Working Directory").pack()

cwd_entry = tk.Entry(root, width=75)
cwd_entry.insert(0, str(Path.home() / "Documents/testing"))
cwd_entry.pack(pady=5)


tk.Label(root, text="Max Turns").pack()

turns_entry = tk.Spinbox(root, from_=1, to=200, width=10)
turns_entry.delete(0, tk.END)
turns_entry.insert(0, "30")
turns_entry.pack(pady=5)


tk.Label(root, text="Prompt").pack()

prompt_entry = scrolledtext.ScrolledText(root, height=7)
prompt_entry.pack(fill="x", padx=10, pady=5)


run_button = tk.Button(
    root,
    text="Run Agent",
    command=start_agent
)
run_button.pack(pady=10)


tk.Label(root, text="Output").pack()

output = scrolledtext.ScrolledText(root, height=12)
output.pack(fill="both", expand=True, padx=10, pady=5)


root.after(100, update_output)
root.mainloop()
