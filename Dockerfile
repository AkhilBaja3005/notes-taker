FROM python:3.12-slim

# Create a non-root user with UID 1000 (standard for Hugging Face Spaces & security)
RUN useradd -m -u 1000 user

WORKDIR /home/user/app

# Install system dependencies & ffmpeg for audio downsampling
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

# Set permissions for non-root runtime
RUN mkdir -p incoming_audio lectures vector_db && \
    chown -R user:user /home/user/app

USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Hugging Face Spaces listens on port 7860
EXPOSE 7860

CMD ["python", "main.py"]
