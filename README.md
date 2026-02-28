# 🎙️ AI Voice Conversational Agent

A Real-Time AI-Powered Voice Assistant built using **FastAPI, AssemblyAI, Google Gemini, and Murf AI**.

This system enables natural voice conversations by converting speech to text, generating intelligent responses, and converting them back into realistic AI speech with session-based memory.

---

## 📌 Project Overview

AI Voice Conversational Agent is a backend-driven voice assistant designed to:

- Convert user speech into text
- Generate intelligent AI responses
- Convert AI text responses into natural voice
- Maintain session-based conversation memory
- Provide a modern interactive frontend UI

---

## 🏗️ Architecture

```
User Voice → Frontend UI → FastAPI Backend
                        ↓
                 AssemblyAI (Speech-to-Text)
                        ↓
                 Google Gemini (AI Response)
                        ↓
                 Murf AI (Text-to-Speech)
                        ↓
                Audio Response to User
```

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Async Client:** httpx
- **Frontend:** HTML, CSS, JavaScript
- **Speech-to-Text:** AssemblyAI
- **AI Engine:** Google Gemini
- **Text-to-Speech:** Murf AI
- **Configuration:** pydantic, python-dotenv
- **Logging:** Python logging module

---

## 📦 Features

### ✅ Speech-to-Text
- Accurate audio transcription
- Async processing
- Handles uploaded audio files

### ✅ AI Response Generation
- Context-aware replies
- Session-based memory
- Structured JSON responses

### ✅ Text-to-Speech
- Natural voice synthesis
- Multiple voice selection support
- Returns playable audio URL

### ✅ Session Management
- Unique `session_id` per user
- Conversation history tracking
- Isolated memory per session

### ✅ Modern UI
- Dark / Light theme toggle
- Animated aura orb
- Live waveform visualization
- Interactive chat interface

---

## 📡 API Endpoints

### `GET /`

Serves the frontend UI.

---

### `POST /agent/chat/{session_id}`

Handles:

- Speech-to-Text
- AI response generation
- Text-to-Speech

#### Path Parameter

- `session_id` – Unique ID for conversation tracking

#### Form Data

- `file` – Audio file (required)
- `voice_id` – Murf voice ID (optional, default: `en-US-natalie`)

#### Sample Response

```json
{
  "audio_url": "https://murf.ai/output/xyz123.mp3",
  "user_text": "Hello there!",
  "ai_text": "Hi! How can I assist you today?"
}
```

---

## 🗂️ Project Structure

```
ai-voice-agent/
│
├── main.py
├── services/
│   ├── assemblyai_service.py
│   ├── gemini_service.py
│   └── murf_service.py
│
├── static/
│   └── index.html
│
├── .env
├── requirements.txt
└── README.md
```

---

## ⚙️ Configuration

Application uses environment-based configuration.

Create a `.env` file in the project root:

```
MURF_API_KEY=your_murf_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

---

## 🚀 Running Locally

### 1️⃣ Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-voice-agent.git
cd ai-voice-agent
```

### 2️⃣ Create Virtual Environment

```bash
python -m venv venv
```

Activate:

Mac/Linux:
```bash
source venv/bin/activate
```

Windows:
```bash
venv\Scripts\activate
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Run Application

```bash
uvicorn main:app --reload
```

Server runs at:

```
http://127.0.0.1:8000
```

---

## 🔄 Usage Flow

1. User records voice in browser
2. Audio is sent to `/agent/chat/{session_id}`
3. Backend transcribes speech
4. AI generates contextual response
5. Response is converted to speech
6. Frontend plays AI voice output

---

## 🔒 Security Highlights

- API keys stored securely via environment variables
- Async request handling
- Session isolation
- Structured logging

---

## 📈 Future Improvements

- Real-time streaming responses
- Multi-language support
- Database-backed conversation storage
- Docker support
- CI/CD pipeline
- Swagger documentation

---

## 👨‍💻 Author

**Kolli Jayanth Eswar**

AI & Backend Developer | FastAPI | Intelligent Systems

---

## 📜 License

This project is licensed under the MIT License.
