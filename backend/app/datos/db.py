"""Conexión a la base de datos con SQLAlchemy.

En local se usa SQLite (``sqlite:///./maestro.db``); en producción, PostgreSQL
en Neon mediante el controlador ``psycopg``. La URL sale de ``DATABASE_URL``.
Aquí vivirán el motor, la fábrica de sesiones y las tablas (sesiones anónimas,
contadores de mensajes y, eventualmente, el banco de ejercicios).
"""
