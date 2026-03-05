FROM python:3.12-alpine AS app

ARG USER=serviceuser

ENV USER=$USER
ENV HOME=/home/$USER
ENV GOSU_VERSION=1.19

# Установка системных зависимостей
RUN apk update && \
    apk add --no-cache curl frp ca-certificates \
    libstdc++ \
    libgcc \
    musl \
    freetype \
    fontconfig \
    jpeg \
    openjpeg \
    tiff \
    lcms2 && \
    adduser -D $USER && \
    touch /frpc.toml && \
    mkdir -p /certs/frp && \
    chown $USER:$USER /frpc.toml && \
    chown -R $USER:$USER /certs/frp && \
    chmod 600 /frpc.toml

RUN set -eux; \
  \
  apk add --no-cache --virtual .gosu-deps \
    ca-certificates \
    dpkg \
    gnupg \
  ; \
  \
  dpkgArch="$(dpkg --print-architecture | awk -F- '{ print $NF }')"; \
  wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch"; \
  wget -O /usr/local/bin/gosu.asc "https://github.com/tianon/gosu/releases/download/$GOSU_VERSION/gosu-$dpkgArch.asc"; \
  \
  export GNUPGHOME="$(mktemp -d)"; \
  gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys B42F6819007F00F88E364FD4036A9C25BF357DD4; \
  gpg --batch --verify /usr/local/bin/gosu.asc /usr/local/bin/gosu; \
  gpgconf --kill all; \
  rm -rf "$GNUPGHOME" /usr/local/bin/gosu.asc; \
  \
  apk del --no-network .gosu-deps; \
  \
  chmod +x /usr/local/bin/gosu

WORKDIR /app

# Создание необходимых директорий
RUN mkdir -p /certs/frp /tmp && \
    chown -R $USER:$USER /certs /tmp && \
    chmod 755 /certs /tmp


COPY --chown=$USER:$USER . .

COPY --chown=$USER:$USER start.sh /start.sh
RUN chmod +x /start.sh && \
  chown -R $USER:$USER /app && \
  pip install -U pip && \
  pip install -r requirements.txt


ENTRYPOINT ["/bin/sh", "-c", "exec gosu \"$USER\" /start.sh python3 main.py"]