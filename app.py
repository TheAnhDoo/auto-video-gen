from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import datetime
import openai
import sqlite3
from config import OPENAI_API_KEY, DESCRIPT_API_URL

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

# Configure OpenAI API Key
openai.api_key = OPENAI_API_KEY

# Initialize database
DB_PATH = "database/scripts.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            script TEXT,
            source TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Function to create a video instantly
def create_video(script_text, video_name, image_style="low-polygon-3d"):
    payload = {
        "script": script_text,
        "image_style": image_style,
        "name": video_name
    }

    response = requests.post(DESCRIPT_API_URL, json=payload)

    if response.status_code == 200:
        video_url = response.json().get("url", "#")
        update_status(video_name, "completed")
        return video_url
    else:
        return None

# Function to store a script in the database
def save_script(title, script_text, source):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO scripts (title, script, source) VALUES (?, ?, ?)", (title, script_text, source))
    conn.commit()
    conn.close()

# Function to update script status
def update_status(title, status):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE scripts SET status = ? WHERE title = ?", (status, title))
    conn.commit()
    conn.close()

# Route for manual script input
@app.route("/manual", methods=["GET", "POST"])
def manual():
    if request.method == "POST":
        action = request.form.get("action")
        title = request.form.get("title")
        script_text = request.form.get("script")
        style = request.form.get("style", "low-polygon-3d")

        if action == "save":
            save_script(title, script_text, "manual")
            return jsonify({"success": True, "message": "Script saved successfully!"})

        elif action == "schedule":
            save_script(title, script_text, "manual")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE scripts SET status = 'scheduled' WHERE title = ?", (title,))
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "Video scheduled successfully!"})

        elif action == "create_now":
            save_script(title, script_text, "manual")
            video_url = create_video(script_text, title, style)
            return jsonify({"success": True, "url": video_url}) if video_url else jsonify({"success": False, "error": "Failed to create video"})

    return render_template("manual.html")

# Route for AI-generated scripts
@app.route("/auto", methods=["GET", "POST"])
def auto():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "generate":
            today = datetime.datetime.now()
            for i in range(10):
                date_str = (today + datetime.timedelta(days=i)).strftime("%B %d, %Y")
                prompt = f"Generate a creative numerology script for {date_str}. Include a suitable engaging title."

                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "system", "content": "You are a numerology expert."},
                              {"role": "user", "content": prompt}]
                )

                script_text = response["choices"][0]["message"]["content"]
                save_script(date_str, script_text, "AI")

            return jsonify({"success": True, "message": "AI scripts generated!"})

        elif action == "schedule":
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE scripts SET status = 'scheduled' WHERE source = 'AI'")
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "AI scripts scheduled!"})

        elif action == "create_now":
            script_id = request.form.get("script_id")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT title, script FROM scripts WHERE id = ?", (script_id,))
            script_data = cursor.fetchone()
            conn.close()

            if script_data:
                title, script_text = script_data
                video_url = create_video(script_text, title, "low-polygon-3d")
                return jsonify({"success": True, "url": video_url}) if video_url else jsonify({"success": False, "error": "Failed to create video"})

    return render_template("auto.html")

# Route to view saved scripts
@app.route("/history")
def history():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, script, source, status FROM scripts ORDER BY id DESC")
    scripts = cursor.fetchall()
    conn.close()
    return render_template("history.html", scripts=scripts)

if __name__ == "__main__":
    app.run(debug=True)
