# Contributing to Lex

Thanks for contributing! This guide covers the essentials for getting started.

## Quick Setup

1. **Clone and setup:**
   ```bash
   git clone https://github.com/i-dot-ai/lex.git
   cd lex
   uv sync
   ```

2. **Start services:**
   ```bash
   docker compose up -d
   ```

3. **Load test data (optional):**
   ```bash
   make ingest-all-sample      # Load sample data (recommended for testing)
   # or for specific types:
   make ingest-legislation-sample
   make ingest-caselaw-sample
   ```

## Development

### Code Style
- Use `ruff format` and `ruff check` before committing
- Line length: 100 characters
- Follow PEP 8 conventions

### Testing
```bash
uv run pytest                    # Run all tests
uv run pytest --cov            # With coverage
```

### Branch Naming
- `feature/description`
- `fix/description`
- `docs/description`

## Pull Requests

1. Create a feature branch from `main`
2. Make your changes and test them
3. Ensure code passes `ruff check` and tests pass
4. Submit PR with clear description

## Issues

Use the appropriate template:
- **Bug Report**: For bugs with reproduction steps
- **Feature Request**: For new features
- **Documentation**: For doc improvements
- **Question**: For general questions

## Getting Help

- Check the [README](README.md) and component docs
- Search existing issues
- Create a new issue with the "Question" template

Thanks for contributing! 