import bleach
import eventlet
eventlet.monkey_patch()

from flask import Flask, send_file, send_from_directory, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room, emit
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import time
import uuid
from collections import defaultdict

# --- Configuration ---
UPLOAD_FOLDER = "uploads"
STATIC_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# User management
user_sessions = {}           # sid → {username, room}
last_disconnect = {}         # username → timestamp
room_users = defaultdict(dict)  # room → {sid: username}
active_calls = defaultdict(dict)  # room → call_info

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- File serving routes ---
@app.route("/")
def index():
    return send_file("login.html")

@app.route("/chat")
def chat():
    return send_file("chat.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(STATIC_FOLDER, filename)

# --- Enhanced file upload with better security ---
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        file = request.files.get("file")
        if not file or file.filename == '':
            return jsonify({"error": "No file provided"}), 400

        # Security checks
        if file.content_length > 50 * 1024 * 1024:  # 50MB limit
            return jsonify({"error": "File too large"}), 400

        safe_name = secure_filename(file.filename)
        if not safe_name:
            return jsonify({"error": "Invalid filename"}), 400

        # Generate unique filename
        name, ext = os.path.splitext(safe_name)
        unique_id = str(uuid.uuid4())
        unique_filename = f"{unique_id}{ext}"

        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)

        return jsonify({
            "url": f"/uploads/{unique_filename}",
            "original_name": safe_name,
            "size": os.path.getsize(file_path)
        }), 200

    except Exception as e:
        return jsonify({"error": "Upload failed"}), 500

# --- Enhanced socket events ---
@socketio.on("join")
def handle_join(data):
    try:
        username = bleach.clean(data.get("username", "Anonymous"))
        room = bleach.clean(data.get("room", "default"))
        sid = request.sid

        # Validate input
        if not username or not room:
            emit("error", {"message": "Invalid username or room"})
            return

        join_room(room)
        user_sessions[sid] = {"username": username, "room": room}
        room_users[room][sid] = username

        # Check if user recently disconnected
        now = time.time()
        last = last_disconnect.get(username, 0)
        rejoined = now - last <= 5

        msg = f"🔄 {username} reconnected" if rejoined else f"✅ {username} joined the chat"
        emit("message", {"username": "System", "message": msg}, room=room)

        if username in last_disconnect:
            del last_disconnect[username]

        emit_user_list(room)

    except Exception as e:
        emit("error", {"message": "Failed to join room"})

@socketio.on("leave")
def handle_leave(data):
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user:
            return

        room = user["room"]
        username = user["username"]
        
        leave_room(room)
        if sid in room_users[room]:
            del room_users[room][sid]
        del user_sessions[sid]
        
        last_disconnect[username] = time.time()
        emit("message", {"username": "System", "message": f"🚪 {username} left the chat"}, room=room)
        emit_user_list(room)

    except Exception as e:
        pass

@socketio.on("disconnect")
def handle_disconnect():
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user:
            return

        room = user["room"]
        username = user["username"]
        
        leave_room(room)
        if sid in room_users[room]:
            del room_users[room][sid]
        del user_sessions[sid]
        
        last_disconnect[username] = time.time()
        emit("message", {"username": "System", "message": f"🚪 {username} disconnected"}, room=room)
        emit_user_list(room)

    except Exception as e:
        pass

def emit_user_list(room):
    """Emit updated user list to room"""
    users = list(room_users[room].values())
    socketio.emit("update_user_list", {
        "users": users,
        "count": len(users)
    }, room=room)

@socketio.on("message")
def handle_message(data):
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user:
            return

        # Enhanced message sanitization
        username = bleach.clean(user["username"])
        raw_msg = data.get("message", "")
        
        # Allow some safe HTML tags for links and files
        allowed_tags = ['a', 'br']
        allowed_attributes = {'a': ['href', 'download', 'target', 'rel', 'class', 'style']}
        message = bleach.clean(raw_msg, tags=allowed_tags, attributes=allowed_attributes, strip=True)

        if not message.strip():
            return

        emit("message", {
            "username": username,
            "message": message,
            "timestamp": time.time()
        }, room=user["room"])

    except Exception as e:
        emit("error", {"message": "Failed to send message"})

@socketio.on("typing")
def handle_typing(data):
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user:
            return
        
        emit("typing", {
            "username": user["username"],
            "timestamp": time.time()
        }, room=user["room"], include_self=False)

    except Exception as e:
        pass

# --- Enhanced WebRTC signaling ---
@socketio.on("offer")
def handle_offer(data):
    try:
        room = data.get("room")
        if not room:
            return

        emit("offer", {
            "offer": data["offer"],
            "username": data["username"],
            "video": data.get("video", False)
        }, room=room, include_self=False)

        # Track active call
        active_calls[room] = {
            "caller": data["username"],
            "type": "video" if data.get("video") else "audio",
            "timestamp": time.time()
        }

    except Exception as e:
        emit("error", {"message": "Failed to initiate call"})

@socketio.on("answer")
def handle_answer(data):
    try:
        emit("answer", {
            "answer": data["answer"]
        }, room=data["room"], include_self=False)

    except Exception as e:
        pass

@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    try:
        emit("ice-candidate", {
            "candidate": data["candidate"]
        }, room=data["room"], include_self=False)

    except Exception as e:
        pass

@socketio.on("reject-call")
def handle_reject_call(data):
    try:
        room = data.get("room")
        emit("call-rejected", {
            "username": data["username"]
        }, room=room, include_self=False)

        # Clear active call
        if room in active_calls:
            del active_calls[room]

    except Exception as e:
        pass

@socketio.on("call-ended")
def handle_call_end(data):
    try:
        room = data.get("room")
        emit("call-ended", {
            "username": data["username"]
        }, room=room, include_self=False)

        # Clear active call
        if room in active_calls:
            del active_calls[room]

    except Exception as e:
        pass

# --- Health check endpoint ---
@app.route("/health")
def health_check():
    return jsonify({
        "status": "healthy",
        "active_rooms": len(room_users),
        "total_users": sum(len(users) for users in room_users.values()),
        "active_calls": len(active_calls),
        "timestamp": time.time()
    })

# --- Error handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    print("🚀 Enhanced Chat Server Starting...")
    print("📍 Server running at http://127.0.0.1:5000/")
    print("📊 Health check available at http://127.0.0.1:5000/health")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False)