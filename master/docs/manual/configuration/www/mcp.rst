.. _Config-WWW-MCP:

MCP Server
==========

Buildbot can expose a built-in `Model Context Protocol <https://modelcontextprotocol.io/>`_
(MCP) server. MCP is an open standard that lets AI assistants and LLM-powered
agents discover and call capabilities offered by external systems. With the MCP
server enabled, such a client can query build status, inspect and search build
logs, and trigger or stop builds, using the same data and permissions as the
rest of the web interface.

Enabling
--------

The MCP server is part of the web server and is disabled by default. Enable it
with the ``mcp`` key of the ``www`` configuration dictionary:

.. code-block:: python

    c['www'] = {
        'port': 8010,
        'mcp': True,
    }

When enabled, the server is reachable at the ``/mcp`` path of the web server
(for example ``http://localhost:8010/mcp``). It speaks MCP over the Streamable
HTTP transport: clients send JSON-RPC messages with HTTP ``POST`` requests.

Connecting a client
-------------------

Any MCP-compatible client (for example an AI assistant integrated into an editor
or IDE) connects by being pointed at the server's ``/mcp`` URL using the
Streamable HTTP transport. Most clients are configured through a JSON block that
registers named servers, of the form:

.. code-block:: json

    {
      "mcpServers": {
        "buildbot": {
          "type": "http",
          "url": "http://localhost:8010/mcp"
        }
      }
    }

Replace the URL with the address of your Buildbot web server. On startup the
client performs the MCP ``initialize`` handshake, discovers the available tools,
and makes them available to the model. The exact location of this configuration
-- a project file, a user-level file, or a command-line registration -- depends
on the client; consult its documentation for where to add an HTTP MCP server.

If the web server requires authentication (see below), the client must be able
to authenticate to it.

Authentication and authorization
--------------------------------

The MCP endpoint lives inside the web server and therefore inherits whatever
authentication is configured with the ``auth`` key (see :ref:`Web-Authentication`).
It is exactly as secure as the rest of the web interface: with the default
``NoAuth`` it is open, and with an authentication plugin configured it requires
the same login.

Authorization is enforced for the write tools (``force_build`` and
``cancel_build``) using the same endpoint matchers as the REST API. A client
may only force or stop a build if the authenticated user holds a role permitted
by the configured ``ForceBuildEndpointMatcher`` / ``StopBuildEndpointMatcher``
rules; otherwise the call returns an error result.

As with the other streaming web APIs, the ``Origin`` header is validated against
the configured ``allowed_origins`` to guard against DNS-rebinding.

Tools
-----

The server exposes the following tools. Every tool that returns a list is
bounded (default 25 items, capped at 100) and reports ``total_count`` and
``has_more`` so that a single call cannot overrun a client's context window.

.. list-table::
    :header-rows: 1
    :widths: 20 15 65

    * - Tool
      - Access
      - Description
    * - ``get_status``
      - read
      - Overall snapshot: number of builders, worker connectivity and the builds currently running.
    * - ``get_builders``
      - read
      - List configured builders (id, name, description, tags).
    * - ``get_workers``
      - read
      - List workers, showing whether each is connected and/or paused.
    * - ``get_recent_builds``
      - read
      - Recent builds, most recent first; optionally restricted to a builder or to running builds only.
    * - ``get_build``
      - read
      - A single build by id, including its steps and result.
    * - ``get_build_logs``
      - read
      - List a build's logs, fetch a log's contents (paginated by line), or search it with an optional regular expression.
    * - ``force_build``
      - write
      - Trigger a build by invoking a force scheduler.
    * - ``cancel_build``
      - write
      - Stop a running build by its build id.

.. note::

    Live streaming of in-progress build logs is not yet available; the
    ``get_build_logs`` tool operates on stored log contents. Bearer-token
    authentication for headless clients is also planned for a future release.
