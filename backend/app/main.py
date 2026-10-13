"""Punto de entrada de la API de MAEstro.

Crea la aplicación FastAPI, configura CORS para el frontend y registra los routers.
Correr con: ``uvicorn app.main:app --reload``.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtener_configuracion
from app.rutas import chat, ejercicios, salud, sesiones

config = obtener_configuracion()

app = FastAPI(
    title="MAEstro",
    description="Tutor de IA que guía con pistas para las pruebas de admisión de la UCR, la UNA y el TEC.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.origenes_permitidos,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(salud.router)
app.include_router(ejercicios.router)
app.include_router(sesiones.router)
app.include_router(chat.router)
