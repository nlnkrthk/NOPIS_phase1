<!-- 299. Package them into a project or team plugin. -->
# Approved MCP Configuration & Specifications (C12)

This directory defines the approved Model Context Protocol (MCP) server configuration and security boundaries for NOPIS network intelligence.

## 1. Overview

The NOPIS MCP server exposes curated telecom network operations capabilities to Claude and AI agents as a **strict thin wrapper** over existing FastAPI endpoints.

* **Server Implementation**: `.claude/mcp_server.py`
* **Transport**: stdio (standard input/output, default for Claude Code)
* **Underlying Service**: NOPIS FastAPI service (`http://127.0.0.1:8000`)

---

## 2. Approved Tool Catalog

| Tool Name | Underlying API Endpoint | Description |
| --------- | ----------------------- | ----------- |
| `network_summary` | `GET /network/summary` | Overall network metrics across Milan grids for an hourly timestamp window |
| `grid_activity` | `GET /network/grid/{grid_id}` | Time-series activity measures for a specific grid cell |
| `hotspots` | `GET /network/hotspots` | Grids exhibiting top activity measures up to a given limit |
| `pipeline_status` | `GET /network/pipeline/status` | Operational status of the Spark batch pipeline and warehouse freshness |
| `grid_location` | Gap-report tool (GeoJSON lookup) | Geographic coordinates for a grid cell |
| `nearby_hotspots` | Gap-report tool (Spatial radius) | Spatial query for neighboring cells within a specified radius |

---

## 3. Strict Security Boundaries

All tools and configurations must maintain the engineering safeguards established in C12:

1. **Read-Only (HTTP GET Exclusively)**: Tools perform HTTP GET requests only. There are no POST, PUT, DELETE, or PATCH mutations.
2. **Zero Direct Database Access**: No `SQLAlchemy`, no `SessionLocal`, and no database connection drivers are imported or executed by MCP.
3. **No SQL Syntax**: The server contains no SQL query strings or table manipulation logic.
4. **No Secret Ingestion**: The MCP server never loads `.env` files. Secrets such as `DB_PASSWORD` or `ANTHROPIC_API_KEY` are never accessed or returned.
5. **Zero Duplicate Business Logic**: The server does not compute anomaly scores, execute risk ranking, or apply alert thresholds. Existing APIs remain the sole source of truth.
6. **No Congestion Claims**: The server and its documentation preserve the rule that high activity does not equal confirmed congestion.
