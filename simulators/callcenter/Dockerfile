FROM python:3.12-slim

WORKDIR /app

COPY server.py .

ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8101 8102 8103

CMD ["python", "server.py"]
