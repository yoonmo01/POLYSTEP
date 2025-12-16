import sys
import asyncio
import uvicorn

def main():
    # ✅ uvicorn이 이벤트루프 만들기 전에 정책부터 고정 (중요)
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        print("EVENT LOOP POLICY =", type(asyncio.get_event_loop_policy()).__name__)

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        loop="asyncio",
    )

if __name__ == "__main__":
    main()