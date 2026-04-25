# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Build/Lint/Test Commands

- Backend tests: `python -m pytest tests/`
- Frontend tests: `npm test` (from bet_dashboard/frontend/)
- Linting: `ruff check .` for Python, `npm run lint` for frontend
- Backend run: `uvicorn main:app --reload --port 8000` (from bet_dashboard/backend/)
- Frontend build: `npm run build` (from bet_dashboard/frontend/)
- Frontend dev: `npm run dev` (from bet_dashboard/frontend/)

## Code Style Guidelines

### Python
- Use type hints for all function parameters and return values
- Follow PEP 8 style guide
- Use f-strings for string formatting
- Use pathlib for file paths
- Import order: standard library, third-party, local
- Use context managers for file operations
- Use 4 spaces for indentation (no tabs)

### TypeScript/React
- Use functional components with hooks
- Use TypeScript for type safety
- Follow Airbnb React/TS style guide
- Use PascalCase for components, camelCase for variables
- Use 2 spaces for indentation
- Use CSS variables for consistent styling (--bg-card, --text-primary, etc.)

### Non-obvious patterns
- Backend uses FastAPI with dependency injection
- Frontend uses Vite with React and TypeScript
- API routes are prefixed with /api
- WebSocket connections use /ws endpoint
- All database operations use context managers
- Environment variables are loaded via os.getenv with defaults
- Frontend uses a proxy to backend at /api
- Profile configurations are loaded from YAML files
- Matches are stored in SQLite databases
- Services run on specific ports (8000 backend, 3002 frontend)
- Ticker services use daemon threads
- Analytics calculations use pandas DataFrames
- Match data is normalized with consensus calculations
- Slips are stored in SQLite with automatic schema migration
- Validation uses web scraping with BeautifulSoup