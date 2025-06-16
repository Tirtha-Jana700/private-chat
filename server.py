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

if __name__ == "__main__":
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host="0.0.0.0", port=5000)



