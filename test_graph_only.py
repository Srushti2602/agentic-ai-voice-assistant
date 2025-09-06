import asyncio
from src.strict_intake_assistant import StrictIntakeAssistant

async def main():
    a = await StrictIntakeAssistant.create(flow_name="injury_intake_strict")  # << await async initializer
    sid = "test-seq-004"

    print("BOT1:", await a.start(sid))
    print("BOT2:", await a.handle_user("shree", sid))
    print("BOT3:", await a.handle_user("Patel", sid))
    print("BOT4:", await a.handle_user("front end crash on I-80", sid))
    print("BOT5:", await a.handle_user("2025-09-04", sid))
    print("BOT6:", await a.handle_user("I-80, near Exit 24", sid))
    print("BOT7:", await a.handle_user("no injuries", sid))
    print("BOT8:", await a.handle_user("No , hospital visit", sid))
    print("BOT9:", await a.handle_user("Three witnesses", sid))
    print("BOT10:", await a.handle_user("yes reported to police", sid))

asyncio.run(main())
