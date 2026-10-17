# TASK_MEE_014 — Tester Access Guide (Mr. Xu's team)

This is the procedure for testing MEE (Multimodal Emotion Engine) remotely
from your own computer. No software installation is required — only a
modern web browser (Chrome or Edge, desktop).

## What you need

- A computer with a webcam and microphone
- A modern browser (Chrome 100+ or Edge 100+)
- The **demo URL** (page), the **WebSocket server URL**, and the **access token** from your contact at Deepsim AI

## Step-by-step

### 1. Open the demo page

Open your browser and navigate to the **page URL** your contact provided:

```
https://mee.deepsim.ai:8443/          (PUBLIC — any device, no Tailscale needed)   <- primary
https://jetson-agx:8443/              (tailnet — Tailscale app on the device)     <- legacy
https://localhost:8443/               (if you are on the Jetson itself)
```

> **The public URL works on any device** — phones on data, China via VPN,
> laptops on any network. Use the tailnet URL only when the device has the
> Tailscale app installed.
>
> **TASK_MEE_035 (2026-10-16):** Public access is now served by Pangolin on
> `mee.deepsim.ai` (page) and `meews.deepsim.ai:8443` (WebSocket). The old
> Tailscale-Funnel URL (`jetson-agx.tail0d394d.ts.net`) is deprecated.
> `mee.deepsim.ai` uses a self-signed cert, so **accept the certificate warning**
> (Chrome: Advanced → Proceed; Firefox/Safari: Accept the risk and continue).
> This is expected and safe — it only means the cert isn't signed by a public CA.
> The WebSocket (`wss://meews.deepsim.ai:8443/`) is auto-filled by the page.

The page should look like a dark UI with a "Connection" card on the left
and a "Fused Affective State" panel on the right.

### 2. Connect

1. In the **Access token** field, type the token your contact gave you
   out-of-band (a long hex string — it is **not** auto-filled on the page).
2. Click **Connect**.

> **Note:** The token is **never** exposed via a public endpoint — it is
> handed to you separately (chat/secure channel). Do not look for it on the
> page. If your contact says the server restarted, the same token still
> works — only the connection needs to be re-established.
>
> **TASK_MEE_035:** The Server URL field on the page is pre-filled with
> `wss://meews.deepsim.ai:8443/` — you only need to type the token and click
> Connect. You do not need to set the URL manually unless your contact gave
> you a different endpoint.

### 3. Start the test

1. Click **Start Test**.
2. The browser will ask for **camera** and **microphone** permission.
   Click **Allow** for both.
3. A live camera preview appears in the left panel, and two indicators
   (Camera, Microphone) turn green.

> **If the browser does NOT show a permission prompt:**
> - Make sure you loaded the page over **`https://`** (not `http://`).
>   Browsers block camera/mic on non-secure origins without warning.
> - Check that the cert warning was accepted (Step 1).
> - Click the lock icon in the address bar and confirm permissions aren't blocked.

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
| No permission prompt / "Permission denied" banner | Make sure you loaded the page over `https://`. Plain HTTP blocks camera/mic silently. Check the URL starts with `https://` and accept the self-signed cert warning. |
| Camera/mic not detected | Check that no other app is using the device. Restart the browser. |
| "Permission denied or no devices: TypeError" | This is a HTTPS issue — verify you are on `https://localhost:8443/` or `https://jetson-agx:8443/`, not `http://`. Accept the self-signed cert warning first. |
| No results after start | Wait a few seconds — the engine is processing. If still nothing, check that you are connected (green dot). |
| "Connection closed" banner | Reconnect and re-authenticate. The server may have restarted. If you see "code 1008" specifically, the token was rejected — verify it matches the value your contact gave you. |
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
