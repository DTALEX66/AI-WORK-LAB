from mcp_gateway import McpGateway, McpServerDecl


def _gw():
    g = McpGateway()
    g.register(McpServerDecl(name="fs", transport="stdio", tools=["read", "write"]))
    g.register(McpServerDecl(name="web", transport="http", tools=["search"], approval_required=True))
    return g


def test_register_and_list():
    g = _gw()
    assert len(g.list_servers()) == 2
    assert g.list_servers()[0]["name"] == "fs"


def test_known_tool_allowed():
    g = _gw()
    assert g.evaluate(server="fs", tool="read").allowed


def test_unknown_server_rejected():
    g = _gw()
    assert not g.evaluate(server="nope", tool="read").allowed


def test_undeclared_tool_rejected():
    g = _gw()
    assert not g.evaluate(server="fs", tool="exec").allowed


def test_approval_required():
    g = _gw()
    d = g.evaluate(server="web", tool="search")
    assert not d.allowed
    assert d.approval_required


def test_default_gateway_empty():
    from mcp_gateway import default_gateway
    assert len(default_gateway().list_servers()) == 0
