from typing import Optional, Callable

import aioredis
import aiohttp
from typing import Literal
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
    errmsg: Literal['ok'] or str
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
        return cache
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
        return cache
    token = await fetch_wechat_token()
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.weixin.qq.com/cgi-bin/ticket/getticket?access_token=", params={
            "token": token,
            "type": "jsapi",
        }) as resp:
            data = parse_obj_as(await resp.json(), TicketResponse)
            await redis_instance.set(key, data.ticket, settings.EXPIRE_SECS)
            return data


class TokenResponse(BaseModel):
    token: str


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


@app.on_event("shutdown")
def shutdown():
    redis_instance.close()
