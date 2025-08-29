const startAndstopBtn = document.getElementById('startAndstopBtn');
const chatLog = document.getElementById('chat-log');
const loadingIndicator = document.getElementById('loading');
const personaSelect = document.getElementById('personaSelect');

let isRecording = false;
let ws = null;
let stream, audioCtx, source, processor;
let manualStop = false;

// Track current assistant bubble for streaming responses
let currentAssistantBubble = null;
let awaitingCity = false;

// Generate or retrieve sessionId
function getSessionId() {
  const params = new URLSearchParams(window.location.search);
  let id = params.get("session");
  if (!id) {
    id = crypto.randomUUID();
    params.set("session", id);
    window.history.replaceState({}, "", `${location.pathname}?${params}`);
  }
  return id;
}
const sessionId = getSessionId();

// ================= Settings UI =================
function injectSettingsUI() {
  const settingsBtn = document.createElement("div");
  settingsBtn.innerHTML = "⚙️";
  settingsBtn.style.position = "fixed";
  settingsBtn.style.top = "15px";
  settingsBtn.style.right = "15px";
  settingsBtn.style.cursor = "pointer";
  settingsBtn.style.fontSize = "20px";
  settingsBtn.style.zIndex = "9999";
  document.body.appendChild(settingsBtn);

  const modal = document.createElement("div");
  modal.innerHTML = `
    <div id="settingsModal" style="
      display:none; position:fixed; top:50%; left:50%;
      transform:translate(-50%, -50%);
      background:#111; color:#fff; padding:20px;
      border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.5);
      z-index:10000; min-width:300px;
    ">
      <h3>🔑 API Settings</h3>
      <label>Gemini API Key *</label>
      <input id="geminiKey" type="text" style="width:100%; margin:5px 0;">
      <label>Murf API Key *</label>
      <input id="murfKey" type="text" style="width:100%; margin:5px 0;">
      <label>ASSEMBLYAI API Key *</label>
      <input id="assemblyaiKey" type="text" style="width:100%; margin:5px 0;">
      <label>OpenWeather API Key</label>
      <input id="weatherKey" type="text" style="width:100%; margin:5px 0;">
      <label>Tavily API Key</label>
      <input id="tavilyKey" type="text" style="width:100%; margin:5px 0;">
      <div style="margin-top:10px; text-align:right;">
        <button id="saveKeysBtn">Save</button>
        <button id="clearKeysBtn">Clear All</button>
        <button id="closeModalBtn">Close</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const modalEl = document.getElementById("settingsModal");

  // Open modal and populate saved keys
  settingsBtn.addEventListener("click", () => {
    modalEl.style.display = "block";
    document.getElementById("geminiKey").value = localStorage.getItem("GEMINI_API_KEY") || "";
    document.getElementById("murfKey").value = localStorage.getItem("MURF_API_KEY") || "";
    document.getElementById("assemblyaiKey").value = localStorage.getItem("ASSEMBLYAI_API_KEY") || "";
    document.getElementById("weatherKey").value = localStorage.getItem("OPENWEATHER_API_KEY") || "";
    document.getElementById("tavilyKey").value = localStorage.getItem("TAVILY_API_KEY") || "";
  });

  document.getElementById("closeModalBtn").addEventListener("click", () => {
    modalEl.style.display = "none";
  });

  // Save keys button
  document.getElementById("saveKeysBtn").addEventListener("click", () => {
    const keys = {
      GEMINI_API_KEY: document.getElementById("geminiKey").value.trim(),
      MURF_API_KEY: document.getElementById("murfKey").value.trim(),
      ASSEMBLYAI_API_KEY: document.getElementById("assemblyaiKey").value.trim(),
      OPENWEATHER_API_KEY: document.getElementById("weatherKey").value.trim(),
      TAVILY_API_KEY: document.getElementById("tavilyKey").value.trim()
    };

    // Mandatory check
    if (!keys.GEMINI_API_KEY || !keys.MURF_API_KEY || !keys.ASSEMBLYAI_API_KEY || !keys.OPENWEATHER_API_KEY || !keys.TAVILY_API_KEY) {
      alert("Please fill in all API keys before saving!");
      return;
    }

    // Save to localStorage
    for (let k in keys) localStorage.setItem(k, keys[k]);

    // Send to backend
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "override_keys", keys }));
      addTextMessage("✅ API keys updated", "info");
    }

    modalEl.style.display = "none";
  });

  // Clear All button
  document.getElementById("clearKeysBtn").addEventListener("click", () => {
    const inputs = ["geminiKey","murfKey","assemblyaiKey","weatherKey","tavilyKey"];
    const keys = {};
    inputs.forEach(id => {
      document.getElementById(id).value = "";
      keys[id.replace("Key","_API_KEY").toUpperCase()] = "";
      localStorage.setItem(id.replace("Key","_API_KEY").toUpperCase(), "");
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "override_keys", keys }));
    }
  });
}
injectSettingsUI();

// ================= Chat + Audio =================
function formatTranscript(text) {
  if (!text) return "";
  text = text.trim();
  text = text.charAt(0).toUpperCase() + text.slice(1);
  if (!/[.?!]$/.test(text)) {
    if (/^(who|what|when|where|why|how)\b/i.test(text)) text += "?";
    else text += ".";
  }
  return text;
}

function addTextMessage(text, type) {
  if (!chatLog) return null;
  const messageDiv = document.createElement('div');
  messageDiv.classList.add('message', type);
  messageDiv.textContent = text;
  chatLog.appendChild(messageDiv);
  chatLog.scrollTo({ top: chatLog.scrollHeight, behavior: "smooth" });
  return messageDiv;
}

function updateBubbleText(bubble, newText) {
  if (!bubble) return;
  bubble.textContent = newText;
  chatLog.scrollTo({ top: chatLog.scrollHeight, behavior: "smooth" });
}

function floatTo16BitPCM(float32Array) {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  let offset = 0;
  for (let i = 0; i < float32Array.length; i++, offset += 2) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function b64toBlob(b64Data, contentType = "", sliceSize = 512) {
  const byteCharacters = atob(b64Data);
  const byteArrays = [];
  for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
    const slice = byteCharacters.slice(offset, offset + sliceSize);
    const byteNumbers = new Array(slice.length);
    for (let i = 0; i < slice.length; i++) byteNumbers[i] = slice.charCodeAt(i);
    byteArrays.push(new Uint8Array(byteNumbers));
  }
  return new Blob(byteArrays, { type: contentType });
}

function playMurfBase64Audio(b64, text = null) {
  if (text) addTextMessage(text, "received");
  try {
    const blob = b64toBlob(b64, "audio/mp3");
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play().catch(() => {
      console.warn("Autoplay blocked. Retrying on user click.");
      document.body.addEventListener("click", () => audio.play(), { once: true });
    });
    audio.onended = () => URL.revokeObjectURL(url);
  } catch (e) {
    console.warn("Audio playback error:", e);
  }
}

// ================= WebSocket =================
function initWebSocket() {
  return new Promise((resolve, reject) => {
    ws = new WebSocket(`wss://ai-voice-agent-p7ct.onrender.com/ws?session=${sessionId}`);


    ws.onopen = () => {
      console.log("✅ WebSocket connected");
      loadingIndicator.style.display = "block";
      ws.send(JSON.stringify({ type: "persona_change", persona: personaSelect.value || "friend" }));

      // Send stored API keys on connect
      const keys = {
        GEMINI_API_KEY: localStorage.getItem("GEMINI_API_KEY") || null,
        MURF_API_KEY: localStorage.getItem("MURF_API_KEY") || null,
        ASSEMBLYAI_API_KEY: localStorage.getItem("ASSEMBLYAI_API_KEY") || null,
        OPENWEATHER_API_KEY: localStorage.getItem("OPENWEATHER_API_KEY") || null,
        TAVILY_API_KEY: localStorage.getItem("TAVILY_API_KEY") || null
      };
      ws.send(JSON.stringify({ type: "override_keys", keys }));

      startAndstopBtn.disabled = false;
      resolve(ws);
    };

    ws.onclose = () => {
      console.log("❌ WebSocket closed, retrying in 3s...");
      loadingIndicator.style.display = "none";
      startAndstopBtn.disabled = false;
      if (!manualStop) setTimeout(initWebSocket, 3000);
    };

    ws.onerror = (err) => {
      console.error("⚠️ WebSocket error", err);
      reject(err);
    };

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } 
      catch { console.error("❌ Invalid WS message", event.data); return; }

      switch (msg.type) {
        case "transcription":
          addTextMessage(formatTranscript(msg.text || ""), "sent");
          currentAssistantBubble = addTextMessage("…", "received");
          break;
        case "llm_chunk":
          if (!currentAssistantBubble) {
            currentAssistantBubble = addTextMessage(msg.text || "", "received");
          } else {
            if (msg.text && msg.text.includes("Could you tell me your city")) {
              updateBubbleText(currentAssistantBubble, msg.text);
              awaitingCity = true;
            } else {
              updateBubbleText(currentAssistantBubble, (currentAssistantBubble.textContent || "") + " " + (msg.text || ""));
            }
          }
          break;
        case "llm_response":
          if (!currentAssistantBubble) addTextMessage(msg.text || "", "received");
          else updateBubbleText(currentAssistantBubble, msg.text || "");
          currentAssistantBubble = null;
          awaitingCity = false;
          break;
        case "murf_audio":
          playMurfBase64Audio(msg.audio, msg.text || null);
          break;
        case "error":
          addTextMessage(`⚠️ ${msg.message}`, "error");
          break;
        case "info":
          addTextMessage(`ℹ️ ${msg.message}`, "info");
          break;
        case "open_url":
          if (msg.url) {
            addTextMessage(`🌐 Click to open: ${msg.url}`, "info");
            const link = document.createElement("a");
            link.href = msg.url;
            link.target = "_blank";
            link.textContent = "👉 Open here";
            chatLog.appendChild(link);
            chatLog.scrollTo({ top: chatLog.scrollHeight, behavior: "smooth" });
          }
          break;
        default:
          console.warn("Unknown WS message type:", msg);
      }
    };
  });
}

// ================= Recording =================
async function startRecording() {
  // Mandatory key check
  const gemini = localStorage.getItem("GEMINI_API_KEY");
  const murf = localStorage.getItem("MURF_API_KEY");
  const assembly = localStorage.getItem("ASSEMBLYAI_API_KEY");
const openWeather = localStorage.getItem("OPENWEATHER_API_KEY");
const tavily = localStorage.getItem("TAVILY_API_KEY");
if (!gemini || !murf || !assembly || !openWeather || !tavily) {
    alert("Please provide all API keys before recording!");
    return;
}


  try {
    await initWebSocket();
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    source = audioCtx.createMediaStreamSource(stream);

    const bufferSize = 4096;
    processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
    source.connect(processor);
    processor.connect(audioCtx.destination);

    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      const pcm16 = floatTo16BitPCM(inputData);
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(pcm16);
      else stopRecording();
    };
  } catch (err) {
    console.error("Mic/WebSocket error:", err);
    alert("Microphone access denied or WebSocket failed.");
  }
}

function stopRecording() {
  manualStop = true;
  try {
    if (processor) { processor.disconnect(); processor.onaudioprocess = null; }
    if (source) source.disconnect();
    if (audioCtx && audioCtx.state !== "closed") audioCtx.close();
    if (stream) stream.getTracks().forEach(track => track.stop());
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  } catch (e) { console.warn("Stop cleanup error:", e); }
  finally {
    loadingIndicator.style.display = "none";
    startAndstopBtn.disabled = false;
  }
}

// Persona change
personaSelect.addEventListener("change", () => {
  const persona = personaSelect.value || "friend";
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "persona_change", persona }));
  }
});

// Start/Stop button
startAndstopBtn.addEventListener("click", async (e) => {
  e.preventDefault();
  if (!isRecording) {
    manualStop = false;
    await startRecording();
    isRecording = true;
    startAndstopBtn.textContent = "Stop Recording";
    startAndstopBtn.classList.add("recording");
  } else {
    stopRecording();
    isRecording = false;
    currentAssistantBubble = null;
    startAndstopBtn.textContent = "Start Recording";
    startAndstopBtn.classList.remove("recording");
  }
});
