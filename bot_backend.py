from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
import asyncio
import time
import re
import logging

logging.basicConfig(level=logging.DEBUG)

API_ID = 27613963
API_HASH = 'ac3495a2287928fba9d6d0b889e4e60b'
BOT_USERNAME = '@CODIGO_HOGAR_BOT'

ALLOWED_DOMAINS = ["xventas.xyz", "rtjg99.com", "gust11.com", "xposemail.com", "rtjg77.com"]
last_sent_messages = {}

# 🧠 Dos clientes separados
client = TelegramClient("mi_sesion", API_ID, API_HASH)
client_reader = TelegramClient("mi_sesion_lectura", API_ID, API_HASH)

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
    await client.start()
    await client_reader.start()
    print("✅ Clientes conectados a Telegram.")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()
    await client_reader.disconnect()

@app.post("/send_command")
async def send_command(request: CommandRequest):
    try:
        command_parts = request.command.split(" ")
        if len(command_parts) != 2:
            raise HTTPException(status_code=400, detail="⚠️ Formato inválido.")

        command_type, email = command_parts
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, email):
            raise HTTPException(status_code=400, detail="⚠️ Formato de correo incorrecto.")

        domain = email.split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(status_code=403, detail="❌ Dominio no permitido.")

        current_time = time.time()
        last_sent = last_sent_messages.get(email)

        if last_sent and (current_time - last_sent["time"] < 300):
            if last_sent["command"] == command_type:
                raise HTTPException(status_code=429, detail="⏳ Ya estamos procesando su petición.")

        last_sent_messages[email] = {"command": command_type, "time": current_time}

        # 💡 Asegurar conexión antes de enviar
        if not client.is_connected():
            await client.connect()
        if not await client.is_user_authorized():
            raise HTTPException(status_code=500, detail="❌ Cliente no autorizado.")

        await client.send_message(BOT_USERNAME, request.command)

        for _ in range(10):
            async for message in client.iter_messages(BOT_USERNAME, limit=1):
                if message.text and message.text != request.command:
                    return {"response": message.text}
            await asyncio.sleep(1)

        raise HTTPException(status_code=500, detail="No se recibió respuesta del BOT.")

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")

@app.get("/get_last_messages")
async def get_last_messages():
    try:
        # 🧠 Usar el cliente lector
        if not client_reader.is_connected():
            await client_reader.connect()

        messages = []
        async for message in client_reader.iter_messages(BOT_USERNAME, limit=10):
            messages.append({
                "from": "Yo" if message.out else "Bot",
                "text": message.text,
                "date": message.date.strftime("%Y-%m-%d %H:%M:%S")
            })
        return {"messages": messages}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot_backend:app", host="0.0.0.0", port=8000, reload=True)
