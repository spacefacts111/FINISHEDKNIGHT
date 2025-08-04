FROM python:3.10-slim

RUN apt-get update && apt-get install -y curl unzip libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxdamage1 libxrandr2 libgbm1 libxshmfence1 libasound2 libxcomposite1 libxfixes3 libxrender1 libxext6 libx11-xcb1 libgtk-3-0 libx11-dev libxss1 libxinerama1 libgl1 libu2f-udev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps

COPY . /app
WORKDIR /app

CMD ["python3", "main.py"]
