FROM python:3.12-slim-bookworm

WORKDIR /app

# 修复 docker build 在国内网络下 apt-get update 经常超时的问题：
# 默认源是 deb.debian.org（国外），国内构建会卡 5-30s。改用阿里云镜像（毫秒级）。
# 同时把超时和重试都调高，给网络抖动留余量。
# 用户如果在国外网络，把 APT_MIRROR 改回 deb.debian.org 即可，或 build 时传 --build-arg。
ARG APT_MIRROR=mirrors.aliyun.com
ARG APT_SUITE=bookworm

# Latest releases available at https://github.com/aptible/supercronic/releases
ARG TARGETARCH
ENV SUPERCRONIC_VERSION=v0.2.39

# 换 apt 源到 APT_MIRROR（构建时通过 --build-arg 覆盖）
RUN set -ex && \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|deb.debian.org/debian|${APT_MIRROR}/debian|g" /etc/apt/sources.list.d/debian.sources; \
        sed -i "s|security.debian.org/debian-security|${APT_MIRROR}/debian-security|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    fi && \
    # apt-get update 重试 3 次（网络抖动场景）
    for i in 1 2 3; do \
        echo "[apt-get update] attempt $i/3"; \
        if apt-get update; then \
            echo "[apt-get update] success"; \
            break; \
        else \
            echo "[apt-get update] attempt $i failed"; \
            [ $i -eq 3 ] && exit 1; \
            sleep 3; \
        fi; \
    done && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    case ${TARGETARCH} in \
    amd64) \
    export SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64; \
    export SUPERCRONIC_SHA1SUM=c98bbf82c5f648aaac8708c182cc83046fe48423; \
    export SUPERCRONIC=supercronic-linux-amd64; \
    ;; \
    arm64) \
    export SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-arm64; \
    export SUPERCRONIC_SHA1SUM=5ef4ccc3d43f12d0f6c3763758bc37cc4e5af76e; \
    export SUPERCRONIC=supercronic-linux-arm64; \
    ;; \
    *) \
    echo "Unsupported architecture: ${TARGETARCH}"; \
    exit 1; \
    ;; \
    esac && \
    echo "Downloading supercronic for ${TARGETARCH} from ${SUPERCRONIC_URL}" && \
    # 重试机制：最多5次，每次超时60秒（github 在国内慢）
    for i in 1 2 3 4 5; do \
        echo "Download attempt $i/5"; \
        if curl -fsSL --connect-timeout 30 --max-time 120 -o "$SUPERCRONIC" "$SUPERCRONIC_URL"; then \
            echo "Download successful"; \
            break; \
        else \
            echo "Download attempt $i failed"; \
            if [ $i -eq 5 ]; then \
                echo "All download attempts failed"; \
                exit 1; \
            fi; \
            sleep 3; \
        fi; \
    done && \
    echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - && \
    chmod +x "$SUPERCRONIC" && \
    mv "$SUPERCRONIC" "/usr/local/bin/${SUPERCRONIC}" && \
    ln -s "/usr/local/bin/${SUPERCRONIC}" /usr/local/bin/supercronic && \
    supercronic -version && \
    apt-get remove -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 从官方镜像拷贝 uv 二进制
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 先安装依赖（利用 Docker 层缓存）
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# 再复制项目代码并安装项目本身
COPY docker/manage.py .
COPY trendradar/ ./trendradar/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# 复制 entrypoint.sh 并强制转换为 LF 格式
COPY docker/entrypoint.sh /entrypoint.sh.tmp
RUN sed -i 's/\r$//' /entrypoint.sh.tmp && \
    mv /entrypoint.sh.tmp /entrypoint.sh && \
    chmod +x /entrypoint.sh && \
    chmod +x manage.py && \
    mkdir -p /app/config /app/output

ENV PYTHONUNBUFFERED=1 \
    CONFIG_PATH=/app/config/config.yaml \
    FREQUENCY_WORDS_PATH=/app/config/frequency_words.txt

ENTRYPOINT ["/entrypoint.sh"]