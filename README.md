# Mise AI Booking Assistant

A demo AI agent for the Mise service marketplace. Lets users search venues, browse services, check real-time staff availability, and create bookings using natural language.

Built with LangChain + Claude (Anthropic) + PostgreSQL. Exposes three interfaces: a Streamlit web UI, a CLI, and an MCP server for Claude Desktop / Claude Code.

## Architecture

```
User → Natural language query
     → LLM intent recognition (Claude claude-sonnet-4-6)
     → Tool calls (parameterized SQL against PostgreSQL)
     → Real DB results injected as context
     → Grounded LLM response
```

**Tools available to the agent:**
- `search_premises` — find venues by category (tattoo, barber, massage, salon, dental, spa)
- `search_services` — browse services and pricing at a venue
- `check_availability` — query real staff schedules and existing bookings
- `get_premise_details` — full venue info, staff list, and reviews
- `create_booking` — create an appointment

## Prerequisites

- Python 3.11+
- PostgreSQL with the Mise database schema and seed data
- An Anthropic API key

## Setup

**1. Clone and install dependencies**

```bash
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://mise:mise@localhost:5432/mise
ANTHROPIC_API_KEY=your-api-key-here
```

**3. Ensure the database is running** with the Mise schema and seed data loaded. The agent connects to the PostgreSQL instance defined in `DATABASE_URL`.

## Running the Demo

### Option 1 — Streamlit Web UI (recommended)

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Chat with the assistant in the browser. The sidebar shows live tool call logs.

### Option 2 — CLI

```bash
python main.py
```

Interactive terminal session with coloured output via `rich`. Type `quit` or `exit` to stop.

### Option 3 — MCP Server

Exposes the booking tools via the Model Context Protocol so any MCP-compatible client (Claude Desktop, Claude Code) can use them.

**stdio mode** (for Claude Desktop):

```bash
python mcp_server.py
```

**HTTP mode** (for networked clients):

```bash
python mcp_server.py --http
```

To connect from Claude Desktop, add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mise": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

To connect from Claude Code:

```bash
claude mcp add mise python /absolute/path/to/mcp_server.py
```

## Project Structure

```
mise-ai/
├── app.py            # Streamlit web UI
├── main.py           # CLI entry point
├── mcp_server.py     # MCP server (stdio or HTTP)
├── config.py         # Env var loading
├── requirements.txt
├── agent/
│   ├── core.py       # LangChain agent setup
│   ├── tools.py      # Tool definitions (LangChain wrappers)
│   └── prompts.py    # System prompt
├── db/
│   ├── connection.py # SQLAlchemy engine / session
│   ├── models.py     # ORM models (mirrors mise-api schema)
│   └── queries.py    # Parameterized query functions
└── utils/
    └── scheduling.py # Availability computation logic
```

## Example Queries

```
Find me a barber in the city
What massage services does Serenity Spa offer?
Is there a tattoo artist available this Saturday afternoon?
Book a haircut with John at 2pm on Friday
```
