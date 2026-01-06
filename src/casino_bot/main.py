from fastapi import FastAPI

app = FastAPI(
    title="Casino Bot (Non-Gambling, UK Legal-by-Design)",
    version="0.1.0",
)

@app.get("/health")
def healthcheck():
    return {"status": "ok"}
