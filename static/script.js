document.addEventListener("DOMContentLoaded", () => {
  feather.replace();

  const socket = io();
  const username = prompt("Enter your username:") || "User_" + Math.floor(Math.random() * 1000);
  const room = "default";

  const popup = document.getElementById('call-popup');
  const fullscreenBtn = document.getElementById('fullscreen-btn');
  const themeToggle = document.getElementById('theme-toggle');
  const chatMessages = document.getElementById('chat-messages');

  let isFullscreen = false;
  let isDragging = false;
  let currentX, currentY, initialX, initialY;
  let xOffset = 0, yOffset = 0;

  // --- Theme Mode Switcher ---
  themeToggle.addEventListener('click', () => {
    document.body.classList.toggle('light-mode');
    document.body.classList.toggle('dark-mode');
    const isLight = document.body.classList.contains('light-mode');
    document.getElementById('theme-icon').setAttribute('data-feather', isLight ? 'moon' : 'sun');
    feather.replace();
  });

  // --- Socket Logic ---
  socket.emit('join', { username, room });

  socket.on('message', (data) => {
    const msgDiv = document.createElement('div');
    
    if (data.type === 'system') {
      msgDiv.className = 'system-message';
      msgDiv.innerHTML = `<i data-feather="${data.icon || 'info'}"></i> <span>${data.message}</span>`;
    } else {
      const isSelf = data.username === username;
      msgDiv.className = `user-message ${isSelf ? 'self' : 'other'}`;
      msgDiv.innerHTML = `<strong>${isSelf ? 'You' : data.username}</strong><span>${data.message}</span>`;
    }

    chatMessages.appendChild(msgDiv);
    feather.replace();
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });

  socket.on('update_user_list', (data) => {
    document.getElementById('online-count').innerText = data.count;
    const usersList = document.getElementById('users-list');
    usersList.innerHTML = '';
    data.users.forEach(u => {
      const span = document.createElement('span');
      span.className = `user-badge ${u === username ? 'active' : ''}`;
      span.innerText = u;
      usersList.appendChild(span);
    });
  });

  // --- Message Sending ---
  document.getElementById('send-btn').addEventListener('click', sendMessage);
  document.getElementById('message-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  function sendMessage() {
    const input = document.getElementById('message-input');
    if (input.value.trim()) {
      socket.emit('message', { message: input.value });
      input.value = '';
    }
  }

  // --- Draggable Call Overlay ---
  popup.addEventListener('pointerdown', dragStart);
  document.addEventListener('pointermove', drag);
  document.addEventListener('pointerup', dragEnd);

  function dragStart(e) {
    if (isFullscreen || e.target.closest('button')) return;
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

  // --- Fixed Fullscreen Toggle ---
  fullscreenBtn.addEventListener('click', () => {
    isFullscreen = !isFullscreen;

    if (isFullscreen) {
      // Clear inline drag styling overrides
      popup.style.top = '';
      popup.style.left = '';
      popup.style.transform = '';

      popup.classList.add('fullscreen-mode');
      document.getElementById('fs-icon').setAttribute('data-feather', 'minimize-2');
    } else {
      popup.classList.remove('fullscreen-mode');
      popup.style.transform = `translate3d(${xOffset}px, ${yOffset}px, 0)`;
      document.getElementById('fs-icon').setAttribute('data-feather', 'maximize-2');
    }
    feather.replace();
  });

  // Call trigger button
  document.getElementById('video-btn').addEventListener('click', () => {
    popup.classList.add('active');
  });

  document.getElementById('end-call-btn').addEventListener('click', () => {
    popup.classList.remove('active');
  });
});
