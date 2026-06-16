from flask import Flask, render_template, jsonify
import subprocess
import sys
import os
import threading
import time

app = Flask(__name__, static_folder="static", template_folder="templates")

# -----------------------------
# Status Handling
# -----------------------------
status_data = {"visual": False, "sound": False}
_last = (False, False)
STATUS_FILE = "status.txt"

# Reset status.txt on Flask startup
with open(STATUS_FILE, "w") as f:
    f.write("0,0")

def status_watcher():
    """ Continuously read status.txt and update status_data """
    global status_data, _last
    while True:
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, "r") as f:
                    raw = f.read().strip()
                parts = raw.split(",")
                if len(parts) >= 2:
                    visual = parts[0].strip() == "1"
                    sound = parts[1].strip() == "1"
                    status_data["visual"] = visual
                    status_data["sound"] = sound
                    if (visual, sound) != _last:
                        print(f"[STATUS] visual={visual}, sound={sound}")
                        _last = (visual, sound)
        except Exception as e:
            print("Status watcher error:", e)
        time.sleep(1)

# Start the status watcher in a background thread
threading.Thread(target=status_watcher, daemon=True).start()

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("drone.html")

@app.route("/credits")
def credits():
    return render_template("credits.html")

@app.route("/start-detection", methods=["POST"])
def start_detection():
    """ Launch the detection script in a separate process """
    try:
        script_path = os.path.join(os.path.dirname(__file__), "Advanced_Drone_Detection.py")
        subprocess.Popen([sys.executable, script_path], stdout=None, stderr=None)
        return jsonify({"status": "🚀 Drone detection started in a new window!"})
    except Exception as e:
        return jsonify({"status": f"❌ Error: {str(e)}"}), 500

@app.route("/status")
def get_status():
    """ Return the latest visual/sound detection status """
    return jsonify(status_data)

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
