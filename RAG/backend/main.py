"""Backend unique du Digital Twin : Customer Advisor (RAG) + Client Simulator + Analyste Qualité.

Lancement (depuis RAG/) :  uvicorn server:app --reload --port 8000
Swagger interactif : http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.settings import CORS_ORIGINS
from backend.core import db
from backend.quality import router as quality_router
from backend.routes import advisor, health, knowledge_base, simulation, workforce, dashboard
from backend.services.advisor import init_agent, quality_reference


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_agent()
    quality_router.set_retriever(quality_reference)
    try:
        db.init_db()  # tables PostgreSQL + vue Power BI
    except Exception as e:  # la base ne doit pas empêcher l'API de démarrer
        print(f"  [db] initialisation impossible : {type(e).__name__}: {str(e)[:200]}")
    yield


app = FastAPI(title="Digital Twin – Customer Advisor API", version="1.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

for r in (advisor.router, simulation.router, knowledge_base.router, health.router, workforce.router, quality_router.router, dashboard.router):
    app.include_router(r)


# format d'erreur commun {code, message} (cf. schéma Error)
@app.exception_handler(HTTPException)
async def _http_err(_: Request, e: HTTPException):
    return JSONResponse({"code": str(e.status_code), "message": str(e.detail)}, status_code=e.status_code)


@app.exception_handler(RequestValidationError)
async def _val_err(_: Request, e: RequestValidationError):
    return JSONResponse({"code": "400", "message": "Requête invalide : " + str(e.errors()[0].get("msg"))}, status_code=400)
