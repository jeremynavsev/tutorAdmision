"""Rutas de ejercicios.

Por ahora devuelve una lista fija. Más adelante leerá ``ejercicios/banco.json``
(o la base de datos) y nunca expondrá la solución ni los pasos.
"""

from fastapi import APIRouter

from app.esquemas import EjercicioPublico

router = APIRouter(prefix="/api", tags=["ejercicios"])

_EJERCICIOS_DE_EJEMPLO = [
    EjercicioPublico(
        id="mat-001",
        tema="Ecuaciones lineales",
        area="Matemática",
        enunciado="Si 3x + 5 = 20, ¿cuál es el valor de x?",
        opciones=["3", "5", "15", "25/3"],
    ),
    EjercicioPublico(
        id="raz-001",
        tema="Sucesiones",
        area="Razonamiento",
        enunciado="¿Qué número sigue en la sucesión 2, 6, 12, 20, 30, …?",
        opciones=["36", "40", "42", "48"],
    ),
]


@router.get("/ejercicios", response_model=list[EjercicioPublico])
def listar_ejercicios() -> list[EjercicioPublico]:
    """Lista de ejercicios disponibles (datos de ejemplo)."""
    return _EJERCICIOS_DE_EJEMPLO
