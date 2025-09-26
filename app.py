from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import uvicorn

app = FastAPI()

# ✅ فعال‌سازی CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # می‌تونی بجای * آدرس GitHub Pages بذاری
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# 📌 مدل‌ها
# ---------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str

class MoveRequest(BaseModel):
    player_id: str
    move: str

class AIState(BaseModel):
    state: dict  # RootModel توی Pydantic v2 تغییر کرده، اینجوری درست کار می‌کنه

# ---------------------------
# 📌 تست ساده (برای اطمینان)
# ---------------------------
@app.get("/")
def root():
    return {"message": "Server is running!"}

# ---------------------------
# 📌 API ثبت‌نام
# ---------------------------
@app.post("/api/register")
def register(req: RegisterRequest):
    # اینجا میشه دیتابیس واقعی زد، الان فقط تستیه
    return {"status": "ok", "player_id": req.username}

# ---------------------------
# 📌 API حرکت (مثال بازی)
# ---------------------------
@app.post("/api/move")
def move(req: MoveRequest):
    # حرکت رو برمی‌گردونیم (برای تست)
    return {"status": "ok", "move": req.move}

# ---------------------------
# 📌 API بازی با AI
# ---------------------------
@app.post("/api/ai")
def ai_play(req: AIState):
    # یه پاسخ خیلی ساده از AI
    return {"status": "ok", "ai_move": "attack_base"}

# ---------------------------
# 📌 اجرای لوکال
# ---------------------------
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
