
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
import asyncio
import time
import re
import logging

API_ID = 27613963
API_HASH = 'ac3495a2287928fba9d6d0b889e4e60b'
BOT_USERNAME = '@CODIGO_HOGAR_BOT'
SESSION_NAME = "mi_sesion"
ALLOWED_DOMAINS = ["xventas.xyz", "rtjg99.com", "gust11.com", "xposemail.com", "rtjg77.com"]

cache_mensajes = {}
CACHE_TTL = 15 * 60  # 15 minutos

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommandRequest(BaseModel):
    command: str

@app.on_event("startup")
async def startup():
    await client.connect()
    if not await client.is_user_authorized():
        raise Exception("❌ Cliente de Telegram no autorizado.")
    print("✅ Cliente conectado a Telegram.")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

@app.post("/send_command")
async def send_command(request: CommandRequest):
    try:
        command_parts = request.command.strip().split(" ")
        if len(command_parts) != 2:
            raise HTTPException(status_code=400, detail="⚠️ Formato inválido.")

        command_type, email = command_parts
        if command_type.lower() != "/code":
            raise HTTPException(status_code=400, detail="⚠️ Solo se permite el comando /code.")

        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, email):
            raise HTTPException(status_code=400, detail="⚠️ Formato de correo incorrecto.")

        domain = email.split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(status_code=403, detail="❌ Dominio no permitido.")

        now = time.time()
        expired = [k for k, v in cache_mensajes.items() if now - v["timestamp"] > CACHE_TTL]
        for k in expired:
            del cache_mensajes[k]

        if email in cache_mensajes:
            return {"response": cache_mensajes[email]["response"]}

        if not client.is_connected():
            await client.connect()

        full_command = f"/code {email}"
        await client.send_message(BOT_USERNAME, full_command)

        for _ in range(10):
            async for message in client.iter_messages(BOT_USERNAME, limit=1):
                if message.text and message.text != full_command:
                    response = message.text
                    cache_mensajes[email] = {
                        "response": response,
                        "timestamp": time.time()
                    }
                    return {"response": response}
            await asyncio.sleep(1)

        raise HTTPException(status_code=500, detail="❌ No se recibió respuesta del BOT.")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"❌ Error inesperado: {str(e)}")

@app.get("/get_last_messages")
async def get_last_messages():
    try:
        mensajes = []
        for email, data in cache_mensajes.items():
            mensajes.append({
                "from": "Bot",
                "text": data["response"],
                "date": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(data["timestamp"]))
            })
        mensajes = sorted(mensajes, key=lambda x: x["date"], reverse=True)
        return {"messages": mensajes}
    except Exception as e:
        return {"error": str(e)}
