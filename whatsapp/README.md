# Duchess WhatsApp Chess Bot

Play chess against the Duchess engine directly in WhatsApp. Send a move, get the board back as an image or ASCII — no app install needed.

---

## How it works

```
You → WhatsApp → Twilio → FastAPI webhook → Duchess engine → reply
```

The bot runs as a FastAPI server alongside the training pipeline. Twilio handles the WhatsApp messaging layer.

---

## Setup

### 1. Twilio sandbox (one-time)

1. Sign up at [twilio.com](https://twilio.com)
2. Go to **Messaging → Try it out → Send a WhatsApp message**
3. Note your:
   - Account SID
   - Auth Token
   - Sandbox number (e.g. `+14155238886`)
4. Join the sandbox from your phone: send `join <keyword>` to the sandbox number on WhatsApp

### 2. RunPod environment variables

Add these to your pod's environment variables:

| Variable | Value |
|---|---|
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token |

### 3. Expose port 8000 on RunPod

In your pod template settings, add **HTTP port 8000**. RunPod will expose it at:
```
https://{POD_ID}-8000.proxy.runpod.net
```

### 4. Set the Twilio webhook

After `runpod_resume.sh` runs, it will print the public URL. Set it in Twilio:

- Go to **Messaging → Settings → WhatsApp sandbox settings**
- Set **"When a message comes in"** to:
  ```
  https://{POD_ID}-8000.proxy.runpod.net/whatsapp
  ```
- Method: `HTTP POST`

> The URL changes each time you get a new pod. Update it in Twilio after each fresh pod start.

---

## Commands

Send any of these to the Twilio sandbox number on WhatsApp:

| Message | Action |
|---|---|
| `new` | Start a new game as White |
| `new black` | Start a new game as Black |
| `e4` | Make a move in SAN notation |
| `e2e4` | Make a move in UCI notation |
| `Nf3` | Move a piece |
| `status` | Show the current board |
| `resign` | Resign the game |
| `mode image` | Board replies as PNG image only |
| `mode text` | Board replies as ASCII text only |
| `mode both` | Image + ASCII (default) |
| `help` | Show the command list |

---

## Board display modes

**Both (default):**
```
Duchess plays: e5

  +-----------------+
8 | ♜ ♞ ♝ ♛ ♚ ♝ ♞ ♜ |
7 | ♟ . ♟ ♟ ♟ ♟ ♟ ♟ |
6 | . . . . . . . . |
5 | . ♟ . . ♙ . . . |
4 | . . . . . . . . |
3 | . . . . . . . . |
2 | ♙ ♙ ♙ ♙ . ♙ ♙ ♙ |
1 | ♖ ♘ ♗ ♕ ♔ ♗ ♘ ♖ |
  +-----------------+
    a b c d e f g h
```
Plus a PNG board image attached.

**Image only:** just the PNG — cleaner for mobile.

**Text only:** just the ASCII board — works on any device, no image loading.

---

## Running locally (for testing)

```bash
source py-duchess/bin/activate
pip install -r requirements.txt

# Set env vars
export TWILIO_ACCOUNT_SID=ACxxxxx
export TWILIO_AUTH_TOKEN=xxxxx
export WHATSAPP_PUBLIC_URL=https://xxxx.ngrok.io

# Start the server
uvicorn whatsapp.bot:app --host 0.0.0.0 --port 8000

# In another terminal — expose publicly
ngrok http 8000
```

Then update the Twilio webhook to your ngrok URL.

---

## Files

| File | Description |
|---|---|
| `bot.py` | FastAPI app — Twilio webhook, image serving |
| `wa_processor.py` | Message routing and game logic adapter |
| `render.py` | FEN → PNG (cairosvg) and FEN → ASCII |
