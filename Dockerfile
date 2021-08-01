FROM python:3.9-alpine

RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.ustc.edu.cn/g' /etc/apk/repositories && \
    sed -i 's/https/http/' /etc/apk/repositories && \
    apk add --no-cache curl && \
    pip config set global.index-url https://mirrors.ustc.edu.cn/pypi/web/simple

WORKDIR /usr/src/app
COPY requirements.txt ./

RUN \
    apk add --no-cache postgresql-libs && \
    apk add --no-cache --virtual .build-deps gcc musl-dev libc-dev postgresql-dev make && \
    pip install --no-cache-dir "uvicorn[standard]" && \
    pip install --no-cache-dir -r requirements.txt && \
    apk --purge del .build-deps

COPY . .

ENTRYPOINT [ "python", "main.py"]
