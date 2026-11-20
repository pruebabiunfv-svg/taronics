FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CALIBPRO_ENV=production
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 tatronics
COPY --chown=tatronics:tatronics . .
RUN mkdir -p /app/instance && chown -R tatronics:tatronics /app/instance
USER tatronics
EXPOSE 8000
# Railway inyecta PORT en ejecución. El shell expande su valor y exec conserva
# las señales para que Gunicorn cierre limpiamente en los despliegues.
# Un worker reduce la competencia durante la migración inicial de SQLite.
CMD ["sh", "-c", "exec gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT:-8000} run:app"]
