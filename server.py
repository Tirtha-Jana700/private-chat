import os
from flask import Flask, render_template, send_from_directory, request
from flask_socketio import SocketIO, join_room, emit
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

socketio = SocketIO(app, async_mode="eventlet")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@socketio.on("join")
def handle_join(data):
    join_room(data["room"])
    emit("private_message", {
        "username": "System",
        "message": f"{data['username']} has joined the room."
    }, room=data["room"])

@socketio.on("private_message")
def handle_message(data):
    emit("private_message", {
        "username": data["username"],
        "message": data["message"]
    }, room=data["room"])

@socketio.on("file_upload")
def handle_file(data):
    file_data = data["file"]
    filename = secure_filename(data["filename"])
    room = data["room"]
    username = data["username"]
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    # Save the file
    with open(filepath, "wb") as f:
        f.write(bytearray(file_data))

    file_url = f"/uploads/{filename}"
    emit("private_message", {
        "username": username,
        "message": f'<a href="{file_url}" target="_blank">📎 {filename}</a>'
    }, room=room)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)


