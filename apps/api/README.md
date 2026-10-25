# Passport API

Run these commands from `apps/api`.

Install the project and its locked dependencies:

```sh
uv sync --locked
```

Start the API server at `http://127.0.0.1:8000`:

```sh
uv run api
```

For development with automatic reload:

```sh
uv run uvicorn passport.main:app --reload
```

The OpenAPI UI is available at `http://127.0.0.1:8000/docs`.

Build the source distribution and wheel:

```sh
uv build
```
