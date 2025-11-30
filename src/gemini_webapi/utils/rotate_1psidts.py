import os
import time
from pathlib import Path

from httpx import AsyncClient

from ..constants import Endpoint, Headers
from ..exceptions import AuthError


async def rotate_1psidts(cookies: dict, proxy: str | None = None) -> str:
    """
    Refresh the __Secure-1PSIDTS cookie and store the refreshed cookie value in cache file.

    Parameters
    ----------
    cookies : `dict`
        Cookies to be used in the request.
    proxy: `str`, optional
        Proxy URL.

    Returns
    -------
    `str`
        New value of the __Secure-1PSIDTS cookie.

    Raises
    ------
    `gemini_webapi.AuthError`
        If request failed with 401 Unauthorized.
    `httpx.HTTPStatusError`
        If request failed with other status codes.
    """

    try:
        from .db import upsert_cookie
    except ImportError:
        # Fallback or error if db module is missing/failing, but we assume it exists
        raise

    # We proceed to rotate without checking local file timestamp for now, 
    # assuming the caller (auto_refresh loop) handles the interval.
    async with AsyncClient(http2=True, proxy=proxy) as client:
        response = await client.post(
            url=Endpoint.ROTATE_COOKIES.value,
            headers=Headers.ROTATE_COOKIES.value,
            cookies=cookies,
            data='[000,"-0000000000000000000"]',
        )
        if response.status_code == 401:
            raise AuthError
        response.raise_for_status()

        if new_1psidts := response.cookies.get("__Secure-1PSIDTS"):
            # Save to DB instead of file
            await upsert_cookie(cookies['__Secure-1PSID'], new_1psidts)
            return new_1psidts

