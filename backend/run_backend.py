import os
import sys
import traceback

if __name__ == '__main__':
    print("=== STARTING BACKEND LAUNCHER ===", flush=True)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Dotenv loaded.", flush=True)

        import uvicorn
        print("Imported uvicorn. Starting server on http://127.0.0.1:8000 ...", flush=True)
        uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info", reload=True)
    except Exception as e:
        print(f"CRITICAL ERROR IN BACKEND: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
