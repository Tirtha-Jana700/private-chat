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
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'mp3', 'mp4', 'wav', 'ogg', 'txt', 'zip'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# User management
user_sessions = {}
last_disconnect = {}
room_users = defaultdict(dict)
active_calls = defaultdict(dict)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=MAX_FILE_SIZE
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

# --- Enhanced file upload ---
@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        safe_name = secure_filename(file.filename)
        if not safe_name:
            return jsonify({"error": "Invalid filename"}), 400

        # Generate unique filename
        name, ext = os.path.splitext(safe_name)
        unique_id = str(uuid.uuid4())[:8]
        unique_filename = f"{unique_id}_{safe_name}"

        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)

        file_size = os.path.getsize(file_path)

        return jsonify({
            "url": f"/uploads/{unique_filename}",
            "original_name": safe_name,
            "size": file_size,
            "success": True
        }), 200

    except Exception as e:
        print(f"File upload error: {e}")
        return jsonify({"error": "Upload failed"}), 500

# --- Socket events ---
@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")

@socketio.on("join")
def handle_join(data):
    try:
        username = bleach.clean(data.get("username", "Anonymous"))
        room = bleach.clean(data.get("room", "default"))
        sid = request.sid

        if not username or not room or len(username) > 20:
            emit("error", {"message": "Invalid username or room"})
            return

        join_room(room)
        user_sessions[sid] = {"username": username, "room": room}
        room_users[room][sid] = username

        now = time.time()
        last = last_disconnect.get(username, 0)
        rejoined = now - last <= 5

        if rejoined:
            emit("message", {"username": "System", "message": "🔄 You reconnected to the chat"})
            msg = f"🔄 {username} reconnected"
        else:
            emit("message", {"username": "System", "message": "✅ You joined the chat"})
            msg = f"✅ {username} joined the chat"
        
        emit("message", {"username": "System", "message": msg}, room=room, include_self=False)

        if username in last_disconnect:
            del last_disconnect[username]

        emit_user_list(room)

    except Exception as e:
        print(f"Join error: {e}")
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
        
        last_disconnect[username] = time.time()
        
        emit("message", {"username": "System", "message": "🚪 You left the chat"})
        emit("message", {"username": "System", "message": f"🚪 {username} left the chat"}, room=room, include_self=False)
        
        emit_user_list(room)

    except Exception as e:
        print(f"Leave error: {e}")

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
        if sid in user_sessions:
            del user_sessions[sid]
        
        last_disconnect[username] = time.time()
        
        emit("message", {"username": "System", "message": f"🚪 {username} disconnected"}, room=room)
        
        emit_user_list(room)

    except Exception as e:
        print(f"Disconnect error: {e}")

def emit_user_list(room):
    """
    Emit non-personalized user list to all users in the room.
    The client will now display the actual username for everyone.
    """
    users = sorted(list(room_users[room].values()))
    
    # Emit the raw, non-personalized list to all SIDs
    for sid, username in room_users[room].items():
        socketio.emit("update_user_list", {
            "users": users,
            "count": len(users)
        }, room=sid)

@socketio.on("message")
def handle_message(data):
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user:
            return

        # Always use the actual username from the session
        username = bleach.clean(user["username"])
        raw_msg = data.get("message", "")
        
        allowed_tags = ['a', 'br', 'img', 'audio']
        allowed_attributes = {
            'a': ['href', 'download', 'target', 'rel', 'class', 'style'],
            'img': ['src', 'style', 'alt'],
            'audio': ['controls', 'style']
        }
        message = bleach.clean(raw_msg, tags=allowed_tags, attributes=allowed_attributes, strip=True)

        if not message.strip():
            return

        # Send the actual username to all clients
        emit("message", {
            "username": username,
            "message": message,
            "timestamp": time.time()
        }, room=user["room"])

    except Exception as e:
        print(f"Message error: {e}")
        emit("error", {"message": "Failed to send message"})

@socketio.on("typing")
def handle_typing(data):
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user:
            return
        
        # Only emit if the user is typing
        if data.get("isTyping"):
            emit("typing", {
                "username": user["username"],
                "timestamp": time.time()
            }, room=user["room"], include_self=False)

    except Exception as e:
        pass

# --- WebRTC signaling ---
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

        active_calls[room] = {
            "caller": data["username"],
            "type": "video" if data.get("video") else "audio",
            "timestamp": time.time()
        }

    except Exception as e:
        print(f"Offer error: {e}")

@socketio.on("answer")
def handle_answer(data):
    try:
        emit("answer", {"answer": data["answer"]}, room=data["room"], include_self=False)
    except Exception as e:
        print(f"Answer error: {e}")

@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    try:
        emit("ice-candidate", {"candidate": data["candidate"]}, room=data["room"], include_self=False)
    except Exception as e:
        print(f"ICE candidate error: {e}")

@socketio.on("reject-call")
def handle_reject_call(data):
    try:
        room = data.get("room")
        emit("call-rejected", {"username": data["username"]}, room=room, include_self=False)
        if room in active_calls:
            del active_calls[room]
    except Exception as e:
        print(f"Reject call error: {e}")

@socketio.on("call-ended")
def handle_call_end(data):
    try:
        room = data.get("room")
        emit("call-ended", {"username": data["username"]}, room=room, include_self=False)
        if room in active_calls:
            del active_calls[room]
    except Exception as e:
        print(f"Call end error: {e}")

# --- Health check ---
@app.route("/health")
def health_check():
    return jsonify({
        "status": "healthy",
        "active_rooms": len(room_users),
        "total_users": sum(len(users) for users in room_users.values()),
        "active_calls": len(active_calls),
        "timestamp": time.time()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    print("🚀 Enhanced Chat Server Starting...")
    print("📍 Server: http://0.0.0.0:5000/")
    print("📊 Health: http://0.0.0.0:5000/health")
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)

