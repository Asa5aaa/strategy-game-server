from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import sqlite3, os, random, string, time, json
from ai_engine import decide_action

DB = 'game.db'
CODES_FILE = 'codes.json'
QUEUE_FILE = 'queue.json'
FRIEND_FILE = 'friends.json'

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        email TEXT PRIMARY KEY,
        player_id TEXT UNIQUE,
        name TEXT,
        password TEXT,
        wins INTEGER DEFAULT 0,
        losses INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS friend_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_pid TEXT,
        to_pid TEXT,
        status TEXT DEFAULT 'pending',
        ts INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pid TEXT,
        friend_pid TEXT,
        ts INTEGER
    )''')
    conn.commit(); conn.close()

init_db()

app = FastAPI(title='Strategy Game Server - Enhanced Prototype')

def send_email(to_email: str, subject: str, body: str):
    # Send an email using SMTP. Configure SMTP via environment variables:
    # SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
    host = _os.environ.get('SMTP_HOST')
    if not host:
        # SMTP not configured; in preview we do not send email
        return False
    try:
        port = int(_os.environ.get('SMTP_PORT', 587))
        user = _os.environ.get('SMTP_USER')
        password = _os.environ.get('SMTP_PASS')
        from_addr = _os.environ.get('SMTP_FROM', user)
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_email
        msg.set_content(body)
        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print('SMTP send failed:', e)
        return False


class RegisterRequest(BaseModel):
    email: EmailStr

class VerifyRequest(BaseModel):
    email: EmailStr
    code: str
    name: str = None
    password: str = None

class FriendRequest(BaseModel):
    from_player_id: str
    to_player_id: str

class FriendRespond(BaseModel):
    from_player_id: str
    to_player_id: str
    accept: bool

class MatchMakeReq(BaseModel):
    player_id: str

class GameComplete(BaseModel):
    player_id: str
    opponent_id: str
    result: str  # 'win'/'loss'/'draw'

@app.post('/api/register')
def register(req: RegisterRequest):
    code = ''.join(random.choice('0123456789') for _ in range(6))
    data = {}
    if os.path.exists(CODES_FILE):
        data = json.load(open(CODES_FILE))
    data[req.email] = {'code': code, 'ts': int(time.time())}
    json.dump(data, open(CODES_FILE, 'w'))
    # For preview we return the code to the client (in production we email it)
    return {'ok': True, 'message': 'code_sent', 'code_preview': code}

@app.post('/api/verify')
def verify(req: VerifyRequest):
    if not os.path.exists(CODES_FILE):
        raise HTTPException(400, 'no code found')
    data = json.load(open(CODES_FILE))
    rec = data.get(req.email)
    if not rec or rec.get('code') != req.code:
        raise HTTPException(400, 'invalid code')
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT player_id FROM players WHERE email=?', (req.email,))
    row = c.fetchone()
    if row:
        pid = row[0]
    else:
        pid = ''.join(random.choice(string.digits) for _ in range(6))
        c.execute('INSERT INTO players (email, player_id, name, password) VALUES (?,?,?,?)',
                  (req.email, pid, req.name or req.email.split('@')[0], req.password or ''))
        conn.commit()
    conn.close()
    return {'ok': True, 'player_id': pid}

@app.get('/api/player/{player_id}')
def get_player(player_id: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT email, player_id, name, wins, losses FROM players WHERE player_id=?', (player_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, 'not found')
    return {'email': row[0], 'player_id': row[1], 'name': row[2], 'wins': row[3], 'losses': row[4]}

@app.post('/api/friend/request')
def friend_request(req: FriendRequest):
    # check players exist
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT 1 FROM players WHERE player_id=? OR player_id=?', (req.from_player_id, req.to_player_id))
    # we don't strictly require both to exist for preview, but ensure format
    c.execute('INSERT INTO friend_requests (from_pid,to_pid,ts) VALUES (?,?,?)', (req.from_player_id, req.to_player_id, int(time.time())))
    conn.commit(); conn.close()
    return {'ok': True, 'message': 'request_sent'}

@app.post('/api/friend/respond')
def friend_respond(req: FriendRespond):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # find the pending request
    c.execute('SELECT id FROM friend_requests WHERE from_pid=? AND to_pid=? AND status="pending"', (req.from_player_id, req.to_player_id))
    row = c.fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, 'request_not_found')
    req_id = row[0]
    if req.accept:
        # add to friends both ways
        c.execute('INSERT INTO friends (pid,friend_pid,ts) VALUES (?,?,?)', (req.from_player_id, req.to_player_id, int(time.time())))
        c.execute('INSERT INTO friends (pid,friend_pid,ts) VALUES (?,?,?)', (req.to_player_id, req.from_player_id, int(time.time())))
        c.execute('UPDATE friend_requests SET status="accepted" WHERE id=?', (req_id,))
        conn.commit()
        conn.close()
        return {'ok': True, 'message': 'accepted'}
    else:
        c.execute('UPDATE friend_requests SET status="rejected" WHERE id=?', (req_id,))
        conn.commit(); conn.close()
        return {'ok': True, 'message': 'rejected'}

@app.post('/api/matchmaking')
def matchmaking(req: MatchMakeReq):
    # simplistic FIFO queue matching via a file
    queue = []
    if os.path.exists(QUEUE_FILE):
        try:
            queue = json.load(open(QUEUE_FILE))
        except:
            queue = []
    # remove stale entries older than 60s
    now = int(time.time())
    queue = [q for q in queue if now - q.get('ts',0) < 60]
    # if someone waiting, match with them
    if queue:
        opponent = queue.pop(0)
        # save back queue
        json.dump(queue, open(QUEUE_FILE, 'w'))
        # return matched opponent details if exists
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('SELECT email,player_id,name FROM players WHERE player_id=?', (opponent['player_id'],))
        row = c.fetchone()
        conn.close()
        if row:
            return {'status':'matched', 'opponent': {'email':row[0], 'player_id':row[1], 'name':row[2]}}
        else:
            return {'status':'bot'}
    else:
        queue.append({'player_id': req.player_id, 'ts': now})
        json.dump(queue, open(QUEUE_FILE, 'w'))
        # if no opponent within short time, instruct client to play vs bot
        return {'status':'queued'}

@app.post('/api/game/complete')
def game_complete(gc: GameComplete):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # update stats based on result
    if gc.result == 'win':
        c.execute('UPDATE players SET wins = wins + 1 WHERE player_id=?', (gc.player_id,))
    elif gc.result == 'loss':
        c.execute('UPDATE players SET losses = losses + 1 WHERE player_id=?', (gc.player_id,))
    conn.commit()
    conn.close()
    return {'ok': True}

@app.post('/api/simulate/batch')
def simulate_batch(n: int = 10):
    results = {'simulations': []}
    for i in range(n):
        winner = random.choice(['you','enemy','draw'])
        results['simulations'].append({'id': i, 'winner': winner})
    return results


from pydantic import BaseModel
class AIState(BaseModel):
    # flexible state; validation is minimal to allow arbitrary dict
    __root__: dict

@app.post('/api/ai/action')
def ai_action(state: AIState):
    try:
        st = state.__root__
        action = decide_action(st)
        return {"ok": True, "action": action}
    except Exception as e:
        raise HTTPException(500, str(e))
