from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import uvicorn

app = FastAPI()

# فعال‌سازی CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # برای امنیت می‌تونی محدود به GitHub Pages کنی
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🟢 مدل‌ها
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str

class MoveRequest(BaseModel):
    player_id: str
    move: str

class AIState(BaseModel):
    state: dict

# 🟢 روت تست
@app.get("/")
def root():
    print("📡 Root endpoint hit")
    return {"message": "Server is running!"}

# 🟢 ثبت‌نام
@app.post("/api/register")
def register(req: RegisterRequest):
    print("📥 Register request:", req.dict())
    return {"status": "ok", "player_id": req.username}

# 🟢 حرکت بازیکن
@app.post("/api/move")
def move(req: MoveRequest):
    print("📥 Move request:", req.dict())
    return {"status": "ok", "move": req.move}

# 🟢 بازی با AI
@app.post("/api/ai")
def ai_play(req: AIState):
    print("📥 AI request:", req.dict())
    # AI خیلی ساده – همیشه attack_base می‌کنه
    return {"status": "ok", "ai_move": "attack_base"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
