#!/bin/bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT FastAPI.main:app

