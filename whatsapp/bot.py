# Duchess Chess — Copyright (c) 2026 Daniel Ammeraal
# Licensed under the MIT License. See LICENSE for details.
"""FastAPI WhatsApp webhook server.

Run with:
    uvicorn whatsapp.bot:app --host 0.0.0.0 --port 8000

Twilio will POST to POST /whatsapp on every incoming WhatsApp message.
Images are served at GET /media/{token} and referenced by the public URL
set in the WHATSAPP_PUBLIC_URL environment variable.
"""
import collections
import os
import uuid

from fastapi import FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse

from duchess.database import SessionLocal
from whatsapp.render import fen_to_ascii, fen_to_png
from whatsapp.wa_processor import get_pref, handle_message

app = FastAPI(title="Duchess WhatsApp Bot")

# In-memory image cache: token -> png_bytes (capped at 100 entries)
_images: collections.OrderedDict[str, bytes] = collections.OrderedDict()
_IMAGE_CACHE_MAX = 100


def _store_image(png: bytes) -> str:
    """Store a PNG and return its token."""
    token = str(uuid.uuid4())
    _images[token] = png
    if len(_images) > _IMAGE_CACHE_MAX:
        _images.popitem(last=False)  # evict oldest
    return token


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request) -> Response:
    form = await request.form()
    phone = form.get("From", "")   # e.g. "whatsapp:+31612345678"
    body = form.get("Body", "").strip()

    db = SessionLocal()
    try:
        reply_text, fen = handle_message(phone, body, db)
    except Exception as exc:
        reply_text = "Something went wrong — please try again."
        fen = None
        print(f"ERROR handling message from {phone}: {exc}")
    finally:
        db.close()

    twiml = MessagingResponse()
    public_url = os.getenv("WHATSAPP_PUBLIC_URL", "").rstrip("/")
    pref = get_pref(phone)

    if fen:
        if pref in ("both", "text"):
            ascii_board = fen_to_ascii(fen)
            full_text = f"{reply_text}\n\n{ascii_board}"
        else:
            full_text = reply_text

        msg = twiml.message(full_text)

        if pref in ("both", "image") and public_url:
            try:
                png = fen_to_png(fen)
                token = _store_image(png)
                msg.media(f"{public_url}/media/{token}")
            except Exception as exc:
                print(f"WARNING: image render failed: {exc}")
    else:
        twiml.message(reply_text)

    return Response(content=str(twiml), media_type="application/xml")


@app.get("/media/{token}")
def serve_image(token: str) -> Response:
    png = _images.get(token)
    if not png:
        return Response(status_code=404)
    return Response(content=png, media_type="image/png")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
