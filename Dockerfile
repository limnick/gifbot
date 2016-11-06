FROM gliderlabs/alpine:latest
MAINTAINER Nick Johnson <njohnson@limcollective.com>

RUN apk update

# install python and deps
RUN apk add --no-cache python python-dev zlib-dev jpeg-dev gcc musl-dev freetype-dev && \
    python -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip install --upgrade pip setuptools && \
    rm -r /root/.cache

ENV APP_DIR=/app
WORKDIR ${APP_DIR}

ADD ./requirements.txt ${APP_DIR}/requirements.txt
RUN pip install -U -r requirements.txt

ADD ./ ${APP_DIR}

ENV BOT_NAME ""
ENV IRC_PASS ""
ENV IRC_NETWORK ""
ENV PUB_IRC_NETWORK ""
ENV IRC_CHAN ""

EXPOSE 9000

CMD ${APP_DIR}/docker_entry.sh
