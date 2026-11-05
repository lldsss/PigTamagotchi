FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    DEMO_MODE=false \
    DATABASE_PATH=/app/data/pigs.sqlite3

WORKDIR /app
COPY pyproject.toml main.py ./
COPY src/ ./src/
COPY web/ ./web/
# Editable-установка сохраняет путь к web/ относительно исходного кода.
RUN python -m pip install --no-cache-dir -e .

EXPOSE 8080
CMD ["python", "-m", "pig_tamagotchi"]
