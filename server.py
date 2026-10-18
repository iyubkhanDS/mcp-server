import hashlib
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
import json

app = FastAPI()

NORMALIZED_EMAIL = "25ds3000107@ds.study.iitm.ac.in"

@app.get("/sse")
async def sse_endpoint(request: Request):
    """MCP SSE endpoint for establishing transport connection."""
    async def event_generator():
        # Inform the client where to post messages
        yield f"event: endpoint\ndata: /messages\n\n"
        while True:
            if await request.is_disconnected():
                break
            # Keep-alive ping
            yield ": ping\n\n"
            import asyncio
            await asyncio.sleep(15)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/messages")
async def mcp_messages(request: Request):
    """Handles JSON-RPC messages for the MCP protocol."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})

    method = body.get("method")
    msg_id = body.get("id")
    params = body.get("params", {})

    # 1. Initialize Handshake
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "iitm-mcp-exam-server",
                    "version": "1.0.0"
                }
            },
            "id": msg_id
        })

    # 2. Initialized Notification
    elif method == "notifications/initialized":
        return Response(status_code=200)

    # 3. List Tools
    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "solve_challenge",
                        "description": "Solves the dynamic exam challenge and returns the required cryptographic hash.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            },
            "id": msg_id
        })

    # 4. Call Tool
    elif method == "tools/call":
        tool_name = params.get("name")
        if tool_name == "solve_challenge":
            # Read X-Exam-Challenge from incoming request headers
            challenge = request.headers.get("x-exam-challenge", "")
            
            # Compute required hash: SHA-256("${challenge}:${normalizedEmail}")[:16]
            raw_data = f"{challenge}:{NORMALIZED_EMAIL}"
            computed_hash = hashlib.sha256(raw_data.encode("utf-8")).hexdigest()[:16]

            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": computed_hash
                        }
                    ],
                    "isError": False
                },
                "id": msg_id
            })
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                "id": msg_id
            })

    return JSONResponse({
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Method not found: {method}"},
        "id": msg_id
    })

# Also handle root post/get for generic MCP transports
@app.post("/")
async def mcp_root_post(request: Request):
    return await mcp_messages(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)