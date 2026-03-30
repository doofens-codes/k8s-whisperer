# K8sWhisperer 🩺

**K8sWhisperer** is an Autonomous Kubernetes Incident Response Agent. It automates the extremely stressful and time-consuming workflow of debugging production failures in Kubernetes.

Instead of human SREs manually inspecting logs, correlating events, inferring root causes, and executing corrective actions, K8sWhisperer compresses this entire reasoning sequence into an intelligent, 7-stage autonomous pipeline that acts within seconds—while maintaining complete safety, explainability, and Human-in-the-loop (HITL) control via Slack.

## 🏗 Architecture (7-Stage Pipeline)

At its core, K8sWhisperer is structured as a LangGraph StateAgent. Each node connects sequentially to form an unbreakable SRE reasoning loop passing an immutable `ClusterState` object:

1. **Observe**: Polls cluster states (Pod events, node health, memory pressure) every 30 seconds via structured `kubectl` commands.
2. **Detect**: Groq LLMs analyze the raw data and classify underlying anomalies using strict evaluation criteria matrices (e.g. associating signal triggers to `CrashLoopBackOff` or `OOMKilled`).
3. **Diagnose**: Fetches deep logs (`--previous` container crashes) and Kubernetes `describe` events to synthesize a concise, evidence-backed root cause analysis.
4. **Plan**: Proposes a remediation action (e.g., dynamically patching memory constraints) alongside a computed `blast_radius` and `confidence` score.
5. **Safety Gate**: The robotic constraint router. Evaluates strict Problem Statement conditions (Action must be safe, confidence > 0.8, blast radius = low). If unsafe, triggers the HITL process.
6. **HITL / Execute**:
   - **HITL (Slack)**: Uses Slack Interactive Webhooks to prompt an administrator. Execution halts until human approval is pressed.
   - **Execute**: Modifies the Kubernetes cluster resources surgically using `kubectl patch` or `set`, then sleeps to verify recovery.
7. **Explain**: Generates a persistent, human-readable post-mortem audit log.

---

## 🚦 Official Anomaly ➔ Action Mappings
K8sWhisperer strictly adheres to the following behavioral contract:

| Anomaly | Trigger Condition | Agent Action | Severity | Auto-Execute? |
|---------|--------------------|--------------|----------|---------------|
| **CrashLoopBackOff** | `restartCount > 3` | Restart Pod after diagnosing | HIGH | ✅ Yes |
| **OOMKilled** | `terminated.reason = OOMKilled` | Auto-scale Resource Limits (`+50%`) | HIGH | ✅ Yes |
| **Evicted Pod** | `pod.status = Evicted` | Delete/Clean up evicted pod | LOW | ✅ Yes |
| **Pending Pod** | `phase = Pending` | Describe Pod, Alert Human | MED | ❌ HITL Required |
| **ImagePullBackOff** | `reason = ErrImagePull` | Extract image info, Alert Human | MED | ❌ HITL Required |
| **Deploy Stalled** | `updatedReplicas ≠ replicas` | Check events, Alert Human | HIGH | ❌ HITL Required |
| **NodeNotReady** | `Ready = False` | Log metrics, Alert Human | CRITICAL | ❌ HITL Required |

---

## 🚀 Setup Instructions

Follow these exact steps to run K8sWhisperer locally and connect it to your Slack workspace.

### 1. Prerequisites
- Python 3.10+
- A running local/remote Kubernetes cluster (e.g., Minikube, kind, or Docker Desktop K8s) with `kubectl` configured.
- A free [Slack API](https://api.slack.com/apps) App.
- [ngrok](https://ngrok.com/) (to expose the local FastAPI webhook server to Slack).
- A free [Groq API Key](https://console.groq.com/).

### 2. Install Dependencies
```bash
git clone https://github.com/your-repo/k8s-whisperer.git
cd k8s-whisperer
pip install -r requirements.txt
```

### 3. Environment Variables
Copy the `.env.example` file and fill in your keys:
```bash
cp .env.example .env
```
Inside your `.env`:
- `GROQ_API_KEY`: Your fast LLM API key.
- `SLACK_BOT_TOKEN`: Your heavily permissioned Slack bot token (`xoxb-...`).
- `SLACK_CHANNEL`: `#your-channel-name`.

### 4. Slack App Configuration (Crucial)
You **must** configure your Slack App to talk back to your agent when you click the "Approve/Reject" buttons.

1. Start `ngrok` on port 8000 (the port our background FastAPI webhook spins up on):
   ```bash
   ngrok http 8000
   ```
2. Go to your **Slack App Dashboard** ➔ **Interactivity & Shortcuts**.
3. Toggle "Interactivity" to **ON**.
4. Paste your ngrok URL combined with the strict `/slack/actions` endpoint into the **Request URL** field:
   `https://<YOUR-NGROK-ID>.ngrok.app/slack/actions`
5. Click **Save Changes**.

*(Keep the ngrok terminal open!)*

---

## 🧪 Testing the Scenarios

K8sWhisperer comes pre-packaged with malicious deployments specifically crafted to test different anomaly branches.

1. Start K8sWhisperer in your terminal:
   ```bash
   python main.py
   ```
2. In a different terminal, manually inject a failure into your cluster. For example, to test an `OOMKilled` auto-patching mechanism:
   ```bash
   kubectl apply -f scenarios/oomkill.yaml
   ```
3. **Watch the magic happen.** K8sWhisperer will observe the rapid memory failure, run deep analysis on the previous container termination states, decide it needs a `patch_memory` action, push a beautiful Block-Kit notification to your Slack, wait for your approval button press, dynamically rewrite the Deployment's memory limits, and then verify the pod successfully restarts without crashing!

*Note: For anomalies like `imagepullbackoff.yaml`, the agent will artificially restrict itself to `alert_human` mode and demand your intervention per the problem statement constraint rules.*