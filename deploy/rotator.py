import asyncio
import os
import sys
from loguru import logger

# Add src to python path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_webapi.utils.db import get_db_pool, upsert_cookie, get_all_active_cookies, set_cookie_active
from gemini_webapi.utils.rotate_1psidts import rotate_1psidts
from gemini_webapi.exceptions import AuthError

async def main():
    logger.info("Starting Gemini Cookie Rotator Service...")
    
    # Initialize DB
    await get_db_pool()

    # Optional: Load initial cookies from ENV
    initial_psid = os.getenv("INIT_SECURE_1PSID")
    initial_psidts = os.getenv("INIT_SECURE_1PSIDTS")
    
    if initial_psid and initial_psidts:
        logger.info("Found initial cookies in ENV, upserting to DB...")
        await upsert_cookie(initial_psid, initial_psidts)

    while True:
        try:
            cookies_list = await get_all_active_cookies()
            if not cookies_list:
                logger.warning("No active cookies found in DB. Waiting...")
                await asyncio.sleep(60)
                continue

            for cookie_data in cookies_list:
                psid = cookie_data["__Secure-1PSID"]
                logger.info(f"Rotating cookies for session: {psid[:10]}...")
                
                try:
                    # This function now updates DB internally
                    await rotate_1psidts(cookie_data)
                    logger.success(f"Successfully rotated cookies for {psid[:10]}...")
                except AuthError:
                    logger.error(f"AuthError for {psid[:10]}... Session is invalid.")
                    await set_cookie_active(psid, False)
                except Exception as e:
                    logger.error(f"Failed to rotate cookies for {psid[:10]}...: {e}")

            # Wait before next rotation cycle (e.g., 10 minutes)
            # Google rotates them frequently, but we don't want to spam
            await asyncio.sleep(600) 

        except Exception as e:
            logger.error(f"Unexpected error in rotator loop: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
