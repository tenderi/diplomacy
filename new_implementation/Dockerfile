FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY new_implementation/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the code
COPY new_implementation /app/new_implementation
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

# Copy start script
COPY new_implementation/start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8000

ENTRYPOINT ["/app/start.sh"] 