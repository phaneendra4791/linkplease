from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.core.logging import setup_logging
from app.api import rules, webhook, stats

setup_logging()

app = FastAPI(
    title="LinkPlease Tech Intern Backend",
    description="Reliable Instagram Comment-to-DM Automation System",
    version="1.0.0"
)

# Register routers
app.include_router(rules.router)
app.include_router(webhook.router)
app.include_router(stats.router)

@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.get("/healthz")
async def health_check():
    return {"status": "ok"}
