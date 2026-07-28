#
# Trigger an OUTBOUND call. Your bot.py dev server must already be running and
# your ngrok tunnel must be up (PUBLIC_WS_URL points at it).
#
# Usage:
#   python make_call.py +15125550123 "Jane Doe" "your demo request from Tuesday"
#
# Only the phone number is required; name and reason are optional but make the
# call feel personal.
#
import argparse
import os
from xml.sax.saxutils import quoteattr

from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(override=True)


def main():
    parser = argparse.ArgumentParser(description="Start an outbound AI voice call.")
    parser.add_argument("to_number", help="Number to call in E.164 form, e.g. +15125550123")
    parser.add_argument("customer_name", nargs="?", default="", help="Person's name (optional)")
    parser.add_argument("call_reason", nargs="?", default="", help="Why you're calling (optional)")
    args = parser.parse_args()

    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    from_number = os.environ["TWILIO_FROM_NUMBER"]
    ws_url = os.environ["PUBLIC_WS_URL"]  # e.g. wss://your-subdomain.ngrok.io/ws

    client = Client(account_sid, auth_token)

    # quoteattr adds the surrounding quotes AND escapes &, <, >, " safely.
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url={quoteattr(ws_url)}>
      <Parameter name="call_type" value="outbound" />
      <Parameter name="customer_name" value={quoteattr(args.customer_name)} />
      <Parameter name="call_reason" value={quoteattr(args.call_reason)} />
      <Parameter name="to_number" value={quoteattr(args.to_number)} />
      <Parameter name="from_number" value={quoteattr(from_number)} />
    </Stream>
  </Connect>
</Response>"""

    call = client.calls.create(to=args.to_number, from_=from_number, twiml=twiml)
    print(f"Outbound call started -> {args.to_number}")
    print(f"Call SID: {call.sid}")


if __name__ == "__main__":
    main()
