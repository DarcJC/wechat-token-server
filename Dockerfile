FROM python:3.10-alpine

# If you are in China, you can run the following to speed up the installation
    #sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories && \
    #sed -i 's/https/http/' /etc/apk/repositories && \

WORKDIR /usr/src/app
COPY requirements.txt ./

RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/web/simple \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

#ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--workers", "$WORKER_NUM", "--log-level", "info"]
ENTRYPOINT [ "python", "main.py"]
