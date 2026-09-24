# TASK_MEE_014 — Tester Access Guide (Mr. Xu's team)

This is the procedure for testing MEE (Multimodal Emotion Engine) remotely
from your own computer. No software installation is required — only a
modern web browser (Chrome or Edge, desktop).

## What you need

- A computer with a webcam and microphone
- A modern browser (Chrome 100+ or Edge 100+)
- The **demo URL** and the **access token** from your contact at Deepsim AI

## Step-by-step

### 1. Open the demo URL

Open your browser and navigate to the URL your contact provided
(e.g. `https://mee.example.com/`).

The page should look like a dark UI with a "Connection" card on the left
and a "Fused Affective State" panel on the right.

> **If the browser shows a warning**: the certificate is issued by
> Tailscale. Click **Advanced → Proceed** to continue. This is expected
> for a prototype deployment.

### 2. Connect

1. In the **Server URL** field, the URL should already be filled in. If not,
   paste the `wss://` URL your contact provided.
2. In the **Access token** field, paste the token (a long hex string).
3. Click **Connect**.

You should see a green dot next to "Connected" under Connection.
If you see a red dot with "Auth failed", the token is wrong — double-check
and retry.

### 3. Start the test

1. Click **Start Test**.
2. The browser will ask for **camera** and **microphone** permission.
   Click **Allow** for both.
3. A live camera preview appears in the left panel, and two indicators
   (Camera, Microphone) turn green.

### 4. Watch the results

The right panel updates in real time:

- **Fused Affective State** (large emoji + label): the combined
  multimodal emotion estimate.
- **Facial Expression**: bar chart of per-emotion scores from vision.
- **Voice Emotion**: bar chart of per-emotion scores from audio.
- **Trend**: a short-lived directional indicator (improving / declining /
  stable / unstable).
- **Latency**: last / average / min / max processing time on the Jetson.

Sit in front of the camera, speak, and change expression. The engine
processes each frame and audio chunk independently.

### 5. Stop

Click **Stop Test** when you are done. The camera and microphone stop,
and the indicators turn grey.

### 6. Disconnect

Click **Disconnect** to close the WebSocket connection.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Camera/mic not detected | Check that no other app is using the device. Restart the browser. |
| "Permission denied" banner | Click **Allow** in the browser permission prompt. If you accidentally denied, click the lock icon in the address bar and re-enable. |
| No results after start | Wait a few seconds — the engine is processing. If still nothing, check that you are connected (green dot). |
| "Connection closed" banner | Reconnect and re-authenticate. The server may have restarted. |
| Very high latency (> 500 ms) | Check your network connection. High latency may also indicate server load. |

## What you will NOT see

- MEE source code
- Model weights
- Jetson filesystem
- Internal services
- SSH access

Your browser only speaks to the MEE WebSocket endpoint. Everything else
stays on Deepsim AI's infrastructure.

## Feedback

Please note:
- The estimated emotion vs. the emotion you intended
- Latency (last/avg)
- Any dropped frames or connection drops
- Overall usability

Send screenshots if helpful.

---

*This is a prototype for capability evaluation. It is not a production
service. Do not distribute the token outside your team.*
