from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
import asyncio
import time
import re
import random  # Para generar un ID único para cada mensaje

API_ID = 27613963
API_HASH = 'ac3495a2287928fba9d6d0b889e4e60b'
BOT_USERNAME = '@CODIGO_HOGAR_BOT'
import os

SESSION_NAME = os.getenv("SESSION_NAME", "mi_sesion_render")
ALLOWED_DOMAINS = ["xventas.xyz", "rtjg99.com", "gust11.com", "xposemail.com", "rtjg77.com", "lordpose.com"]

cache_mensajes = {}
CACHE_TTL = 15 * 60  # 15 minutos

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

origins = [
    "https://netcodes.online",
    "https://www.netcodes.online"
]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

def shorten_url(url: str) -> str:
    """Acorta una URL (simulado). En la práctica, usarías un servicio externo."""
    if len(url) > 20:
        return url[:20] + "..."
    return url

@app.post("/send_command")
async def send_command(request: CommandRequest):
    try {
        command_parts = request.command.strip().split(" ")
        if len(command_parts) != 2:
            raise HTTPException(status_code=400, detail="⚠️ Formato inválido.")

        command_type, email = command_parts
        if command_type.lower() not in ["/code", "/hogar"]:
            raise HTTPException(status_code=400, detail="⚠️ Comando inválido. Usa /code o /hogar.")

        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, email):
            raise HTTPException(status_code=400, detail="⚠️ Formato de correo incorrecto.")

        domain = email.split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(status_code=403, detail="❌ Dominio no permitido.")

        cache_key = f"{command_type.lower()}|{email}"
        now = time.time()
        expired = [k for k, v in cache_mensajes.items() if now - v["timestamp"] > CACHE_TTL]
        for k in expired:
            del cache_mensajes[k]

        if cache_key in cache_mensajes:
            return {"messages": [cache_mensajes[cache_key]["message"]]}  # Devuelve solo el mensaje

        if not client.is_connected():
            await client.connect()

        full_command = f"{command_type} {email}"
        await client.send_message(BOT_USERNAME, full_command)

        for _ in range(10):
            async for message in client.iter_messages(BOT_USERNAME, limit=1):
                if message.text and message.text != full_command:
                    response_text = message.text
                    shortened_url = None
                    url_match = re.search(r'https?://[^\s]+', response_text)
                    if url_match:
                        url = url_match.group(0)
                        shortened_url = shorten_url(url)
                        response_text = response_text.replace(url, "")  # Remove the full URL from the text

                    response = {
                        "command": full_command,
                        "email": email,
                        "time": time.strftime('%H:%M:%S', time.localtime(time.time())),
                        "response_text": response_text.strip(),
                        "full_url": url if url_match else None,
                        "shortened_url": shortened_url,
                        "is_error": "⛔️ No hay mensajes" in response_text
                    }
                    cache_mensajes[cache_key] = {"message": response, "timestamp": time.time()}  # Cache the message
                    return {"messages": [response]}  # Return as a list of messages
            await asyncio.sleep(1)

        error_response = {
            "command": full_command,
            "email": email,
            "time": time.strftime('%H:%M:%S', time.localtime(time.time())),
            "response_text": "⛔️ No se recibió respuesta del BOT.",
            "full_url": None,
            "shortened_url": None,
            "is_error": True
        }
        cache_mensajes[cache_key] = {"message": error_response, "timestamp": time.time()}  # Cache the error
        raise HTTPException(status_code=500, detail="❌ No se recibió respuesta del BOT.")

    except HTTPException as e:
        error_response = {
            "command": request.command,
            "email": email if 'email' in locals() else '',
            "time": time.strftime('%H:%M:%S', time.localtime(time.time())),
            "response_text": f"❌ {e.detail}",
            "full_url": None,
            "shortened_url": None,
            "is_error": True
        }
        cache_mensajes[cache_key] = {"message": error_response, "timestamp": time.time()}  # Cache the error
        raise
    except Exception as e:
        error_response = {
            "command": request.command,
            "email": '',
            "time": time.strftime('%H:%M:%S', time.localtime(time.time())),
            "response_text": f"❌ Error inesperado: {str(e)}",
            "full_url": None,
            "shortened_url": None,
            "is_error": True
        }
        cache_mensajes[cache_key] = {"message": error_response, "timestamp": time.time()}  # Cache the error
        raise HTTPException(status_code=500, detail=f"❌ Error inesperado: {str(e)}")

@app.get("/get_last_messages")
async def get_last_messages():
    try:
        now = time.time()
        valid_messages = []
        for k, v in cache_mensajes.items():
            if now - v["timestamp"] <= CACHE_TTL:
                valid_messages.append(v["message"])

        valid_messages.sort(key=lambda x: x["time"], reverse=True)  # Ordenar por hora
        return {"messages": valid_messages}
    except Exception as e:
        return {"error": str(e)}
