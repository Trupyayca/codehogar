from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
import asyncio
import uvicorn
import time
import re  # Para validar el formato del email
import logging

logging.basicConfig(level=logging.DEBUG)

# Configuración de Telegram
API_ID = "27613963"
API_HASH = "ac3495a2287928fba9d6d0b889e4e60b"
BOT_USERNAME = "@CODIGO_HOGAR_BOT"  # Cambia esto por el nombre de usuario del BOT

# Lista de dominios permitidos
ALLOWED_DOMAINS = ["xventas.xyz", "rtjg99.com", "gust11.com", "xposemail.com", "rtjg77.com"]

# Almacenar los últimos envíos (email -> timestamp)
last_sent_messages = {}

# Crear cliente de Telegram
client = TelegramClient("mi_sesion", API_ID, API_HASH)

# Crear instancia de FastAPI
app = FastAPI()

# 🔹 Configurar CORS para permitir solicitudes desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permitir todas las conexiones (cambiar esto si es necesario)
    allow_credentials=True,
    allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permitir todos los headers
)

# Modelo para los comandos enviados desde el frontend
class CommandRequest(BaseModel):
    command: str

@app.on_event("startup")
async def startup():
    await client.start()
    print("✅ Conectado a Telegram.")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

@app.post("/send_command")
async def send_command(request: CommandRequest):
    """
    Envía un comando al BOT y valida el email antes de enviarlo.
    """
    try:
        command_parts = request.command.split(" ")
        if len(command_parts) != 2:
            raise HTTPException(status_code=400, detail="⚠️ Por favor, verifique el formato del correo que ingresó.")

        command_type, email = command_parts

        # 🔹 Validar el formato del email con expresión regular
        email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(email_regex, email):
            raise HTTPException(status_code=400, detail="⚠️ Por favor, verifique el formato del correo que ingresó.")

        email_parts = email.split("@")
        domain = email_parts[1]

        # 🔹 Validar si el dominio está permitido
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(status_code=403, detail="❌ Este correo no pertenece a este sitio web.")

        # 🔹 Evitar envíos seguidos (5 minutos de espera)
        current_time = time.time()
        last_sent = last_sent_messages.get(email)

        if last_sent and (current_time - last_sent["time"] < 300):  # 300 segundos = 5 minutos
            if last_sent["command"] == command_type:
                raise HTTPException(status_code=429, detail="⏳ Ya estamos procesando su petición, no reenvíe muy seguido el código.")

        # Guardar el último envío de este email
        last_sent_messages[email] = {"command": command_type, "time": current_time}

        # 🔹 Enviar el mensaje a Telegram
        await client.send_message(BOT_USERNAME, request.command)

        # Esperar la respuesta del BOT
        for _ in range(10):  # Intentar durante 10 ciclos (~10 segundos)
            async for message in client.iter_messages(BOT_USERNAME, limit=1):
                if message.text and message.text != request.command:  # Evitar devolver el mismo mensaje enviado
                    return {"response": message.text}
            await asyncio.sleep(1)  # Esperar un segundo antes de intentar de nuevo

        raise HTTPException(status_code=500, detail="No se recibió respuesta del BOT en el tiempo esperado.")

    except HTTPException as http_err:
        raise http_err  # Retornar errores personalizados

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")

@app.get("/get_last_messages")
async def get_last_messages():
    """
    Obtiene los últimos 10 mensajes enviados y recibidos en Telegram.
    """
    try:
        messages = []
        async for message in client.iter_messages(BOT_USERNAME, limit=10):
            messages.append({
                "from": "Yo" if message.out else "Bot",
                "text": message.text,
                "date": message.date.strftime("%Y-%m-%d %H:%M:%S")
            })
        return {"messages": messages[::-1]}  # Invertimos la lista para mostrar en orden cronológico

    except Exception as e:
        return {"error": str(e)}

# 🔹 Corrección: Esto debe estar bien indentado para ejecutarse correctamente
if __name__ == "__main__":
    uvicorn.run("bot_backend:app", host="0.0.0.0", port=8000, reload=True)
