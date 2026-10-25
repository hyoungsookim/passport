"""Command-line entry point for the API server."""

import uvicorn


def main() -> None:
    uvicorn.run("passport.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
