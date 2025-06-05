# Lex Backend

This component provides the API interface for the Lex legislative platform, enabling search and retrieval of legislation, caselaw, explanatory notes, and amendments from Elasticsearch.

## Architecture Overview

The Lex backend follows a modular architecture based on FastAPI:

1. **API Routers** - Define endpoints for each document type
2. **Search Services** - Handle Elasticsearch queries and transformations
3. **Models** - Define data structures for requests and responses
4. **Core Configuration** - Manage shared services and settings

### Key Components

- **Routers**: Define API endpoints for each document type
- **Search Services**: Handle Elasticsearch queries with text and vector search
- **Models**: Pydantic models for request/response validation
- **Core Config**: Centralized configuration and client management

## Data Flow

```
                    ┌─────────┐          ┌───────────┐          ┌─────────────────┐
                    │         │          │           │          │                 │
API Request ───────► Router   ├──Params──► Search    ├──Query───► Elasticsearch    │
                    │         │          │ Service   │          │                 │
                    └─────────┘          └───────────┘          └────────┬────────┘
                        │                                               │
                        │                                               │
                        │                Response                       │
                    ┌───▼─────┐          ┌───────────┐          ┌───────▼────────┐
                    │         │          │           │          │                 │
JSON Response ◄─────┤ Router  ◄──Models──┤ Models    ◄──Results─┤ Elasticsearch   │
                    │         │          │           │          │                 │
                    └─────────┘          └───────────┘          └─────────────────┘
```

For example, with legislation search processing:

1. An API request arrives at the `/legislation/section/search` endpoint
2. The router validates the request parameters using the `LegislationSectionSearch` model
3. The search service constructs an Elasticsearch query (text or vector-based)
4. Elasticsearch returns matching results
5. The results are transformed into `LegislationSection` models
6. The API returns the models as a JSON response

## API Access and Documentation

### API Endpoints

The Lex backend provides a comprehensive REST API for accessing legal data:

- **Base URL**: `http://localhost:8000`
- **Interactive Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **Alternative Documentation**: `http://localhost:8000/redoc` (ReDoc)
- **MCP Server Endpoint**: `http://localhost:8000/mcp`

#### API Design Choices

The API consistently uses POST requests even for read operations (search, lookup) rather than GET requests. This decision was made for several reasons:

- **Complex Query Parameters**: The search queries often involve complex nested structures that would be unwieldy as URL parameters
- **Request Body Support**: POST requests allow for structured JSON bodies that clearly represent the search parameters
- **API Consistency**: Using POST for all endpoints provides a consistent interface pattern
- **Cleaner API**: Complex filtering, pagination, and search parameters are more clearly organized in a JSON body

#### Legislation Endpoints

- `POST /legislation/section/search` - Search for legislation sections by content
- `POST /legislation/search` - Search for legislation acts by title
- `POST /legislation/lookup` - Look up legislation by type, year, and number
- `POST /legislation/section/lookup` - Get sections for a specific legislation
- `POST /legislation/text` - Get full text of legislation by ID

#### Caselaw Endpoints

- `POST /caselaw/search` - Search for caselaw documents
- `POST /caselaw/section/search` - Search for specific sections within caselaw
- `POST /caselaw/reference/search` - Search for cases that reference specific cases or legislation

#### Explanatory Notes Endpoints

- `POST /explanatory_note/section/search` - Search for explanatory notes
- `POST /explanatory_note/legislation/lookup` - Get explanatory notes for specific legislation
- `POST /explanatory_note/section/lookup` - Get specific explanatory note sections

#### Amendments Endpoints

- `POST /amendment/search` - Search for amendments to legislation
- `POST /amendment/section/search` - Search for amendment sections

## MCP Server Integration

The Lex backend includes built-in support for the Model Context Protocol (MCP), allowing AI assistants and other tools to access legal data through a standardized interface. The MCP server hosts all the FastAPI endpoints.

### MCP Configuration

A sample MCP configuration file is provided in the project root as `mcp_config.json`:

```json
{
  "mcpServers": {
    "lex": {
      "command": "uvx",
      "args": [
        "mcp-proxy",
        "http://localhost:8000/mcp"
      ]
    }
  }
}
```

### Setting Up MCP Client Access

1. **Start the Lex Backend**:
   ```bash
   # Docker (recommended)
   docker compose up -d
   
   # OR local development
   docker-compose up -d elasticsearch
   python src/backend/main.py
   ```

2. **Configure MCP Client**:
   - Copy the `mcp_config.json` file to your MCP client's configuration directory

## Docker Deployment

The backend runs in a Docker container as part of the docker-compose setup. This is the recommended way to run the backend for both development and production.

### Running with Docker

```bash
# Start all services (Elasticsearch, Kibana, Backend, Pipeline)
docker compose up -d

# Start only the backend and its dependencies
docker compose up -d elasticsearch backend

# View backend logs
docker compose logs -f backend

# Stop all services
docker compose down
```

### Docker Configuration

The backend Docker container:
- Runs on port 8000 (mapped from container port 8080)
- Automatically connects to Elasticsearch running in the `elasticsearch` container
- Uses environment variables from `.env` file for configuration
- Includes health checks for monitoring service status

## Development

### Running the Backend

**Docker (Recommended):**
```bash
# Start all services including the backend
docker compose up -d

# View backend logs
docker compose logs -f backend

# Restart just the backend after code changes
docker compose restart backend
```

**Local Development:**
```bash
# Start Elasticsearch dependency
docker-compose up -d elasticsearch

# Run the FastAPI server locally
python src/backend/main.py
```

### API Documentation

When the server is running, API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Module Structure

Each module in the backend follows a consistent structure:

- `router.py` - Defines API endpoints and request handling
- `models.py` - Defines Pydantic models for requests and responses
- `search.py` - Implements search logic and Elasticsearch queries

## Search Capabilities

The backend supports multiple search strategies:

- **Keyword Search**: Traditional text-based search
- **Semantic Search**: Vector-based search using OpenAI embeddings
- **Filtered Search**: Search with additional filters (year, type, etc.)
- **Exact Lookup**: Direct retrieval by identifier

## Core Configuration

The core module provides:

- **Client Management**: Elasticsearch and OpenAI clients
- **Index Configuration**: Names of Elasticsearch indices
- **Logging**: Structured logging with context

## Usage Examples

### Searching for Legislation Sections

```python
import requests

url = "http://localhost:8000/legislation/section/search"

payload = {
    "query": "environmental protection requirements",
    "legislation_category": ["PRIMARY"],
    "year_from": 2020,
    "size": 5
}
response = requests.post(url, json=payload)
results = response.json()
```

### Looking Up Specific Legislation

```python
import requests

url = "http://localhost:8000/legislation/lookup"

payload = {
    "legislation_type": "ukpga",
    "year": 2022,
    "number": 1
}
response = requests.post(url, json=payload)
legislation = response.json()
```

## Extending the API

To add new endpoints or functionality:

1. Add new models to the appropriate `models.py` file
2. Implement search logic in the `search.py` file
3. Add new routes to the `router.py` file
4. Register the router in `main.py` if needed 