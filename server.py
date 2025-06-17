import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, join_room, emit
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Allow CORS for all domains
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

@app.route("/")
def index():
    return render_template("index.html")

from flask import send_from_directory

@app.route("/")
def serve_index():
    return send_from_directory("public", "index.html")

@app.route("/chat.html")
def serve_chat():
    return send_from_directory("public", "chat.html")

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    path = os.path.join("static/uploads", file.filename)
    file.save(path)
    return { "url": f"/static/uploads/{file.filename}" }

@app.route("/static/uploads/<filename>")
def serve_file(filename):
    return send_from_directory("static/uploads", filename)

@socketio.on("join")
def handle_join(data):
    join_room(data["room"])
    emit("private_message", {
        "username": "System",
        "message": f"{data['username']} has joined the room."
    }, room=data["room"])

# server.py
@socketio.on("private_message")
def handle_private_message(data):
    room = data["room"]
    emit("private_message", data, room=room)

@socketio.on("typing")
def handle_typing(data):
    emit("typing", {"username": data["username"]}, room=data["room"], include_self=False)

if __name__ == "__main__":
    import os
    import eventlet
    eventlet.monkey_patch()
    port = int(os.environ.get("PORT", 5000))  # Use Render's port or default to 5000
    socketio.run(app, host="0.0.0.0", port=port)





