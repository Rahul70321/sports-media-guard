FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements or directly install for MVP
COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn opencv-python-headless imagehash Pillow beautifulsoup4 requests sqlalchemy python-dotenv boto3

COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
