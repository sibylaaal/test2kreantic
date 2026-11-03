from fastapi import FastAPI

app = FastAPI(title="Notification Service", version="0.1.0")


@app.get("/")
def root() -> dict:
    return {"service": "notification", "message": "Notification service is ready"}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "notification"}
