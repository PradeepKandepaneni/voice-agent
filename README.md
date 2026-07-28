# Inbound + Outbound AI Voice Agent (free-to-prototype starter)

One AI agent that answers your inbound calls **and** makes outbound calls, built
on open-source [Pipecat](https://github.com/pipecat-ai/pipecat) + Twilio.

**The free stack:** Google Gemini (free tier) · Deepgram STT ($200 free credit) ·
Cartesia TTS (free tier) · Twilio (~$15 trial credit, no card). You can build,
test, and demo the whole thing for about $0. Real production calls cost roughly
**$0.02–0.06 per minute** once you exit the free tiers.

---

## How it works

```
INBOUND:   caller --> Twilio number --> (TwiML Bin) --> your bot's /ws  --> agent talks
OUTBOUND:  make_call.py --> Twilio dials lead --> streams into same /ws --> agent talks
```

The same running `bot.py` serves both. Outbound calls are tagged
`call_type=outbound` (plus the lead's name + reason), so the bot switches from
its support personality to its sales personality automatically.

---

## 1. Get your keys (all free)

| Service | Where | Free allowance |
|---|---|---|
| Twilio | https://console.twilio.com | ~$15 trial credit + 1 number |
| Gemini | https://aistudio.google.com/apikey | Free tier |
| Deepgram | https://console.deepgram.com | $200 credit |
| Cartesia | https://play.cartesia.ai | Free tier |
| ngrok | https://ngrok.com | Free tunnel |

## 2. Install

```bash
cd voice-agent
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env          # then fill in .env
```

## 3. Start the tunnel + bot (two terminals)

Terminal 1 — expose your local server to the internet:
```bash
ngrok http 7860
```
Copy the `https://…ngrok-free.app` URL. Put its **wss** form + `/ws` into `.env`
as `PUBLIC_WS_URL` (e.g. `wss://loud-otter-1234.ngrok-free.app/ws`).

Terminal 2 — run the agent:
```bash
python bot.py --transport twilio
```

## 4. Wire up INBOUND (one-time, in Twilio console)

1. Twilio Console → **TwiML Bins** → create one:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <Response>
     <Connect>
       <Stream url="wss://YOUR-SUBDOMAIN.ngrok-free.app/ws" />
     </Connect>
   </Response>
   ```
2. **Phone Numbers → Active numbers → your number → Voice → "A call comes in"** →
   set to that TwiML Bin → Save.
3. Call your Twilio number. The agent answers. ✅

> On a Twilio **trial**, you can only call/answer *verified* numbers. Verify your
> own mobile in the console first, or upgrade (adding a card keeps the same rates).

## 5. Fire an OUTBOUND call

With `bot.py` still running:
```bash
python make_call.py +15125550123 "Jane Doe" "your demo request from Tuesday"
```
Twilio dials the number and streams it into your agent, which opens with a
personalized line. ✅

---

## Make it yours

- **Personality / script:** edit `prompts.py` (the only file most people touch).
- **Voice:** change `CARTESIA_VOICE_ID` in `.env`.
- **Brain:** swap `GOOGLE_MODEL`, or replace `GoogleLLMService` in `bot.py` with
  another provider (OpenAI, Groq/Llama, etc.).
- **CRM / calendar:** add tool calls in the LLM step to look up customers or book
  slots. Pipecat supports function calling.

### "Speak first" note
The agent opens the call via a `TTSSpeakFrame` in `on_client_connected`. If your
installed Pipecat version errors on `worker.queue_frames([...])`, that method may
be named slightly differently in your version — check the runner/worker docs at
https://docs.pipecat.ai and adjust that one line.

---

## Before you dial real prospects (important, US)

Outbound calling is legally regulated:
- **TCPA:** you generally need prior consent to call/robocall leads. Keep proof of
  consent and honor do-not-call / opt-out requests immediately.
- **A2P 10DLC + STIR/SHAKEN:** register your number/brand with Twilio or your
  calls get flagged as "Spam Likely" and blocked. Do this before volume calling.
- Identify yourself and the business at the start of every outbound call.

This isn't legal advice — confirm the rules for your industry and state.

---

## Cost reality

- Software (Pipecat): free, forever.
- Prototyping: ~$0 on the free tiers/credits above.
- Production: ~$0.02–0.06/min all-in (telephony + STT + LLM + TTS). Managed
  platforms like Bland/Retell/Vapi run ~$0.09–0.33/min if you'd rather not host.
