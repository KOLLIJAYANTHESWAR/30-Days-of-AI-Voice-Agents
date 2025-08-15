🎙️ AI Voice Conversational Agent (FastAPI):
An advanced real-time AI-powered voice assistant that transcribes your speech, generates intelligent and context-aware responses using Google Gemini, and speaks back to you with natural-sounding voices using Murf AI. Built with FastAPI, it supports session-based conversations, multiple voice selections, and a modern, interactive UI.

✨ Features:
--> Speech-to-Text – Accurate transcription using AssemblyAI.
--> AI Response Generation – Context-aware replies from Google Gemini.
--> Text-to-Speech – Lifelike voice synthesis via Murf AI.
--> Session-based Conversation Memory – Maintains dialogue history per user.
--> Modern UI – Dark/Light theme toggle, animated aura orb, live waveform visualization.
--> Fast & Async – Built on FastAPI with async calls for low latency.
--> Modular Design – Easily replace APIs or extend features.

🏗 Architecture:
🎤 User Speech
      ↓
[Frontend UI]
      ↓ (audio file)
[FastAPI Backend]
      ↓
AssemblyAI (Speech-to-Text)
      ↓
Google Gemini (AI Chat Generation)
      ↓
Murf AI (Text-to-Speech)
      ↓ (audio URL)
[Frontend UI - Plays AI Voice Response]


🏗 Architecture Diagram:
           ┌──────────────────────────┐
           │        User Device        │
           │   (Browser Frontend UI)   │
           └───────────┬──────────────┘
                       │ Audio (file)
                       ▼
          ┌────────────────────────────┐
          │        FastAPI Backend      │
          │   (app.py / main.py)        │
          └───────┬───────────┬────────┘
                  │           │
                  ▼           ▼
       ┌────────────────┐  ┌─────────────────┐
       │  AssemblyAI     │  │ Google Gemini   │
       │ (Speech-to-Text)│  │ (AI Response)   │
       └───────┬─────────┘  └──────────┬─────┘
               │                        │
               ▼                        │
       ┌────────────────────────────────┘
       │
       ▼
  ┌───────────────┐
  │   Murf AI      │
  │ (Text-to-Speech│
  └───────┬────────┘
          │ Audio URL
          ▼
   ┌───────────────────────┐
   │ Browser Plays Response │
   └───────────────────────┘


🛠 Tech Stack:
Backend: FastAPI, Python 3.11+
Frontend: HTML, CSS, JavaScript
APIs: AssemblyAI, Google Gemini, Murf AI
Tools & Libraries:
httpx – Async HTTP requests
pydantic & pydantic-settings – Config validation
python-dotenv – Environment variable management
logging – Structured logging


📦 Installation:
1️⃣ Clone the Repository:
git clone https://github.com/your-username/ai-voice-agent.git
cd ai-voice-agent

2️⃣ Create & Activate Virtual Environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Set Up Environment Variables
Create a .env file in the root directory:

MURF_API_KEY=your_murf_api_key
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
GEMINI_API_KEY=your_gemini_api_key

5️⃣ Run the Backend
uvicorn main:app --reload

Backend will be available at:
➡ http://127.0.0.1:8000

📡 API Endpoints
GET /
Serves the frontend UI (static/index.html).
POST /agent/chat/{session_id}
Handles speech-to-text, AI generation, and text-to-speech.

Request:
Path Parameter: session_id – unique ID for each conversation.

Form Data:
file – Audio file (required)

voice_id – Murf AI voice ID (optional, default "en-US-natalie")
Response (JSON):
{
  "audio_url": "https://murf.ai/output/xyz123.mp3",
  "user_text": "Hello there!",
  "ai_text": "Hi! How can I assist you today?"
}

🎯 Usage Flow:
User records voice → Frontend sends to /agent/chat/{session_id}.
Backend transcribes via AssemblyAI.
Google Gemini generates AI response.
Murf AI turns text into audio.
Frontend plays AI’s voice response.

📌 Example .env Configuration:
MURF_API_KEY=xxxxxxxxxxxxxxxxxxxx
ASSEMBLYAI_API_KEY=xxxxxxxxxxxxxxxxxxxx
GEMINI_API_KEY=xxxxxxxxxxxxxxxxxxxx

🔮 Future Enhancements:
🎧 Real-time streaming transcription & response
🌍 Multi-language support
🗂 Save conversation history to a database
📱 Mobile-friendly PWA version

🤝 Contributing:
Fork this repository
Create your feature branch (git checkout -b feature/my-feature)
Commit changes (git commit -m 'Add my feature')
Push to branch (git push origin feature/my-feature)
Create Pull Request

📜 License:
MIT License – free to use and modify.