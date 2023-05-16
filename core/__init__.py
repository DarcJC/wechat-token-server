import hashlib
import time
from typing import Optional, Callable

import aioredis
import aiohttp
import random
import string
from typing import Literal, Optional
from fastapi import FastAPI
from pydantic import conint, constr, BaseModel, parse_obj_as, ValidationError
from aioredis import from_url
from starlette.responses import JSONResponse

from core.settings import settings

app = FastAPI()
redis_instance: aioredis.Redis = None


@app.on_event("startup")
async def startup():
    global redis_instance
    redis_instance = await from_url(settings.REDIS_DSN)


class BadResponse(BaseModel):
    errcode: int
    errmsg: str


class GoodResponse(BaseModel):
    access_token: str
    expires_in: int


class TicketResponse(BaseModel):
    errcode: int
    errmsg: str
    ticket: str
    expires_in: int


def try_parse(obj):
    try:
        return parse_obj_as(GoodResponse, obj)
    except ValidationError:
        return parse_obj_as(BadResponse, obj)


async def fetch_wechat_token() -> BadResponse or str:
    key = "data::wechat_access_token"
    cache = await redis_instance.get(key)
    if cache is not None:
        return cache.decode()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.weixin.qq.com/cgi-bin/token", params={
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APPID,
            "secret": settings.WECHAT_SECRET,
        }) as resp:
            data = try_parse(await resp.json())
            if isinstance(data, GoodResponse):
                await redis_instance.set(key, data.access_token, settings.EXPIRE_SECS)
                return data.access_token
            else:
                return data


async def fetch_js_ticket_token() -> TicketResponse:
    key = "data::wechat_js_ticket_token"
    cache = await redis_instance.get(key)
    if cache is not None:
        return TicketResponse(ticket=cache.decode(), errcode=0, errmsg="ok", expires_in="0")
    token = await fetch_wechat_token()
    if type(token) == 'bytes':
        token = token.decode()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.weixin.qq.com/cgi-bin/ticket/getticket", params={
            "access_token": token,
            "type": "jsapi",
        }) as resp:
            data = parse_obj_as(TicketResponse, await resp.json())
            await redis_instance.set(key, data.ticket, settings.EXPIRE_SECS)
            return data


class TokenResponse(BaseModel):
    token: str


class SignatureResponse(BaseModel):
    signature: str
    nonce: str
    timestamp: int


class ForbiddenResponse(BaseModel):
    detail: str


@app.get("/access_token/{token}", response_model=TokenResponse, responses={
    404: {"model": BadResponse},
    403: {"model": ForbiddenResponse}
})
async def get_token(token: constr(min_length=1)):
    if token != settings.SERVER_SECRET:
        return JSONResponse({"detail": "bad token"}, 403)
    data = await fetch_wechat_token()
    if isinstance(data, BadResponse):
        return JSONResponse(data.json(), 404)
    return TokenResponse(token=data)


@app.get("/js_ticket/{token}", response_model=TokenResponse)
async def get_js_ticket(token: constr(min_length=1)):
    if token != settings.SERVER_SECRET:
        return JSONResponse({"detail": "bad token"}, 403)
    data = await fetch_js_ticket_token()
    return TokenResponse(token=data.ticket)


@app.get("/js_sdk/signature", response_model=SignatureResponse)
async def js_sdk_signature(url: constr(min_length=1)):
    # get domain from url
    url_split = url.split("/")
    if len(url_split) < 3:
        return JSONResponse({"detail": "bad url"}, 403)
    domain = url_split[2]
    if domain not in settings.DOMAIN_WHITELIST:
        return JSONResponse({"detail": "domain isn't in whitelist"}, 403)
    sign_body = dict(sorted({
        "noncestr":
            ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16)),
        "jsapi_ticket": await fetch_js_ticket_token(),
        "timestamp": int(time.time()),
        "url": url,
    }.items()))
    sign_str = '&'.join([f"{k}={v}&" for k, v in sign_body.items()])[:-1]
    sign = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()
    return SignatureResponse(signature=sign, nonce=sign_body["noncestr"], timestamp=sign_body["timestamp"])


@app.on_event("shutdown")
def shutdown():
    redis_instance.close()
