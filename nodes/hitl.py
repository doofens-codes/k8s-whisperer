import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from state import ClusterState
from sync import state as sync_state


def hitl_node(state: ClusterState) -> dict:
    plan = state.get("plan", {})
    anomaly = state["anomalies"][0] if state["anomalies"] else {}
    
    anomaly_type = anomaly.get('type', 'Unknown Anomaly')
    affected_resource = anomaly.get('affected_resource', 'Unknown Resource')
    diagnosis = state.get('diagnosis', 'N/A')
    action = plan.get('action', 'N/A')
    target = plan.get('target', 'N/A')
    blast_radius = plan.get('blast_radius', 'N/A')
    confidence = plan.get('confidence', 'N/A')

    print("\n" + "="*60)
    print("HUMAN APPROVAL REQUIRED (Forwarded to Slack)")
    print("="*60)
    print(f"Anomaly   : {anomaly_type} on {affected_resource}")
    print(f"Diagnosis : {diagnosis}")
    print(f"Action    : {action}")
    print(f"Target    : {target}")
    
    # 1. Reset synchronization state
    sync_state.reset()
    
    # 2. Build Slack Block Kit
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    slack_channel = os.environ.get("SLACK_CHANNEL", "#k8s-alerts")
    hitl_timeout = int(os.environ.get("HITL_TIMEOUT_SECONDS", "300"))
    
    if not slack_token:
        print("[HITL] ERROR: SLACK_BOT_TOKEN is missing. Reverting to terminal Fallback.")
        decision = input("Approve action? (y/n): ").strip().lower()
        return {"approved": decision == "y"}
        
    client = WebClient(token=slack_token)
    
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 K8sWhisperer: Human Approval Required",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Anomaly:*\n{anomaly_type}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Resource:*\n{affected_resource}"
                }
            ]
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Diagnosis:*\n{diagnosis}"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Action:*\n{action} on {target}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Blast Radius:*\n{blast_radius} (Confidence: {confidence})"
                }
            ]
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": "approved",
                    "action_id": "approve_action"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Reject",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": "rejected",
                    "action_id": "reject_action"
                }
            ]
        }
    ]
    
    try:
        # 3. Send message to Slack
        response = client.chat_postMessage(
            channel=slack_channel,
            text="🚨 K8sWhisperer: Human Approval Required", # Fallback text
            blocks=blocks
        )
        print(f"[HITL] Slack message posted to {slack_channel}. Waiting up to {hitl_timeout}s for response...")
        
        # 4. Wait for action
        event_set = sync_state.approval_event.wait(timeout=hitl_timeout)
        
        # We can update the message here to remove the buttons once a decision was made
        if event_set:
            status_text = "✅ *Approved*" if sync_state.approval_decision else "❌ *Rejected*"
        else:
            status_text = "⏳ *Timed out*"
            
        blocks[-1] = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Decision: {status_text}"
            }
        }
        
        client.chat_update(
            channel=response["channel"],
            ts=response["ts"],
            text="🚨 K8sWhisperer: Approval Processed",
            blocks=blocks
        )
            
        if event_set:
            approved = sync_state.approval_decision
            if approved:
                print("[HITL] Remote Approved. Executing...")
            else:
                print("[HITL] Remote Rejected. Skipping execution.")
            return {"approved": approved}
        else:
            print("[HITL] Timeout reached. Treating as Reject.")
            return {"approved": False}
            
    except SlackApiError as e:
        print(f"[HITL] SlackApiError: {e.response['error']}. Reverting to terminal.")
        decision = input("Approve action? (y/n): ").strip().lower()
        return {"approved": decision == "y"}