from flask import Flask, render_template, request, redirect, send_from_directory, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
import os
import uuid

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/chat")
def chat():
    return app.send_static_file("chat.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    filename = str(uuid.uuid4()) + "_" + file.filename
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)
    return jsonify({"url": f"/uploads/{filename}"})

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@socketio.on("join")
def on_join(data):
    socketio.emit("private_message", {
        "username": "System",
        "message": f"{data['username']} joined the room"
    }, room=data["room"])
    socketio.enter_room(request.sid, data["room"])

@socketio.on("private_message")
def handle_message(data):
    socketio.emit("private_message", data, room=data["room"])

@socketio.on("typing")
def handle_typing(data):
    socketio.emit("typing", {"username": data["username"]}, room=data["room"])

if __name__ == "__main__":
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host="0.0.0.0", port=5000)





