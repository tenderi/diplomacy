FROM python:3.11-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc libcairo2 libcairo2-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code
COPY . /app/
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Copy start script
COPY ./start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8000

ENV PYTHONPATH=/app/src

ENTRYPOINT ["/app/start.sh"] 