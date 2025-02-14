#!/bin/bash
# gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT FastAPI.main:app
uvicorn FastAPI.main:app --host 0.0.0.0 --port 8000


