from flask import Flask, render_template, request, jsonify
import database

app = Flask(__name__)

# Initialize database on startup
database.init_db()


def get_encouraging_message(response: str, successful_count: int, target: int) -> dict:
    """Generate an encouraging message based on response type and progress."""
    remaining = target - successful_count
    
    # Check if on rampage (one away from target) - only for successful responses
    if response in ("A", "B", "C") and remaining == 1:
        return {
            "text": "You're on Rampage, let's get it done!",
            "type": "rampage",
            "emoji": "⚡🔥"
        }
    
    if response in ("A", "B", "C"):
        if remaining <= 0:
            return {
                "text": "Target achieved! Keep the momentum going!",
                "type": "success",
                "emoji": "🎉🏆"
            }
        return {
            "text": f"Great, {remaining} to go!",
            "type": "success",
            "emoji": "🎉"
        }
    elif response == "NA":
        return {
            "text": "Call this guy next time, let's go for next!",
            "type": "followup",
            "emoji": "🔥"
        }
    else:  # DNP
        return {
            "text": "Someone's waiting for your call. Let's reach till there!",
            "type": "retry",
            "emoji": "🔥🔥"
        }


@app.route("/")
def dashboard():
    """Render the main dashboard."""
    # Get selected date from query param, default to today
    selected_date = request.args.get("date", database.get_today())
    today = database.get_today()
    
    target = database.get_daily_target(selected_date)
    stats = database.get_today_stats(selected_date)
    calls = database.get_today_calls(selected_date)
    contacts = database.get_contacts_for_date(selected_date)
    
    return render_template(
        "index.html",
        target=target,
        stats=stats,
        calls=calls,
        contacts=contacts,
        selected_date=selected_date,
        today=today,
        is_today=(selected_date == today)
    )


@app.route("/set-target", methods=["POST"])
def set_target():
    """Set the daily target."""
    data = request.get_json()
    target = int(data.get("target", 0))
    selected_date = data.get("date", database.get_today())
    
    if target < 1:
        return jsonify({"error": "Target must be at least 1"}), 400
    
    database.set_daily_target(target, selected_date)
    return jsonify({"success": True, "target": target})


@app.route("/add-call", methods=["POST"])
def add_call():
    """Add a new call record."""
    data = request.get_json()
    name = data.get("name", "").strip()
    response = data.get("response", "").upper()
    selected_date = data.get("date", database.get_today())
    
    if not name:
        return jsonify({"error": "Name is required"}), 400
    
    if response not in ("A", "B", "C", "NA", "DNP"):
        return jsonify({"error": "Invalid response type"}), 400
    
    # Add the call
    call_id = database.add_call(name, response, selected_date)
    
    # Get updated stats
    stats = database.get_today_stats(selected_date)
    target = database.get_daily_target(selected_date) or 0
    
    # Generate encouraging message
    message = get_encouraging_message(response, stats["successful"], target)
    
    return jsonify({
        "success": True,
        "call_id": call_id,
        "name": name,
        "stats": stats,
        "message": message
    })


@app.route("/stats")
def get_stats():
    """Get statistics for a specific date."""
    selected_date = request.args.get("date", database.get_today())
    stats = database.get_today_stats(selected_date)
    target = database.get_daily_target(selected_date)
    return jsonify({
        "stats": stats,
        "target": target
    })


@app.route("/delete-call", methods=["POST"])
def delete_call():
    """Delete a call record."""
    data = request.get_json()
    call_id = data.get("call_id")
    selected_date = data.get("date", database.get_today())
    
    if not call_id:
        return jsonify({"error": "Call ID is required"}), 400
    
    deleted = database.delete_call(call_id)
    
    if deleted:
        # Return updated stats
        stats = database.get_today_stats(selected_date)
        target = database.get_daily_target(selected_date) or 0
        return jsonify({
            "success": True,
            "stats": stats,
            "target": target
        })
    
    return jsonify({"error": "Call not found"}), 404


@app.route("/update-call", methods=["POST"])
def update_call():
    """Update an existing call's response."""
    data = request.get_json()
    call_id = data.get("call_id")
    response = data.get("response", "").upper()
    selected_date = data.get("date", database.get_today())
    
    if not call_id:
        return jsonify({"error": "Call ID is required"}), 400
    
    if response not in ("A", "B", "C", "NA", "DNP"):
        return jsonify({"error": "Invalid response type"}), 400
    
    updated = database.update_call(call_id, response)
    
    if updated:
        # Get updated stats
        stats = database.get_today_stats(selected_date)
        target = database.get_daily_target(selected_date) or 0
        
        # Generate encouraging message
        message = get_encouraging_message(response, stats["successful"], target)
        
        return jsonify({
            "success": True,
            "stats": stats,
            "message": message
        })
    
    return jsonify({"error": "Call not found"}), 404


# Contact management routes
@app.route("/contacts")
def get_contacts():
    """Get all contacts."""
    contacts = database.get_all_contacts()
    return jsonify({"contacts": contacts})


@app.route("/add-contact", methods=["POST"])
def add_contact():
    """Add a new contact for a specific date."""
    data = request.get_json()
    name = data.get("name", "").strip()
    selected_date = data.get("date", database.get_today())
    
    if not name:
        return jsonify({"error": "Name is required"}), 400
    
    try:
        contact_id = database.add_contact(name, selected_date)
        return jsonify({
            "success": True,
            "contact": {"id": contact_id, "name": name}
        })
    except ValueError as e:
        # Contact already exists in the database
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to add contact: {str(e)}"}), 400


@app.route("/delete-contact", methods=["POST"])
def delete_contact():
    """Delete a contact."""
    data = request.get_json()
    contact_id = data.get("contact_id")
    
    if not contact_id:
        return jsonify({"error": "Contact ID is required"}), 400
    
    deleted = database.delete_contact(contact_id)
    
    if deleted:
        return jsonify({"success": True})
    
    return jsonify({"error": "Contact not found"}), 404


@app.route("/summary")
def summary():
    """Render the summary page with all contacts and their latest responses."""
    # Get filter from query params (comma-separated)
    filter_param = request.args.get("filter", "")
    filters = [f.strip().upper() for f in filter_param.split(",") if f.strip()]
    
    # Map 'NA' display to actual filter
    filters = ['NA' if f == 'N/A' else f for f in filters]
    
    contacts = database.get_all_contacts_summary(filters if filters else None)
    today = database.get_today()
    
    # Get names that are already in today's list
    added_to_today = database.get_contacts_added_today()
    
    return render_template(
        "summary.html",
        contacts=contacts,
        active_filters=filters,
        today=today,
        added_to_today=added_to_today
    )


@app.route("/add-to-today", methods=["POST"])
def add_to_today():
    """Add a contact name to today's list (from summary page)."""
    data = request.get_json()
    name = data.get("name", "").strip()
    
    if not name:
        return jsonify({"error": "Name is required"}), 400
    
    today = database.get_today()
    
    try:
        # skip_global_check=True because these contacts already exist from previous dates
        contact_id = database.add_contact(name, today, skip_global_check=True)
        return jsonify({
            "success": True,
            "already_exists": False,
            "contact": {"id": contact_id, "name": name}
        })
    except ValueError as e:
        # Already in today's list
        return jsonify({
            "success": True,
            "already_exists": True,
            "contact": {"name": name}
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/add-multiple-to-today", methods=["POST"])
def add_multiple_to_today():
    """Add multiple contact names to today's list (from summary page)."""
    data = request.get_json()
    names = data.get("names", [])
    
    if not names:
        return jsonify({"error": "Names are required"}), 400
    
    today = database.get_today()
    added = []
    skipped = []
    
    for name in names:
        name = name.strip()
        if not name:
            continue
        try:
            # skip_global_check=True because these contacts already exist from previous dates
            database.add_contact(name, today, skip_global_check=True)
            added.append(name)
        except:
            skipped.append(name)
    
    return jsonify({
        "success": True,
        "added": added,
        "skipped": skipped,
        "added_count": len(added),
        "skipped_count": len(skipped)
    })


@app.route("/month-achievements")
def month_achievements():
    """Get achievement data for a month."""
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    
    if not year or not month:
        # Default to current month
        today = database.get_today()
        parts = today.split('-')
        year = int(parts[0])
        month = int(parts[1])
    
    achievements = database.get_month_achievements(year, month)
    return jsonify({"achievements": achievements})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
