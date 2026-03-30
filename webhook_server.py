import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sync import state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webhook_server")

app = FastAPI(title="K8sWhisperer Webhook Server")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/slack/actions")
async def slack_actions(request: Request):
    """
    Endpoint to receive interactive callbacks from Slack
    when buttons are clicked.
    """
    form_data = await request.form()
    
    if "payload" not in form_data:
        return JSONResponse(content={"error": "Invalid request"}, status_code=400)
        
    try:
        payload = json.loads(form_data["payload"])
    except Exception as e:
        logger.error(f"Failed to parse payload: {e}")
        return JSONResponse(content={"error": "Failed to parse payload"}, status_code=400)

    # Validate that we have actions
    if "actions" in payload and len(payload["actions"]) > 0:
        action = payload["actions"][0]
        action_id = action.get("action_id")
        
        user_name = payload.get("user", {}).get("username", "Unknown user")
        logger.info(f"Received action '{action_id}' from {user_name}")

        if action_id == "approve_action":
            state.approval_decision = True
            state.approval_event.set()
        elif action_id == "reject_action":
            state.approval_decision = False
            state.approval_event.set()
        else:
            logger.warning(f"Unknown action_id '{action_id}'")

    # Acknowledge the request to Slack
    return JSONResponse(content={"status": "received"})

@app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path_name: str):
    logger.warning(f"⚠️ 404 NOT FOUND: Received {request.method} request to /{path_name}")
    logger.warning("Make sure your Slack Request URL ends EXACTLY with /slack/actions")
    return JSONResponse(content={"error": "Not Found"}, status_code=404)
