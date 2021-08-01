from typing import Optional, Callable

import requests
from fastapi import FastAPI
from pydantic import conint, constr, BaseModel, parse_obj_as, ValidationError
from redis import from_url
from starlette.responses import JSONResponse

from core.settings import settings

app = FastAPI()
redis_instance = from_url(settings.REDIS_DSN)


class BadResponse(BaseModel):
    errcode: int
    errmsg: str


class GoodResponse(BaseModel):
    access_token: str
    expires_in: int


def try_parse(obj):
    try:
        return parse_obj_as(GoodResponse, obj)
    except ValidationError:
        return parse_obj_as(BadResponse, obj)


def fetch_wechat_token() -> BadResponse or str:
    key = "data::wechat_access_token"
    cache = redis_instance.get(key)
    if isinstance(cache, str):
        return cache
    resp = requests.get("https://api.weixin.qq.com/cgi-bin/token", params={
        "grant_type": "client_credential",
        "appid": settings.WECHAT_APPID,
        "secret": settings.WECHAT_SECRET,
    }).json()
    data = try_parse(resp)
    if isinstance(data, GoodResponse):
        redis_instance.set(key, data.access_token, settings.EXPIRE_SECS)
        return data.access_token
    else:
        return data


class TokenResponse(BaseModel):
    token: str


class ForbiddenResponse(BaseModel):
    detail: str


@app.get("/{token}", response_model=TokenResponse, responses={
    404: {"model": BadResponse},
    403: {"model": ForbiddenResponse}
})
def get_token(token: constr(min_length=1)):
    if token != settings.SERVER_SECRET:
        return JSONResponse({"detail": "bad token"}, 403)
    data = fetch_wechat_token()
    if isinstance(data, BadResponse):
        return JSONResponse(data.json(), 404)
    return TokenResponse(token=data)


@app.on_event("shutdown")
def shutdown():
    redis_instance.close()
