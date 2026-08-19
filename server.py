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
MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg',
    'mp3', 'wav', 'ogg', 'oga', 'opus', 'm4a', 'aac', 'flac', 'amr', 'weba', 'webm', 'mka', '3gp',
    'mp4', 'mov', 'avi', 'mkv', 'm4v',
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'zip', 'rar'
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

user_sessions = {}
room_users = defaultdict(dict)
active_calls = defaultdict(dict)

app = Flask(__name__)
app.secret_key = os.urandom(24)
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

def file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

@app.route("/")
def index():
    return send_file("login.html")

@app.route("/chat")
def chat():
    return send_file("chat.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, conditional=True)

@app.route("/upload", methods=["POST"])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "File type not supported"}), 400

        safe_name = secure_filename(file.filename)
        if not safe_name or safe_name.startswith('.'):
            ext = file_extension(file.filename)
            safe_name = f"file.{ext}" if ext else "file"

        unique_filename = f"{str(uuid.uuid4())[:8]}_{safe_name}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        file_url = f"/uploads/{unique_filename}"

        # FIX: Returning simple JSON response. Handled safely on JS socket side to prevent thread locks.
        return jsonify({
            "url": file_url,
            "original_name": safe_name,
            "size": os.path.getsize(file_path),
            "success": True
        }), 200

    except Exception as e:
        print(f"File upload error: {e}")
        return jsonify({"error": "Upload failed"}), 500

def emit_user_list(room):
    if room in room_users:
        users = sorted(list(set(room_users[room].values())))
        socketio.emit("update_user_list", {
            "users": users,
            "count": len(users)
        }, room=room)

@socketio.on("connect")
def handle_connect():
    pass

@socketio.on("join")
def handle_join(data):
    try:
        username = bleach.clean(data.get("username", "Anonymous"))
        room = bleach.clean(data.get("room", "default"))
        sid = request.sid

        join_room(room)
        
        # Clear stale duplicate sessions on reconnect/refresh
        sids_to_remove = [s for s, u in room_users.get(room, {}).items() if u == username]
        for s in sids_to_remove:
            if s != sid:
                del room_users[room][s]
                if s in user_sessions:
                    del user_sessions[s]

        user_sessions[sid] = {"username": username, "room": room}
        room_users[room][sid] = username

        emit("message", {"username": "System", "message": f"✅ {username} joined the chat"}, room=room, include_self=False)
        emit("message", {"username": "System", "message": "✅ You joined the chat"})
        
        emit_user_list(room)

    except Exception as e:
        print(f"Join error: {e}")

@socketio.on("disconnect")
def handle_disconnect():
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user: return

        room = user["room"]
        username = user["username"]
        
        leave_room(room)
        
        if sid in user_sessions: del user_sessions[sid]
        if sid in room_users.get(room, {}): del room_users[room][sid]

        still_in_room = any(u == username for s, u in room_users.get(room, {}).items())
        
        if not still_in_room:
            if room in active_calls and active_calls[room]["caller"] == username:
                socketio.emit("call-ended", {"username": username}, room=room)
                del active_calls[room]

            def broadcast_disconnect(target_room, target_user):
                eventlet.sleep(2.0)
                if not any(u == target_user for s, u in room_users.get(target_room, {}).items()):
                    socketio.emit("message", {"username": "System", "message": f"🚪 {target_user} disconnected"}, room=target_room)
                    emit_user_list(target_room)

            eventlet.spawn(broadcast_disconnect, room, username)
        else:
            emit_user_list(room)

    except Exception as e:
        pass

@socketio.on("message")
def handle_message(data):
    try:
        sid = request.sid
        user = user_sessions.get(sid)
        if not user: return

        username = user["username"]
        raw_msg = data.get("message", "")
        
        message = bleach.clean(raw_msg, tags=['a', 'br', 'img', 'audio'], attributes={'a': ['href', 'download', 'target', 'rel', 'class', 'style'], 'img': ['src', 'style', 'alt'], 'audio': ['controls', 'style']}, strip=True)

        if not message.strip(): return

        emit("message", {"username": username, "message": message}, room=user["room"])
    except Exception as e:
        pass

@socketio.on("offer")
def handle_offer(data):
    try:
        room = data.get("room")
        emit("offer", {"offer": data["offer"], "username": data["username"], "video": data.get("video", False)}, room=room, include_self=False)
        active_calls[room] = {"caller": data["username"], "timestamp": time.time()}
    except Exception: pass

@socketio.on("answer")
def handle_answer(data):
    try: emit("answer", {"answer": data["answer"]}, room=data["room"], include_self=False)
    except Exception: pass

@socketio.on("ice-candidate")
def handle_ice_candidate(data):
    try: emit("ice-candidate", {"candidate": data["candidate"]}, room=data["room"], include_self=False)
    except Exception: pass

@socketio.on("reject-call")
def handle_reject_call(data):
    try:
        room = data.get("room")
        emit("call-rejected", {"username": data["username"]}, room=room, include_self=False)
        if room in active_calls: del active_calls[room]
    except Exception: pass

@socketio.on("call-ended")
def handle_call_end(data):
    try:
        room = data.get("room")
        emit("call-ended", {"username": data["username"]}, room=room, include_self=False)
        if room in active_calls: del active_calls[room]
    except Exception: pass

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
