"""ASGI application entry point."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="Passport API", version="0.1.0")


app = create_app()
