import eventlet
eventlet.monkey_patch()

from flask import Flask, send_file, send_from_directory, request
from flask_socketio import SocketIO, join_room, emit
from flask_cors import CORS
import os
import base64
import time

user_sessions = {}           # sid → {username, room}
last_disconnect = {}         # username → last disconnect timestamp

app = Flask(__name__)
app.secret_key = "your_secret_key"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Serve static files
@app.route("/")
def index():
    return send_file("login.html")

@app.route("/chat.html")
def chat():
    return send_file("chat.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Handle new user joining
@socketio.on("join")
def handle_join(data):
    username = data.get("username", "Anonymous")
    room = data.get("room", "default")
    sid = request.sid

    join_room(room)
    user_sessions[sid] = {"username": username, "room": room}

    now = time.time()
    last = last_disconnect.get(username, 0)
    rejoined = now - last <= 3

    msg = f"🔄 {username} reconnected." if rejoined else f"✅ {username} joined the chat."

    emit("message", {
        "username": "System",
        "message": msg
    }, room=room)

    if username in last_disconnect:
        del last_disconnect[username]

# Handle user messages
@socketio.on("message")
def handle_message(data):
    sid = request.sid
    user = user_sessions.get(sid)
    if not user:
        return
    emit("message", {
        "username": user["username"],
        "message": data.get("message", "")
    }, room=user["room"])

# Handle typing status
@socketio.on("typing")
def handle_typing(data):
    sid = request.sid
    user = user_sessions.get(sid)
    if not user:
        return
    emit("typing", {"username": user["username"]}, room=user["room"])

# Handle file sharing
@socketio.on("file")
def handle_file(data):
    sid = request.sid
    user = user_sessions.get(sid)
    if not user:
        return

    file_name = data.get("fileName", "file.txt")
    file_data = data.get("data", "")

    emit("file", {
        "username": user["username"],
        "fileName": file_name,
        "data": file_data
    }, room=user["room"])

# Handle disconnects
@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    user = user_sessions.get(sid)
    if user:
        emit("message", {
            "username": "System",
            "message": f"🚪 {user['username']} left the chat."
        }, room=user["room"])
        last_disconnect[user["username"]] = time.time()
        del user_sessions[sid]

# Run the app
if __name__ == "__main__":
    print("🚀 Server running at http://127.0.0.1:5000/")
    socketio.run(app, host="0.0.0.0", port=5000)


