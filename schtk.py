import os
import sqlite3
import subprocess
import shutil
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from concurrent.futures import ThreadPoolExecutor

# ----------------------------
# Configuration & Globals
# ----------------------------
SCRIPT_DIRECTORY = "D:\\WorldEconomicEngineProj\\IndiaStockExchange\\"  # Adjust as needed
DB_FILE = "scheduled_jobs.db"  # For job details
AP_SCHEDULER_DB = "apscheduler_jobs.db"  # For persisting APScheduler jobs
LOG_FILE = "script_logs.txt"

# Create a ThreadPoolExecutor to run scripts asynchronously
executor = ThreadPoolExecutor(max_workers=4)

# Initialize APScheduler with a persistent job store.
jobstores = {
    'default': SQLAlchemyJobStore(url=f"sqlite:///{AP_SCHEDULER_DB}")
}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()


# ----------------------------
# Database Initialization
# ----------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_path TEXT NOT NULL,
            hour INTEGER,
            minute INTEGER,
            second INTEGER,
            frequency TEXT,
            active INTEGER,
            scheduler_id TEXT
        )
    ''')
    conn.commit()
    conn.close()


init_db()


# ----------------------------
# Logging Functionality
# ----------------------------
def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {message}\n")


# ----------------------------
# Script Execution (Thread Pool)
# ----------------------------
def run_script(script_path):
    def execute():
        try:
            log_message(f"⚡ Running: {script_path}")
            result = subprocess.run(["python", script_path], capture_output=True, text=True)
            output = result.stdout + "\n" + result.stderr
            log_message(f"✅ Finished: {script_path}\n{output}")
        except Exception as e:
            log_message(f"❌ Error: {script_path}: {str(e)}")

    executor.submit(execute)


# ----------------------------
# Database Job Management Functions
# ----------------------------
def add_job_to_db(script_path, hour, minute, second, frequency, active=1):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO jobs (script_path, hour, minute, second, frequency, active) VALUES (?, ?, ?, ?, ?, ?)",
              (script_path, hour, minute, second, frequency, active))
    job_db_id = c.lastrowid
    conn.commit()
    conn.close()
    return job_db_id


def update_job_scheduler_id(job_db_id, scheduler_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE jobs SET scheduler_id=? WHERE id=?", (scheduler_id, job_db_id))
    conn.commit()
    conn.close()


def update_job_in_db(job_db_id, script_path, hour, minute, second, frequency, active):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE jobs SET script_path=?, hour=?, minute=?, second=?, frequency=?, active=? WHERE id=?",
              (script_path, hour, minute, second, frequency, active, job_db_id))
    conn.commit()
    conn.close()


def remove_job_from_db(job_db_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM jobs WHERE id=?", (job_db_id,))
    conn.commit()
    conn.close()


def get_jobs_from_db():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM jobs", conn)
    conn.close()
    return df


def get_job_by_id(job_db_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id=?", (job_db_id,))
    job = c.fetchone()
    conn.close()
    return job


# ----------------------------
# Scheduler Job Management Functions
# ----------------------------
def schedule_job(job_db_id, script_path, hour, minute, second, frequency):
    # Create a scheduler job ID that includes the DB job ID.
    scheduler_id = f"{job_db_id}_{os.path.basename(script_path)}_{hour}_{minute}_{second}"
    run_date = datetime.now().replace(hour=hour, minute=minute, second=second)
    if run_date < datetime.now():
        run_date += timedelta(days=1)
    if frequency == "daily":
        scheduler.add_job(run_script, 'cron', hour=hour, minute=minute, second=second,
                          id=scheduler_id, args=[script_path])
    elif frequency == "weekly":
        scheduler.add_job(run_script, 'interval', weeks=1, id=scheduler_id, args=[script_path])
    elif frequency == "monthly":
        scheduler.add_job(run_script, 'interval', weeks=4, id=scheduler_id, args=[script_path])
    elif frequency.startswith("custom_"):
        days = int(frequency.split("_")[1].replace("d", ""))
        scheduler.add_job(run_script, 'interval', days=days, id=scheduler_id, args=[script_path])
    else:  # once
        scheduler.add_job(run_script, 'date', run_date=run_date, id=scheduler_id, args=[script_path])
    update_job_scheduler_id(job_db_id, scheduler_id)
    return scheduler_id


def remove_scheduler_job(scheduler_id):
    try:
        scheduler.remove_job(scheduler_id)
        log_message(f"🗑 Removed scheduler job: {scheduler_id}")
    except Exception as e:
        log_message(f"Error removing scheduler job {scheduler_id}: {str(e)}")


def reschedule_job(job_db_id, script_path, hour, minute, second, frequency):
    job = get_job_by_id(job_db_id)
    if job and job[7]:  # scheduler_id is at index 7
        remove_scheduler_job(job[7])
    schedule_job(job_db_id, script_path, hour, minute, second, frequency)


# ----------------------------
# Main Tkinter Application
# ----------------------------
class SchedulerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fincept Task Scheduler")
        self.geometry("1100x800")
        self.status_var = tk.StringVar()
        self.filter_var = tk.StringVar()
        self.log_filter_var = tk.StringVar()
        self.create_widgets()
        self.update_script_list()
        self.periodic_refresh()  # start periodic updates

    def create_widgets(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=1, fill="both")
        self.create_schedule_tab()
        self.create_jobs_tab()
        self.create_manual_run_tab()
        self.create_logs_tab()
        # Status Bar for notifications
        self.status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

    def set_status(self, message, duration=3000):
        self.status_var.set(message)
        self.after(duration, lambda: self.status_var.set(""))

    # ---------------- Schedule Tab ----------------
    def create_schedule_tab(self):
        self.schedule_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.schedule_frame, text="Schedule")
        # Upload section
        upload_label = ttk.Label(self.schedule_frame, text="Upload New Script:")
        upload_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        upload_button = ttk.Button(self.schedule_frame, text="Browse & Upload", command=self.upload_script)
        upload_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        # Script selection
        script_label = ttk.Label(self.schedule_frame, text="Select Script:")
        script_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.script_var = tk.StringVar()
        self.script_combo = ttk.Combobox(self.schedule_frame, textvariable=self.script_var, state="readonly")
        self.script_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        # Time inputs
        ttk.Label(self.schedule_frame, text="Hour (0-23):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.hour_spin = tk.Spinbox(self.schedule_frame, from_=0, to=23, width=5)
        self.hour_spin.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.schedule_frame, text="Minute (0-59):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.minute_spin = tk.Spinbox(self.schedule_frame, from_=0, to=59, width=5)
        self.minute_spin.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(self.schedule_frame, text="Second (0-59):").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.second_spin = tk.Spinbox(self.schedule_frame, from_=0, to=59, width=5)
        self.second_spin.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        # Frequency selection
        ttk.Label(self.schedule_frame, text="Frequency:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.freq_var = tk.StringVar()
        self.freq_combo = ttk.Combobox(self.schedule_frame, textvariable=self.freq_var, state="readonly",
                                       values=["once", "daily", "weekly", "monthly", "custom"])
        self.freq_combo.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.freq_combo.bind("<<ComboboxSelected>>", self.freq_selected)
        # Custom interval (shown only when "custom" is selected)
        self.custom_label = ttk.Label(self.schedule_frame, text="Custom Interval (Days):")
        self.custom_spin = tk.Spinbox(self.schedule_frame, from_=1, to=30, width=5)
        # Schedule button
        schedule_button = ttk.Button(self.schedule_frame, text="Schedule Script", command=self.schedule_script)
        schedule_button.grid(row=7, column=0, columnspan=2, padx=5, pady=10)

    def freq_selected(self, event):
        if self.freq_var.get() == "custom":
            self.custom_label.grid(row=6, column=0, padx=5, pady=5, sticky="w")
            self.custom_spin.grid(row=6, column=1, padx=5, pady=5, sticky="w")
        else:
            self.custom_label.grid_forget()
            self.custom_spin.grid_forget()

    def upload_script(self):
        file_path = filedialog.askopenfilename(title="Select Python Script", filetypes=[("Python Files", "*.py")])
        if file_path:
            try:
                filename = os.path.basename(file_path)
                dest_path = os.path.join(SCRIPT_DIRECTORY, filename)
                shutil.copy(file_path, dest_path)
                self.set_status(f"Script uploaded: {filename}")
                self.update_script_list()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload script: {str(e)}")

    def update_script_list(self):
        try:
            scripts = [f for f in os.listdir(SCRIPT_DIRECTORY) if f.endswith(".py")]
        except Exception:
            scripts = []
        self.script_combo['values'] = scripts
        if scripts:
            self.script_combo.current(0)

    def schedule_script(self):
        script_name = self.script_var.get()
        if not script_name:
            messagebox.showwarning("Warning", "Please select a script.")
            return
        script_path = os.path.join(SCRIPT_DIRECTORY, script_name)
        try:
            hour = int(self.hour_spin.get())
            minute = int(self.minute_spin.get())
            second = int(self.second_spin.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid time values.")
            return
        frequency = self.freq_var.get()
        if frequency == "custom":
            try:
                custom_days = int(self.custom_spin.get())
                frequency = f"custom_{custom_days}d"
            except ValueError:
                messagebox.showerror("Error", "Invalid custom interval.")
                return
        # Insert job into DB and schedule it
        job_db_id = add_job_to_db(script_path, hour, minute, second, frequency)
        schedule_job(job_db_id, script_path, hour, minute, second, frequency)
        self.set_status("Script Scheduled!")
        self.update_jobs()

    # ---------------- Jobs Tab ----------------
    def create_jobs_tab(self):
        self.jobs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.jobs_frame, text="Jobs")
        # Filter entry for job list
        ttk.Label(self.jobs_frame, text="Filter Jobs (by Script Name):") \
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.job_filter_entry = ttk.Entry(self.jobs_frame, textvariable=self.filter_var)
        self.job_filter_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.job_filter_entry.bind("<KeyRelease>", lambda e: self.update_jobs())
        # Treeview for displaying jobs
        self.jobs_tree = ttk.Treeview(self.jobs_frame,
                                      columns=("ID", "Script", "Hour", "Minute", "Second", "Frequency", "Active"),
                                      show="headings")
        for col in ("ID", "Script", "Hour", "Minute", "Second", "Frequency", "Active"):
            self.jobs_tree.heading(col, text=col, command=lambda _col=col: self.sort_jobs(_col))
        self.jobs_tree.grid(row=1, column=0, columnspan=6, padx=5, pady=5, sticky="nsew")
        self.jobs_frame.grid_rowconfigure(1, weight=1)
        self.jobs_frame.grid_columnconfigure(0, weight=1)
        # Buttons for Remove, Edit, and Toggle
        ttk.Button(self.jobs_frame, text="Remove Job", command=self.remove_job_ui) \
            .grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttk.Button(self.jobs_frame, text="Edit Job", command=self.edit_job_ui) \
            .grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(self.jobs_frame, text="Toggle Job", command=self.toggle_job_ui) \
            .grid(row=2, column=2, padx=5, pady=5, sticky="w")

    def sort_jobs(self, col):
        df = get_jobs_from_db()
        ascending = True
        try:
            df_sorted = df.sort_values(by=col, ascending=ascending)
        except Exception:
            df_sorted = df.sort_values(by=col, key=lambda x: x.astype(str), ascending=ascending)
        self.populate_jobs_tree(df_sorted)

    def populate_jobs_tree(self, df):
        for item in self.jobs_tree.get_children():
            self.jobs_tree.delete(item)
        filter_text = self.filter_var.get().lower()
        for index, row in df.iterrows():
            script_name = os.path.basename(row["script_path"]) if row["script_path"] else "Unknown"
            if filter_text and filter_text not in script_name.lower():
                continue
            display_status = "Active" if row["active"] == 1 else "Paused"
            self.jobs_tree.insert("", "end",
                                  values=(row["id"], script_name,
                                          row["hour"], row["minute"], row["second"],
                                          row["frequency"], display_status))

    def update_jobs(self):
        df = get_jobs_from_db()
        self.populate_jobs_tree(df)

    def remove_job_ui(self):
        selected = self.jobs_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "No job selected.")
            return
        item = self.jobs_tree.item(selected[0])
        job_id = item["values"][0]
        job = get_job_by_id(job_id)
        if job and job[7]:
            remove_scheduler_job(job[7])
        remove_job_from_db(job_id)
        self.set_status(f"Removed job {job_id}")
        self.update_jobs()

    def toggle_job_ui(self):
        selected = self.jobs_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "No job selected.")
            return
        item = self.jobs_tree.item(selected[0])
        job_id = item["values"][0]
        job = get_job_by_id(job_id)
        if not job:
            return
        # Toggle the "active" status (active==1, paused==0)
        new_status = 0 if job[5] == "Active" or job[6] == 1 else 1
        update_job_in_db(job_id, job[1], job[2], job[3], job[4], job[5], new_status)
        if new_status == 0:
            if job[7]:
                remove_scheduler_job(job[7])
        else:
            reschedule_job(job_id, job[1], job[2], job[3], job[4])
        self.set_status(f"Toggled job {job_id}")
        self.update_jobs()

    def edit_job_ui(self):
        selected = self.jobs_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "No job selected for editing.")
            return
        item = self.jobs_tree.item(selected[0])
        job_id = item["values"][0]
        job = get_job_by_id(job_id)
        if not job:
            return
        EditJobWindow(self, job)

    # ---------------- Manual Run Tab ----------------
    def create_manual_run_tab(self):
        self.manual_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.manual_frame, text="Manual Run")
        ttk.Label(self.manual_frame, text="Select Script to Run:") \
            .grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.manual_script_var = tk.StringVar()
        self.manual_script_combo = ttk.Combobox(self.manual_frame, textvariable=self.manual_script_var,
                                                state="readonly")
        self.manual_script_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(self.manual_frame, text="Run Now", command=self.run_script_manually) \
            .grid(row=1, column=0, columnspan=2, padx=5, pady=10)
        self.update_manual_script_list()

    def update_manual_script_list(self):
        try:
            scripts = [f for f in os.listdir(SCRIPT_DIRECTORY) if f.endswith(".py")]
        except Exception:
            scripts = []
        self.manual_script_combo['values'] = scripts
        if scripts:
            self.manual_script_combo.current(0)

    def run_script_manually(self):
        script_name = self.manual_script_var.get()
        if script_name:
            script_path = os.path.join(SCRIPT_DIRECTORY, script_name)
            run_script(script_path)
            self.set_status(f"Executed {script_name}")
        else:
            messagebox.showwarning("Warning", "No script selected.")

    # ---------------- Logs Tab ----------------
    def create_logs_tab(self):
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="Logs")
        ttk.Label(self.logs_frame, text="Filter Logs (by keyword):") \
            .pack(anchor="w", padx=5, pady=5)
        self.log_filter_entry = ttk.Entry(self.logs_frame, textvariable=self.log_filter_var)
        self.log_filter_entry.pack(anchor="w", padx=5, pady=5)
        self.log_filter_entry.bind("<KeyRelease>", lambda e: self.refresh_logs())
        self.logs_text = tk.Text(self.logs_frame, wrap="none", height=30)
        self.logs_text.pack(expand=1, fill="both", padx=5, pady=5)
        self.log_progress = ttk.Progressbar(self.logs_frame, mode="indeterminate")
        self.log_progress.pack(fill="x", padx=5, pady=5)
        self.refresh_logs()

    def refresh_logs(self):
        self.log_progress.start()
        self.logs_text.delete("1.0", tk.END)
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = f.readlines()
            filter_keyword = self.log_filter_var.get().lower()
            filtered_logs = [line for line in logs if filter_keyword in line.lower()]
            self.logs_text.insert(tk.END, "".join(filtered_logs))
        else:
            self.logs_text.insert(tk.END, "No logs available.")
        self.log_progress.stop()

    # ---------------- Periodic Refresh ----------------
    def periodic_refresh(self):
        self.update_jobs()
        self.refresh_logs()
        self.after(5000, self.periodic_refresh)  # Refresh every 5 seconds


# ----------------------------
# Job Editing Window
# ----------------------------
class EditJobWindow(tk.Toplevel):
    def __init__(self, master, job):
        super().__init__(master)
        self.master = master
        self.job = job  # job tuple: (id, script_path, hour, minute, second, frequency, active, scheduler_id)
        self.title(f"Edit Job {job[0]}")
        self.create_widgets()

    def create_widgets(self):
        ttk.Label(self, text="Script Path:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.script_entry = ttk.Entry(self, width=50)
        self.script_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.script_entry.insert(0, self.job[1])
        ttk.Label(self, text="Hour (0-23):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.hour_spin = tk.Spinbox(self, from_=0, to=23, width=5)
        self.hour_spin.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.hour_spin.delete(0, tk.END)
        self.hour_spin.insert(0, self.job[2])
        ttk.Label(self, text="Minute (0-59):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.minute_spin = tk.Spinbox(self, from_=0, to=59, width=5)
        self.minute_spin.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.minute_spin.delete(0, tk.END)
        self.minute_spin.insert(0, self.job[3])
        ttk.Label(self, text="Second (0-59):").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.second_spin = tk.Spinbox(self, from_=0, to=59, width=5)
        self.second_spin.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.second_spin.delete(0, tk.END)
        self.second_spin.insert(0, self.job[4])
        ttk.Label(self, text="Frequency:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.freq_var = tk.StringVar()
        self.freq_combo = ttk.Combobox(self, textvariable=self.freq_var, state="readonly",
                                       values=["once", "daily", "weekly", "monthly", "custom"])
        self.freq_combo.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        self.freq_combo.set(self.job[5])
        self.freq_combo.bind("<<ComboboxSelected>>", self.freq_selected)
        self.custom_label = ttk.Label(self, text="Custom Interval (Days):")
        self.custom_spin = tk.Spinbox(self, from_=1, to=30, width=5)
        if self.job[5].startswith("custom_"):
            self.custom_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
            self.custom_spin.grid(row=5, column=1, padx=5, pady=5, sticky="w")
            try:
                custom_days = int(self.job[5].split("_")[1].replace("d", ""))
                self.custom_spin.delete(0, tk.END)
                self.custom_spin.insert(0, custom_days)
            except:
                self.custom_spin.insert(0, 1)
        ttk.Button(self, text="Save Changes", command=self.save_changes) \
            .grid(row=6, column=0, columnspan=2, padx=5, pady=10)

    def freq_selected(self, event):
        if self.freq_var.get() == "custom":
            self.custom_label.grid(row=5, column=0, padx=5, pady=5, sticky="w")
            self.custom_spin.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        else:
            self.custom_label.grid_forget()
            self.custom_spin.grid_forget()

    def save_changes(self):
        script_path = self.script_entry.get()
        try:
            hour = int(self.hour_spin.get())
            minute = int(self.minute_spin.get())
            second = int(self.second_spin.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid time values.")
            return
        frequency = self.freq_var.get()
        if frequency == "custom":
            try:
                custom_days = int(self.custom_spin.get())
                frequency = f"custom_{custom_days}d"
            except ValueError:
                messagebox.showerror("Error", "Invalid custom interval.")
                return
        active = 1  # Keep the same active status
        job_db_id = self.job[0]
        update_job_in_db(job_db_id, script_path, hour, minute, second, frequency, active)
        reschedule_job(job_db_id, script_path, hour, minute, second, frequency)
        self.master.set_status(f"Job {job_db_id} updated.")
        self.master.update_jobs()
        self.destroy()


# ----------------------------
# Main Entry Point
# ----------------------------
if __name__ == "__main__":
    app = SchedulerApp()
    app.mainloop()
