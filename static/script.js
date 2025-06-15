const socket = io();
let room = "";
let username = "";

function joinRoom() {
  username = document.getElementById("username").value;
  room = document.getElementById("room").value;

  if (!username || !room) return alert("Enter name and room ID");

  document.getElementById("login").style.display = "none";
  document.getElementById("chat").style.display = "block";
  document.getElementById("room-name").innerText = "Room: " + room;

  socket.emit("join", { username, room });
}

document.getElementById("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const msg = document.getElementById("message").value;
  socket.emit("private_message", { username, room, message: msg });
  document.getElementById("message").value = "";
});

socket.on("private_message", (data) => {
  const div = document.createElement("div");
  div.innerHTML = `<b>${data.username}</b>: ${data.message}`;
  document.getElementById("messages").appendChild(div);
});
