import eventlet
eventlet.monkey_patch()

from flask import Flask, send_file, send_from_directory, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import time
from collections import defaultdict

# --- Config ---
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

user_sessions = {}           # sid → {username, room}
last_disconnect = {}         # username → timestamp
room_users = defaultdict(dict)  # room → {sid: username}

app = Flask(__name__)
app.secret_key = "your_secret_key"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Serve Files ---
@app.route("/")
def index():
    return send_file("login.html")

@app.route("/chat.html")
def chat():
    return send_file("chat.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# 🔐 File Upload API with sanitization
@app.route("/upload", methods=["POST"])
def upload_file():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    safe_name = secure_filename(file.filename)
    timestamp = int(time.time())
    name, ext = os.path.splitext(safe_name)
    unique_filename = f"{name}_{timestamp}{ext}"

    file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(file_path)

    return jsonify({"url": f"/uploads/{unique_filename}"}), 200

# --- Socket Events ---
@socketio.on("join")
def handle_join(data):
    username = data.get("username", "Anonymous")
    room = data.get("room", "default")
    sid = request.sid

    join_room(room)
    user_sessions[sid] = {"username": username, "room": room}
    room_users[room][sid] = username

    now = time.time()
    last = last_disconnect.get(username, 0)
    rejoined = now - last <= 3

    msg = f"🔄 {username} reconnected." if rejoined else f"✅ {username} joined the room."
    emit("message", {"username": "System", "message": msg}, room=room)

    if username in last_disconnect:
        del last_disconnect[username]

    emit_user_list(room)

@socketio.on("leave")
def handle_leave(data):
    sid = request.sid
    room = data.get("room")
    if sid in user_sessions:
        username = user_sessions[sid]["username"]
        leave_room(room)
        if sid in room_users[room]:
            del room_users[room][sid]
        del user_sessions[sid]
        last_disconnect[username] = time.time()
        emit("message", {"username": "System", "message": f"🚪 {username} left the chat."}, room=room)
        emit_user_list(room)

@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    user = user_sessions.get(sid)
    if user:
        room = user["room"]
        username = user["username"]
        leave_room(room)
        if sid in room_users[room]:
            del room_users[room][sid]
        del user_sessions[sid]
        last_disconnect[username] = time.time()
        emit("message", {"username": "System", "message": f"🚪 {username} left the chat."}, room=room)
        emit_user_list(room)

def emit_user_list(room):
    users = list(room_users[room].values())
    emit("update_user_list", {
        "users": users,
        "count": len(users)
    }, room=room)

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

@socketio.on("typing")
def handle_typing(data):
    sid = request.sid
    user = user_sessions.get(sid)
    if not user:
        return
    emit("typing", {"username": user["username"]}, room=user["room"], include_self=False)

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

@socketio.on("offer")
def handle_offer(data):
    emit("offer", {
        "offer": data["offer"],
        "username": data["username"],
        "video": data["video"]
    }, room=data["room"], include_self=False)

@socketio.on("answer")
def handle_answer(data):
    emit("answer", {
        "answer": data["answer"]
    }, room=data["room"], include_self=False)

@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    emit("ice-candidate", {
        "candidate": data["candidate"]
    }, room=data["room"], include_self=False)

@socketio.on("reject-call")
def handle_reject_call(data):
    emit("call-rejected", {
        "username": data["username"]
    }, room=data["room"], include_self=False)

@socketio.on("call-ended")
def handle_call_end(data):
    emit("call-ended", {
        "username": data["username"]
    }, room=data["room"], include_self=False)

# --- Run App ---
if __name__ == "__main__":
    print("🚀 Server running at http://127.0.0.1:5000/")
    socketio.run(app, host="0.0.0.0", port=5000)