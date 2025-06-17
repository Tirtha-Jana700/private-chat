from flask import Flask, send_file, send_from_directory, request
from flask_socketio import SocketIO, join_room, emit
from flask_cors import CORS
import os
import base64

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
    join_room(room)
    emit("message", {
        "username": "System",
        "message": f"✅ {username} joined the chat."
    }, room=room)

# Handle text messages
@socketio.on("message")
def handle_message(data):
    username = data.get("username", "Anonymous")
    room = data.get("room", "default")
    message = data.get("message", "")
    emit("message", {
        "username": username,
        "message": message
    }, room=room)

# Handle typing status
@socketio.on("typing")
def handle_typing(data):
    username = data.get("username", "Someone")
    room = data.get("room", "default")
    emit("typing", { "username": username }, room=room)

# Handle file upload
@socketio.on("file")
def handle_file(data):
    username = data.get("username", "Anonymous")
    room = data.get("room", "default")
    file_name = data.get("fileName", "file")
    file_data = data.get("data", "")

    # Decode base64 data and save to disk
    if ";base64," in file_data:
        file_content = file_data.split(";base64,")[1]
        extension = file_name.split('.')[-1]
        safe_name = f"{username}_{str(abs(hash(file_data)))}.{extension}"
        file_path = os.path.join(UPLOAD_FOLDER, safe_name)

        with open(file_path, "wb") as f:
            f.write(base64.b64decode(file_content))

        emit("message", {
            "username": username,
            "file": f"/uploads/{safe_name}",
            "fileName": file_name
        }, room=room)

# Run the app
if __name__ == "__main__":
    print("🚀 Server running at http://127.0.0.1:5000/")
    socketio.run(app, host="0.0.0.0", port=5000)


