import asyncio
import json
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import random

app = FastAPI()

# Allow frontend from Vite (port 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.player_cards: Dict[str, List[str]] = {}
        self.user_names: Dict[WebSocket, str] = {}
        self.cards_stk_played: List[str] = []
        self.no_of_cards_played: int = None
        self.isgameStarted: bool = False
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            username = self.ws_to_user.pop(websocket, None)
            if username and username in self.users:
                del self.users[username]
            await self.broadcast_users()

    async def register_user(self, websocket: WebSocket, username: str):
        async with self.lock:
            if self.isgameStarted:
                if websocket:
                    payload = {
                    "type": "game started",
                    "message": "Sorry! you cant join now",
                    }
                    msg = json.dumps(payload)
                    await websocket.send_text(msg)
            orig = username
            i = 1
            while username in self.users:
                username = f"{orig}_{i}"
                i += 1
            self.users[username] = None
            self.user_names[websocket] = username
            self.player_cards[username] = []
            await self.broadcast_users()
            return username

    async def shuffle(self):
        async with self.lock:
            def create_deck():
                """Return a standard 52-card deck"""
                suits = ['H', 'D', 'C', 'S']
                ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
                return [f"{rank}-{suit}" for suit in suits for rank in ranks]
            deck1 = create_deck()
            deck2 = create_deck()
            combined_deck = deck1 + deck2  # total 104 cards

            # Step 2: Shuffle the combined deck
            random.shuffle(combined_deck)

            for i in range(11):
                for i in self.player_cards:
                    card = combined_deck.pop()
                    self.player_cards[i].append(card)
            

            username = self.ws_to_user.get(websocket)
            if username:
                self.users[username] += 1
                await self.broadcast_users()

    async def broadcast_users(self,type):
        payload = {
            "type": "users_update",
            "users": self.user_names.values(),
        }
        msg = json.dumps(payload)
        for ws in list(self.active_connections):
            try:
                await ws.send_text(msg)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg["type"] == "join":
                username = msg.get("username", "Anonymous")
                final = await manager.register_user(websocket, username)
                await websocket.send_text(json.dumps({"type": "join_ack", "username": final}))
            elif msg["type"] == "start game":
                await manager.shuffel()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
