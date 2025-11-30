import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_webapi import GeminiClient
from gemini_webapi.utils.db import get_db_pool

# Global client instance (can be improved with a pool of clients for high load)
client: GeminiClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global client
    await get_db_pool() # Init DB
    
    # Initialize client without specific cookies - it will try to find valid ones in DB
    client = GeminiClient(auto_refresh=False)
    try:
        await client.init()
        print("Gemini Client initialized successfully")
    except Exception as e:
        print(f"Warning: Failed to initialize Gemini Client at startup: {e}")
        print("Will try to re-initialize on first request.")
    
    yield
    
    # Shutdown
    if client:
        await client.close()

import aiofiles
import uuid
from pathlib import Path
import httpx

app = FastAPI(title="Gemini Web API Worker", lifespan=lifespan)

class GenerateRequest(BaseModel):
    prompt: str
    image_url: Optional[str] = None
    model: Optional[str] = None

@app.post("/generate")
async def generate_content(request: GenerateRequest):
    global client
    if not client:
        raise HTTPException(status_code=503, detail="Client not initialized")

    temp_file_path: Path | None = None
    
    try:
        files = []
        if request.image_url:
            # Download image to temp file
            async with httpx.AsyncClient() as http_client:
                resp = await http_client.get(request.image_url)
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to download image: {resp.status_code}")
                
                ext = request.image_url.split(".")[-1].split("?")[0] or "jpg"
                if len(ext) > 4: ext = "jpg" # fallback
                
                temp_file_path = Path(f"/tmp/{uuid.uuid4()}.{ext}")
                async with aiofiles.open(temp_file_path, "wb") as f:
                    await f.write(resp.content)
                
                files.append(temp_file_path)

        # The client logic we verified earlier handles re-init on 401/APIError
        response = await client.generate_content(
            prompt=request.prompt,
            files=files if files else None,
            model=request.model or "unspecified" # Let client handle default
        )
        
        return {
            "text": response.text,
            "images": [img.url for img in response.images],
            "metadata": response.metadata
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup temp file
        if temp_file_path and temp_file_path.exists():
            try:
                os.remove(temp_file_path)
            except Exception:
                pass

@app.get("/health")
async def health_check():
    return {"status": "ok", "client_initialized": client._running if client else False}
