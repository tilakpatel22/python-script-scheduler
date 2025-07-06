# 🕒 Fincept Task Scheduler (Python GUI + APScheduler)

A powerful desktop GUI application for scheduling and managing Python scripts with full logging, frequency control, and persistent storage — built using `Tkinter`, `APScheduler`, and `SQLite`.

---

## 🚀 Features

- ✅ Schedule Python scripts to run:
  - Once
  - Daily
  - Weekly
  - Monthly
  - Custom intervals (e.g., every X days)
- 🧠 View, Edit, Enable/Disable, and Delete jobs
- 📦 Upload `.py` scripts directly from the GUI
- 📝 View execution logs with keyword filtering
- 🧵 Asynchronous script execution using `ThreadPoolExecutor`
- 💾 Persistent job storage using SQLite (`apscheduler_jobs.db`)
- 📊 Filterable, sortable job list view
- 🔁 Auto-refresh every 5 seconds

---

## 🖥️ Technologies Used

| Component     | Description                      |
|---------------|----------------------------------|
| Python 3.x    | Core programming language        |
| Tkinter       | GUI interface                    |
| APScheduler   | Background job scheduling        |
| SQLite        | Local database for persistence   |
| Pandas        | Data management & filtering      |
| ThreadPoolExecutor | Async script execution     |

---

## 📁 Directory Structure

```bash
.
├── scheduled_jobs.db        # Stores job configurations
├── apscheduler_jobs.db      # APScheduler persistent storage
├── script_logs.txt          # Output & error logs of scheduled jobs
├── D:\WorldEconomicEngineProj\IndiaStockExchange\
│   └── your_uploaded_scripts.py
└── your_main_script.py      # This code
