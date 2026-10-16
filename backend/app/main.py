"""Punto de entrada de la API de MAEstro.

Crea la aplicación FastAPI, configura CORS para el frontend y registra los routers.
Correr con: ``uvicorn app.main:app --reload``.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import obtener_configuracion
from app.datos import db
from app.rutas import chat, salud, sesiones

config = obtener_configuracion()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Al arrancar: conecta la base de datos y crea las tablas que falten."""
    db.configurar()
    yield


app = FastAPI(
    title="MAEstro",
    description="Tutor de IA que guía con pistas para las pruebas de admisión de la UCR, la UNA y el TEC.",
    version="0.1.0",
    lifespan=ciclo_de_vida,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.origenes_permitidos,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    # El frontend lee cuántos mensajes le quedan al estudiante hoy.
    expose_headers=["X-Mensajes-Restantes"],
)

app.include_router(salud.router)
app.include_router(sesiones.router)
app.include_router(chat.router)
