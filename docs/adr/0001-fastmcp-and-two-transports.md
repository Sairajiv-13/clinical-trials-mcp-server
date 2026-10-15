# ADR 0001: FastMCP, with stdio and HTTP transports

Status: Accepted
Date: 2026-10-14

## Context

The server has to plug into two kinds of hosts. Desktop and CLI hosts (for
example Claude Code or a local agent runner) start MCP servers as child
processes and talk over stdio. Hosted setups (a shared internal endpoint, a
container on a VM) need the server reachable over the network instead. The
choice of framework and transports decides how much protocol code this
project owns.

## Decision

Build on FastMCP (Python) and keep the tool layer transport-free:

- Tools are plain async functions decorated with `@mcp.tool`. Nothing in
  `client.py`, `models.py`, or `eligibility.py` imports FastMCP, so the
  whole domain layer is testable without a server.
- `main()` picks the transport at startup: `--transport stdio` (default)
  or `--transport http` for streamable HTTP. The Dockerfile uses HTTP.
- Tool inputs and outputs are pydantic models. FastMCP turns them into the
  JSON schemas hosts validate against, and returns structured content the
  model can read without parsing prose.

## Alternatives considered

Raw MCP protocol over the official low-level SDK. It works, but every tool
needs hand-written schema and dispatch code, and the schemas drift from the
Python types over time. Rejected: this project has four tools and one
upstream API; the protocol plumbing is not where its risk is.

HTTP only, no stdio. Simpler to deploy, but local hosts expect to spawn a
process, and a trial search tool is mostly used from local agent setups.
Rejected on fit, not on effort.

## Consequences

- One codebase serves both host styles; the only transport-specific code
  is the three lines in `main()` that start the server.
- FastMCP is a fast-moving dependency. The domain layer staying
  framework-free is the hedge: if the framework API changes, only
  `server.py` changes with it.
- Stdio mode writes nothing to stdout except protocol messages; logs must
  go to stderr. The server stays silent for this reason.
