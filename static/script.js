document.addEventListener("DOMContentLoaded", () => {
  const socket = io();

  // Ask for username or generate default
  let username = prompt("Enter your username:") || "User_" + Math.floor(Math.random() * 1000);
  username = username.trim();
  const room = "default";

  // Elements
  const chatMessages = document.getElementById("chat-messages");
  const messageInput = document.getElementById("message-input");
  const sendBtn = document.getElementById("send-btn");
  const usersList = document.getElementById("users-list");
  const onlineCount = document.getElementById("online-count");
  const toggleUsersBtn = document.getElementById("toggle-users-btn");
  
  const popup = document.getElementById("call-popup");
  const fullscreenBtn = document.getElementById("fullscreen-btn");
  const videoBtn = document.getElementById("video-btn");
  const endCallBtn = document.getElementById("end-call-btn");

  // Join Room
  socket.emit("join", { username, room });

  // Toggle Online Users List
  toggleUsersBtn.addEventListener("click", () => {
    usersList.classList.toggle("hidden");
    const arrow = document.getElementById("user-list-arrow");
    if (usersList.classList.contains("hidden")) {
      arrow.className = "fa-solid fa-chevron-down";
    } else {
      arrow.className = "fa-solid fa-chevron-up";
    }
  });

  // Render Incoming Messages
  socket.on("message", (data) => {
    const msgDiv = document.createElement("div");

    if (data.username === "System") {
      msgDiv.className = "system-message";
      
      // Select appropriate icon based on system text content
      let iconClass = "fa-solid fa-circle-info";
      if (data.message.includes("reconnected")) iconClass = "fa-solid fa-arrows-rotate";
      else if (data.message.includes("joined")) iconClass = "fa-solid fa-circle-check";
      else if (data.message.includes("left") || data.message.includes("disconnected")) iconClass = "fa-solid fa-right-from-bracket";
      
      msgDiv.innerHTML = `<i class="${iconClass}"></i><span>${data.message}</span>`;
    } else {
      const isSelf = data.username === username;
      msgDiv.className = `user-message ${isSelf ? "self" : "other"}`;
      msgDiv.innerHTML = `
        <span class="username">${isSelf ? "You" : data.username}</span>
        <span class="text">${data.message}</span>
      `;
    }

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });

  // Update Online User Badges
  socket.on("update_user_list", (data) => {
    onlineCount.innerText = data.count;
    usersList.innerHTML = "";
    data.users.forEach((u) => {
      const badge = document.createElement("span");
      badge.className = `user-badge ${u === username ? "active" : ""}`;
      badge.innerText = u;
      usersList.appendChild(badge);
    });
  });

  // Message Delivery
  function sendMessage() {
    const text = messageInput.value.trim();
    if (text) {
      socket.emit("message", { message: text });
      messageInput.value = "";
    }
  }

  sendBtn.addEventListener("click", sendMessage);
  messageInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") sendMessage();
  });

  // --- Dragging Functionality for Call Pop-up ---
  let isDragging = false;
  let isFullscreen = false;
  let currentX, currentY, initialX, initialY;
  let xOffset = 0, yOffset = 0;

  popup.addEventListener("pointerdown", dragStart);
  document.addEventListener("pointermove", drag);
  document.addEventListener("pointerup", dragEnd);

  function dragStart(e) {
    if (isFullscreen || e.target.closest("button")) return;
    initialX = e.clientX - xOffset;
    initialY = e.clientY - yOffset;
    isDragging = true;
  }

  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      xOffset = currentX;
      yOffset = currentY;
      popup.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
    }
  }

  function dragEnd() {
    isDragging = false;
  }

  // --- Fullscreen Toggle Logic (Resets Inline Position) ---
  fullscreenBtn.addEventListener("click", () => {
    isFullscreen = !isFullscreen;

    if (isFullscreen) {
      // Clear drag offset values so CSS fullscreen rule applies
      popup.style.top = "";
      popup.style.left = "";
      popup.style.transform = "";

      popup.classList.add("fullscreen-mode");
      fullscreenBtn.innerHTML = `<i class="fa-solid fa-compress"></i>`;
    } else {
      popup.classList.remove("fullscreen-mode");
      
      // Re-apply pre-fullscreen drag coordinates
      popup.style.transform = `translate3d(${xOffset}px, ${yOffset}px, 0)`;
      fullscreenBtn.innerHTML = `<i class="fa-solid fa-expand"></i>`;
    }
  });

  // Toggle Video Call Container Display
  videoBtn.addEventListener("click", () => {
    popup.classList.add("active");
  });

  endCallBtn.addEventListener("click", () => {
    popup.classList.remove("active");
  });
});
