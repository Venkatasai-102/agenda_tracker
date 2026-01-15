# 📞 Daily Calls Tracker

A local web application to track daily call targets, manage contacts, and monitor call progress with encouraging messages.

## ✨ Features

### Daily Call Tracking
- **Set Daily Targets**: Define how many successful calls you want to make each day
- **Track Responses**: Log call responses as A, B, C, N/A, or DNP (Didn't Pick Phone)
- **Progress Bar**: Visual indicator showing progress towards daily target
- **Encouraging Messages**: Motivational messages based on response type and progress

### Contact Management
- **Today's Lucky Folks**: Table showing contacts scheduled for the day
- **Carry-Forward Logic**: 
  - Contacts not called carry forward to the next day
  - DNP contacts automatically appear the next day for follow-up
- **Duplicate Prevention**: Same contact name cannot be added twice globally

### Summary & Analytics
- **Summary Page**: View all contacts with their latest response
- **Filters**: Filter by response type (A, B, C, N/A, DNP, Un-Attempted)
- **Multi-Select Filters**: Combine multiple filters
- **DNP Count**: Track how many times a contact didn't pick up
- **Bulk Add**: Add all filtered contacts to today's list with one click
- **Add to Today**: Easily re-add any contact to today's list

### Calendar View
- **Monthly Calendar**: Shows current month with navigation
- **Achievement Icons**: 🎉 icon appears on days where target was achieved
- **Date Navigation**: Quick navigation with < > buttons

### UI/UX
- **Dark Theme**: Easy on the eyes with orange/green accents
- **Sidebar Navigation**: Hover to expand, quick access to pages
- **Responsive Design**: Clean, modern interface
- **Date Format**: dd/mm/yyyy for easy reading

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python Flask |
| Database | SQLite with WAL mode |
| Frontend | HTML, CSS, JavaScript |
| Templating | Jinja2 |

## 📁 Project Structure

```
agenda_tracker/
├── app.py              # Flask application & routes
├── database.py         # Database operations (singleton pattern)
├── calls.db            # SQLite database (auto-created)
├── requirements.txt    # Python dependencies
├── static/
│   └── style.css       # Styling
├── templates/
│   ├── index.html      # Main dashboard
│   └── summary.html    # Summary page
└── venv/               # Virtual environment
```

## 🗄️ Database Schema

### Tables

**daily_targets**
- `date` (TEXT, PRIMARY KEY) - Date in YYYY-MM-DD format
- `target` (INTEGER) - Daily call target

**contacts**
- `id` (INTEGER, PRIMARY KEY)
- `name` (TEXT) - Contact name
- `date` (TEXT) - Date when contact was added
- `created_at` (TIMESTAMP) - Creation timestamp
- UNIQUE constraint on (name, date)

**calls**
- `id` (INTEGER, PRIMARY KEY)
- `name` (TEXT) - Contact name
- `response` (TEXT) - One of: A, B, C, NA, DNP
- `date` (TEXT) - Call date
- `created_at` (TIMESTAMP) - Creation timestamp

## 🚀 Setup Instructions

### Prerequisites
- Python 3.10+ installed
- pip (Python package manager)

### Installation

1. **Clone/Navigate to the project**
   ```bash
   cd agenda_tracker
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**
   
   On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```
   
   On Windows:
   ```bash
   venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**
   ```bash
   python -c "from app import app; app.run(debug=True, port=5001)"
   ```
   
   Or simply:
   ```bash
   flask run --port 5001
   ```

6. **Open in browser**
   ```
   http://127.0.0.1:5001
   ```

## 📖 Usage Guide

### Setting a Daily Target
1. Enter your target number in the input field at the top
2. Click "Set" to save

### Adding Contacts
1. Type a name in "Add new name..." field
2. Press Enter or click "+ Add"
3. Contact appears in "Today's Lucky Folks" table

### Logging Call Responses
1. Find the contact in the table
2. Select a response from the dropdown:
   - **A, B, C**: Successful calls (counts towards target)
   - **N/A**: Not applicable
   - **DNP**: Didn't Pick Phone (carries forward)

### Using the Summary Page
1. Hover over the sidebar and click "Summary"
2. Use filter buttons to find specific contacts
3. Click "+ Today" to add a contact back to today's list
4. Use "Add X to Today" button to bulk-add filtered contacts

### Viewing Past Days
1. Use < > buttons to navigate dates
2. Click "Today" to return to current date
3. Check the calendar for days with 🎉 (target achieved)

## 🔧 Technical Details

### Singleton Database Connection
The application uses a thread-safe singleton pattern for database connections to prevent "database is locked" errors:
- Single connection reused across all operations
- Thread lock for concurrent access safety
- WAL (Write-Ahead Logging) mode enabled
- 30-second timeout for busy operations

### Carry-Forward Logic
Contacts automatically appear on subsequent days if:
1. They were never called (no response logged)
2. Their last response was DNP

### Response Color Coding
- **A**: Bright green (best response)
- **B**: Medium green
- **C**: Light green
- **N/A**: Orange
- **DNP**: Red/orange

## 📝 License

This project is for personal use.

---

Built with ❤️ for efficient call tracking
