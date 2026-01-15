import sqlite3
import threading
from datetime import date
from typing import Optional

DATABASE_PATH = "calls.db"

# Singleton connection manager
class DatabaseConnection:
    _instance = None
    _lock = threading.Lock()
    _connection = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_connection(self):
        """Get or create the singleton database connection."""
        if self._connection is None:
            with self._lock:
                if self._connection is None:
                    self._connection = sqlite3.connect(
                        DATABASE_PATH, 
                        timeout=30,
                        check_same_thread=False  # Allow multi-threaded access
                    )
                    self._connection.row_factory = sqlite3.Row
                    # Enable WAL mode for better concurrent access
                    self._connection.execute("PRAGMA journal_mode=WAL")
                    self._connection.execute("PRAGMA busy_timeout=30000")
        return self._connection
    
    def close(self):
        """Close the connection if open."""
        if self._connection:
            with self._lock:
                if self._connection:
                    self._connection.close()
                    self._connection = None

# Global singleton instance
_db_manager = DatabaseConnection()


def get_connection():
    """Get the singleton database connection."""
    return _db_manager.get_connection()


def init_db():
    """Initialize the database with required tables."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create daily_targets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_targets (
            date TEXT PRIMARY KEY,
            target INTEGER NOT NULL
        )
    """)
    
    # Create calls table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            response TEXT NOT NULL CHECK(response IN ('A', 'B', 'C', 'NA', 'DNP', 'CATCHUP')),
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create contacts table (pre-added names with date)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            date TEXT NOT NULL DEFAULT (date('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, date)
        )
    """)
    
    # Migration: Add date column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE contacts ADD COLUMN date TEXT NOT NULL DEFAULT (date('now'))")
    except:
        pass  # Column already exists
    
    conn.commit()


def get_today() -> str:
    """Get today's date as string."""
    return date.today().isoformat()


def get_daily_target(target_date: Optional[str] = None) -> Optional[int]:
    """Get the daily target for a specific date (defaults to today)."""
    if target_date is None:
        target_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT target FROM daily_targets WHERE date = ?", (target_date,))
    row = cursor.fetchone()
    return row["target"] if row else None


def set_daily_target(target: int, target_date: Optional[str] = None) -> None:
    """Set or update the daily target for a specific date (defaults to today)."""
    if target_date is None:
        target_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO daily_targets (date, target) VALUES (?, ?)
    """, (target_date, target))
    conn.commit()


def add_call(name: str, response: str, call_date: Optional[str] = None) -> int:
    """Add a new call record. Returns the new call ID."""
    if call_date is None:
        call_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO calls (name, response, date) VALUES (?, ?, ?)
    """, (name, response, call_date))
    call_id = cursor.lastrowid
    conn.commit()
    return call_id


def get_today_calls(call_date: Optional[str] = None) -> list:
    """Get all calls for a specific date (defaults to today)."""
    if call_date is None:
        call_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, response, created_at 
        FROM calls 
        WHERE date = ? 
        ORDER BY created_at DESC
    """, (call_date,))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_today_stats(call_date: Optional[str] = None) -> dict:
    """Get statistics for a specific date (defaults to today)."""
    if call_date is None:
        call_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get counts by response type
    cursor.execute("""
        SELECT response, COUNT(*) as count 
        FROM calls 
        WHERE date = ? 
        GROUP BY response
    """, (call_date,))
    
    stats = {
        "A": 0,
        "B": 0,
        "C": 0,
        "NA": 0,
        "DNP": 0,
        "CATCHUP": 0,
        "total": 0,
        "successful": 0  # A + B + C
    }
    
    for row in cursor.fetchall():
        response = row["response"]
        count = row["count"]
        if response in stats:
            stats[response] = count
        stats["total"] += count
        if response in ("A", "B", "C"):
            stats["successful"] += count
    
    return stats


def contact_exists_anywhere(name: str) -> bool:
    """Check if a contact with this name exists anywhere in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM contacts WHERE LOWER(name) = LOWER(?)", (name,))
    return cursor.fetchone() is not None


# Contact management functions
def add_contact(name: str, contact_date: Optional[str] = None, skip_global_check: bool = False) -> int:
    """
    Add a new contact for a specific date. Returns the contact ID.
    
    skip_global_check: If True, only checks if contact exists for the specific date
                       (used when adding from summary page to today's list)
    """
    if contact_date is None:
        contact_date = get_today()
    
    # Check if name already exists for this date
    if contact_exists_for_date(name, contact_date):
        raise ValueError(f"Contact '{name}' already in today's list")
    
    # Check if name already exists anywhere (unless skipped)
    if not skip_global_check and contact_exists_anywhere(name):
        raise ValueError(f"Contact '{name}' already exists")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO contacts (name, date) VALUES (?, ?)", (name, contact_date))
    contact_id = cursor.lastrowid
    conn.commit()
    return contact_id


def get_contacts_for_date(target_date: Optional[str] = None) -> list:
    """
    Get contacts to show for a specific date.
    Shows:
    - ALL contacts added on that date (always shown, regardless of call status)
    - Contacts from previous dates that were never called (carry forward)
    - Contacts from previous dates whose last response was DNP (carry forward)
    - Contacts from previous dates that have a call logged on target_date (already handled today)
    
    Ordered by: attempted calls first, then non-attempted
    Returns only unique names (prefers today's entry if exists).
    """
    if target_date is None:
        target_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all relevant contacts with a flag for whether they have a call today
    # Use GROUP BY name to ensure unique names, preferring entries from target_date
    cursor.execute("""
        SELECT 
            MAX(CASE WHEN c.date = ? THEN c.id ELSE c.id END) as id,
            c.name, 
            MAX(c.date) as added_date,
            CASE WHEN EXISTS (
                SELECT 1 FROM calls WHERE calls.name = c.name AND calls.date = ?
            ) THEN 1 ELSE 0 END as has_call_today
        FROM contacts c
        WHERE 
            -- Contacts added on target_date (always show)
            c.date = ?
            
            -- Previous contacts that need to carry forward (uncalled)
            OR (c.date < ? AND NOT EXISTS (
                SELECT 1 FROM calls WHERE calls.name = c.name
            ))
            
            -- Previous contacts whose last response was DNP
            OR (c.date < ? AND (
                SELECT response FROM calls 
                WHERE calls.name = c.name 
                ORDER BY date DESC, created_at DESC 
                LIMIT 1
            ) = 'DNP')
            
            -- Previous contacts that have a call logged on target_date
            OR (c.date < ? AND EXISTS (
                SELECT 1 FROM calls WHERE calls.name = c.name AND calls.date = ?
            ))
        
        GROUP BY c.name
        ORDER BY has_call_today DESC, MIN(c.created_at) ASC
    """, (target_date, target_date, target_date, target_date, target_date, target_date, target_date))
    
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_all_contacts() -> list:
    """Get all contacts (for backwards compatibility)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM contacts ORDER BY name ASC")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def delete_contact(contact_id: int) -> bool:
    """Delete a contact by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    return deleted


def contact_exists_for_date(name: str, target_date: Optional[str] = None) -> bool:
    """Check if a contact with this name exists for the given date."""
    if target_date is None:
        target_date = get_today()
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM contacts WHERE name = ? AND date = ?",
        (name, target_date)
    )
    return cursor.fetchone() is not None


def get_contacts_added_today() -> set:
    """Get set of contact names that are in today's list."""
    today = get_today()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM contacts WHERE date = ?", (today,))
    return {row['name'] for row in cursor.fetchall()}


def get_month_achievements(year: int, month: int) -> dict:
    """
    Get achievement status for each day in a month.
    Returns dict with date strings as keys and achievement status as values.
    Achievement = successful calls >= target for that day.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all targets and successful call counts for the month
    start_date = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end_date = f"{year+1:04d}-01-01"
    else:
        end_date = f"{year:04d}-{month+1:02d}-01"
    
    # Get targets for the month
    cursor.execute("""
        SELECT date, target FROM daily_targets
        WHERE date >= ? AND date < ?
    """, (start_date, end_date))
    targets = {row['date']: row['target'] for row in cursor.fetchall()}
    
    # Get successful call counts for the month
    cursor.execute("""
        SELECT date, COUNT(*) as successful
        FROM calls
        WHERE date >= ? AND date < ? AND response IN ('A', 'B', 'C')
        GROUP BY date
    """, (start_date, end_date))
    successful_counts = {row['date']: row['successful'] for row in cursor.fetchall()}
    
    # Determine achievements
    achievements = {}
    for date_str, target in targets.items():
        successful = successful_counts.get(date_str, 0)
        achievements[date_str] = successful >= target
    
    return achievements


def delete_call(call_id: int) -> bool:
    """Delete a call by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM calls WHERE id = ?", (call_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    return deleted


def update_call(call_id: int, response: str) -> bool:
    """Update the response of an existing call."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE calls SET response = ? WHERE id = ?", (response, call_id))
    updated = cursor.rowcount > 0
    conn.commit()
    return updated


def get_all_contacts_summary(filters: list = None) -> list:
    """
    Get summary of all contacts with their latest response.
    Includes DNP count for contacts whose latest response is DNP.
    
    filters: list of response types to include (e.g., ['A', 'B', 'DNP', 'UN'])
             'UN' means un-attempted contacts
             None or empty means all
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all contacts with their latest call info and DNP count
    cursor.execute("""
        SELECT 
            c.id,
            c.name,
            c.date as added_date,
            latest.response as latest_response,
            latest.date as last_called_date,
            COALESCE(dnp_counts.dnp_count, 0) as dnp_count
        FROM contacts c
        LEFT JOIN (
            -- Get the latest call for each contact
            SELECT 
                name,
                response,
                date,
                ROW_NUMBER() OVER (PARTITION BY name ORDER BY date DESC, created_at DESC) as rn
            FROM calls
        ) latest ON c.name = latest.name AND latest.rn = 1
        LEFT JOIN (
            -- Count total DNP calls for each contact
            SELECT name, COUNT(*) as dnp_count
            FROM calls
            WHERE response = 'DNP'
            GROUP BY name
        ) dnp_counts ON c.name = dnp_counts.name
        GROUP BY c.name
        ORDER BY 
            CASE WHEN latest.response IS NULL THEN 1 ELSE 0 END,
            latest.date DESC,
            c.name ASC
    """)
    
    rows = cursor.fetchall()
    
    results = []
    for row in rows:
        item = dict(row)
        # Determine the display response
        if item['latest_response'] is None:
            item['display_response'] = 'UN'  # Un-attempted
        else:
            item['display_response'] = item['latest_response']
        results.append(item)
    
    # Apply filters if specified
    if filters and len(filters) > 0:
        results = [r for r in results if r['display_response'] in filters]
    
    return results


def get_contact_call_history(contact_name: str) -> list:
    """Get all calls for a specific contact."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, response, date, created_at
        FROM calls
        WHERE name = ?
        ORDER BY date DESC, created_at DESC
    """, (contact_name,))
    rows = cursor.fetchall()
    return [dict(row) for row in rows]
