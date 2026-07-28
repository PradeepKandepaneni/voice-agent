#
# One AI voice agent that handles BOTH inbound and outbound phone calls.
#
# - Inbound:  a customer calls your Twilio number -> Twilio streams the call to
#             this bot's /ws endpoint (via a TwiML Bin you set up once).
# - Outbound: you run `make_call.py` -> it tells Twilio to dial a lead and
#             stream that call into this SAME bot, tagged call_type=outbound.
#
# The bot reads the call "direction" (and any customer info) from the stream
# parameters, then picks the right personality + opening line from prompts.py.
#
# API surface follows the official Pipecat v1.0 Twilio example.
#
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from prompts import build_greeting, build_system_prompt

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="INFO")

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Acme Co")


async def run_bot(transport, handle_sigint, *, direction, customer_name, call_reason):
    """Build and run the STT -> LLM -> TTS pipeline for a single call."""

    system_prompt = build_system_prompt(
        direction=direction,
        business_name=BUSINESS_NAME,
        customer_name=customer_name,
        call_reason=call_reason,
    )
    greeting = build_greeting(
        direction=direction,
        business_name=BUSINESS_NAME,
        customer_name=customer_name,
        call_reason=call_reason,
    )

    # --- The "brain": Google Gemini (free tier) ---
    llm = GoogleLLMService(
        api_key=os.getenv("GOOGLE_API_KEY"),
        model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash"),
        settings=GoogleLLMService.Settings(system_instruction=system_prompt),
    )

    # --- The "ears": Deepgram speech-to-text (free credits) ---
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))

    # --- The "voice": Cartesia text-to-speech (free tier) ---
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        settings=CartesiaTTSService.Settings(
            voice=os.getenv("CARTESIA_VOICE_ID", "71a7ad14-091c-4e8e-a314-022ece01c121"),
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),   # caller audio in (from Twilio websocket)
            stt,                 # -> text
            user_aggregator,     # add caller turn to context
            llm,                 # -> reply text
            tts,                 # -> audio
            transport.output(),  # agent audio out (to Twilio websocket)
            assistant_aggregator,  # add agent turn to context
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            # Twilio Media Streams are 8kHz mono; match it to avoid resampling.
            audio_in_sample_rate=8000,
            audio_out_sample_rate=8000,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Call connected ({direction}). Speaking opening line.")
        # The agent speaks first in BOTH directions. The system prompt tells the
        # model it already opened with this line, so it won't greet twice.
        # NOTE: if your installed Pipecat version raises on this line, the frame
        # queue method may be named differently — see README "Speak first".
        await worker.queue_frames([TTSSpeakFrame(greeting)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Call ended.")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=handle_sigint)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Entry point the Pipecat dev runner (and Pipecat Cloud) calls per connection."""
    transport_type, call_data = await parse_telephony_websocket(runner_args.websocket)
    logger.info(f"Transport: {transport_type}")

    # Custom <Parameter> values from the TwiML stream.
    # Inbound calls carry none -> we default to the inbound personality.
    body = call_data.get("body", {}) or {}
    direction = body.get("call_type", "inbound")
    customer_name = body.get("customer_name") or None
    call_reason = body.get("call_reason") or None
    logger.info(f"Direction={direction} name={customer_name} reason={call_reason}")

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data["call_id"],
        account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
    )

    transport = FastAPIWebsocketTransport(
        websocket=runner_args.websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    await run_bot(
        transport,
        runner_args.handle_sigint,
        direction=direction,
        customer_name=customer_name,
        call_reason=call_reason,
    )


if __name__ == "__main__":
    # Pipecat's development runner: starts a FastAPI server on :7860, exposes /ws,
    # and registers the Twilio webhook. Run with:  python bot.py --transport twilio
    from pipecat.runner.run import main

    main()
