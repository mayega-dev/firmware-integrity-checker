FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# System libraries required for PySide6's "xcb" Qt platform plugin
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libegl1 \
    libxkbcommon-x11-0 \
    libxkbcommon0 \
    libfontconfig1 \
    libfreetype6 \
    libx11-xcb1 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxrender1 \
    libxi6 \
    libsm6 \
    libice6 \
    libdbus-1-3 \
    libglib2.0-0 \
    fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 180 --retries 15 -r requirements.txt

COPY . .

CMD ["python3", "main.py"]