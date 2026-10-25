# Passport API



## Goals

Implement a unified Identity & Tenant Management Platform for enterprise SaaS services.

Passport aims to provide secure and consistent authentication, user identity, account, and tenant management that can be shared across enterprise SaaS services.

This allows users to access multiple SaaS services with a single identity and enterprises to manage users and tenants centrally. It also allows each SaaS service to focus on its own business functionality without duplicating authentication and common user management features.


## Technology Stack

Language: Python 3.15.1
Dependency and Virtual environment management: uv
Type Checker: ty
Lint: ruff

Framework: FastAPI[standard] >= 0.162 
ASGI: Uvicorn[standard] >= 0.54 
ORM: SQLAlchemy[asyncio] >= 2.1.6
Background Job: Celery >= 5.6.3

Database Migration: Alembic >= 1.20
Database Driver: Psycopg[binary,pool] >= 3.3.6
Database: PostgreSQL 18
Cache: Valkey

Unit test: pytest, pytest-asyncio
Coverage: pytest-cov

Passport must be delivered as a single package that automatically performs a basic installation of the application and supporting software, such as PostgreSQL and Valkey, when customers install the package. It must therefore avoid complex installation procedures and excessive infrastructure requirements.



## Coding Guidelines

1. Think Before Coding

Do not make assumptions without checking them. Do not hide uncertainty. Make tradeoffs explicit.

Before implementing:

- State your assumptions explicitly. Ask if you are unsure.
- If multiple interpretations are possible, present them. Do not arbitrarily choose one and proceed.
- If there is a simpler approach, say so. Push back when warranted.
- If something is unclear, stop. Explain what is confusing and ask for clarification.

2. Simplicity First

Write the minimum code needed to solve the problem. Include nothing unnecessary.

- Do not add features that were not requested.
- Do not create abstractions for code used only once.
- Do not add "flexibility" or "configurability" that was not requested.
- Do not add error handling for situations that cannot occur.
- If you write 200 lines that could be reduced to 50, rewrite them.

Ask yourself: "Would a senior engineer consider this overly complex?" If so, simplify it.

3. Surgical Changes

Change only what is necessary. Clean up only issues introduced by your changes.

When modifying existing code:

- Do not "improve" unrelated code, comments, or formatting.
- Do not refactor code that works correctly.
- Follow the existing style, even if you prefer your own.
- If you find unrelated dead code, mention it without deleting it.

When your changes leave orphaned code:

- Remove imports, variables, and functions that become unused because of your changes.
- Do not remove pre-existing dead code unless the user requests it.

Validation criterion: Every changed line must be directly traceable to the user's request.

4. Write Pythonic Code

- Follow PEP 8 for Python code.
- Use comprehensions whenever code can be expressed as a comprehension.
- Use conditional expressions whenever applicable.
- Write idiomatic Python code.
- After completing an implementation, write tests and ensure that all tests pass, with no errors or warnings from ruff or ty.


## Requirements

Refer to docs/REQUIREMENTS.md for the core functional requirements.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
