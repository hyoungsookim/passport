# Passport

Passport is a centralized identity and tenant management service that provides authentication, personal identity management, tenant administration, and user membership management for multiple enterprise SaaS applications.

## Run the API

Prerequisites: Python 3.15 or later and uv. Run these commands from the repository root.

Install the project and its locked dependencies:

```sh
uv sync --project apps/api --locked
```

Start the API server:

```sh
uv run --project apps/api api
```

For development with automatic reload:

```sh
uv run --project apps/api uvicorn passport.main:app --reload --reload-dir apps/api/passport
```

- API: <http://127.0.0.1:8000>
- API documentation: <http://127.0.0.1:8000/docs>
- OpenAPI specification: <http://127.0.0.1:8000/openapi.json>

Stop the server with `Ctrl+C`. See [the API README](apps/api/README.md) for build instructions.

## Type checking

Run ty from the repository root:

```sh
uv run --project apps/api ty check --project apps/api
```

The root `ty.toml` configures `apps/api/.venv` as the Python environment and `apps/api` as the source root, so ty can resolve API dependencies when the repository root is open in an editor.
