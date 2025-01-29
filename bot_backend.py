from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
import asyncio
import uvicorn

# Configuración de Telegram
API_ID = "27613963"
API_HASH = "ac3495a2287928fba9d6d0b889e4e60b"
BOT_USERNAME = "@CODIGO_HOGAR_BOT"  # Cambia esto por el nombre de usuario del BOT

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
    print("Conectado a Telegram.")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

@app.post("/send_command")
async def send_command(request: CommandRequest):
    """
    Envía un comando al BOT y espera la respuesta.
    """
    try:
        # Enviar el comando al BOT
        await client.send_message(BOT_USERNAME, request.command)

        # Esperar la respuesta del BOT
        for _ in range(10):  # Intentar durante 10 ciclos (~10 segundos)
            async for message in client.iter_messages(BOT_USERNAME, limit=1):
                if message.text and message.text != request.command:  # Evitar devolver el mismo mensaje enviado
                    return {"response": message.text}
            await asyncio.sleep(1)  # Esperar un segundo antes de intentar de nuevo

        raise HTTPException(status_code=500, detail="No se recibió respuesta del BOT en el tiempo esperado.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# 🔹 Esto estaba mal indentado. Ahora está correctamente afuera de la función send_command
if __name__ == "__main__":
    uvicorn.run("bot_backend:app", host="0.0.0.0", port=8000, reload=True)
