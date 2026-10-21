"""
api1.py - API for designing, editting and structuring the BEM design. Can be used to modify building topology, and add HVAC equipment
"""
from fastapi import FastAPI, 

app = FastAPI(
    title="Pipeline MCP 1 API",
    description="Minimal service layer for building model diagnosis, solution resolution, and autosizing.",
    version="1.0.0"
)
# Endpoints
@app.get("/")
def root():
    return {"status": "online", "service": "API/MCP 1 - Engineering"}

