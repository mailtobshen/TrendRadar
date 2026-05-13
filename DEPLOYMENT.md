# TrendRadar 部署说明

> 本文件供 Claude Code / OpenClaw 阅读理解 TrendRadar 部署架构和操作指南。

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     TrendRadar 部署架构                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐     ┌─────────────────────────────┐ │
│  │  Docker Host      │     │  WSL / Linux Host           │ │
│  │                  │     │                             │ │
│  │  ┌────────────┐  │     │  ┌───────────────────────┐  │ │
│  │  │trendradar  │  │     │  │trendradar-wechat-     │  │ │
│  │  │(container) │  │────▶│  │relay.py (port 8090)   │  │ │
│  │  └────────────┘  │     │  └───────────┬───────────┘  │ │
│  │                  │     │              │              │ │
│  │  ┌────────────┐  │     │              ▼              │ │
│  │  │trendradar-│  │     │  ┌───────────────────────┐  │ │
│  │  │mcp        │  │     │  │  iLink API            │  │ │
│  │  │(port 3333)│  │     │  │  (微信推送通道)        │  │ │
│  │  └────────────┘  │     │  └───────────────────────┘  │ │
│  │                  │     │                             │ │
│  │  ┌────────────┐  │     │                             │ │
│  │  │we-mp-rss  │  │     │                             │ │
│  │  │(port 8001)│  │     │                             │ │
│  │  └────────────┘  │     │                             │ │
│  │                  │     │                             │ │
│  │  ┌────────────┐  │     │                             │ │
│  │  │forge-proxy│  │     │                             │ │
│  │  │(port 8084)│  │     │                             │ │
│  │  └────────────┘  │     │                             │ │
│  └──────────────────┘     └─────────────────────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Docker 容器清单

| 容器名 | 镜像 | 端口 | 功能 | 状态 |
|--------|------|------|------|------|
| `trendradar` | `wantcat/trendradar:latest` | host 模式 | 热点抓取 + 定时推送 | ✅ 运行中 |
| `trendradar-mcp` | `wantcat/trendradar-mcp:latest` | 127.0.0.1:3333 | MCP AI 分析服务 | ✅ 运行中 |
| `we-mp-rss` | `ghcr.io/rachelos/we-mp-rss:latest` | 0.0.0.0:8001 | 微信公众号 RSS | ✅ 运行中 |
| `forge-proxy` | `nginx:alpine` | 0.0.0.0:8084 | Nginx 反向代理 | ✅ 运行中 |

---

## 3. 宿主机进程

| 进程 | 路径 | 端口 | 功能 |
|------|------|------|------|
| `trendradar-wechat-relay.py` | `~/.openclaw/workspace/scripts/` | 8090 | TrendRadar → 微信 中转服务 |

---

## 4. 数据流向

```
1. trendradar 容器（host 网络）
   ├── 每 30 分钟抓取 11 个平台热点
   ├── 按 frequency_words.txt 过滤关键词
   ├── 生成 HTML 报告 → output/
   └── 通过 HTTP Webhook → http://localhost:8090/webhook

2. trendradar-wechat-relay.py（port 8090）
   ├── 接收 trendradar 的 webhook 调用
   ├── 读取 ~/.hermes/weixin/accounts/ 下的微信账号 token
   └── 通过 iLink API 发送消息到微信

3. trendradar-mcp（port 3333）
   └── 提供 MCP 协议 AI 分析工具，供 OpenClaw 调用
```

---

## 5. 监控平台（11个）

| ID | 名称 |
|----|------|
| `toutiao` | 今日头条 |
| `baidu` | 百度热搜 |
| `wallstreetcn-hot` | 华尔街见闻 |
| `thepaper` | 澎湃新闻 |
| `bilibili-hot-search` | bilibili 热搜 |
| `cls-hot` | 财联社热门 |
| `ifeng` | 凤凰网 |
| `tieba` | 贴吧 |
| `weibo` | 微博 |
| `douyin` | 抖音 |
| `zhihu` | 知乎 |

---

## 6. 关键配置

### 6.1 环境变量（docker/.env）

```bash
# 代理配置
HTTP_PROXY=http://172.25.128.1:1080
HTTPS_PROXY=http://172.25.128.1:1080

# Web 服务器
WEBSERVER_PORT=8080

# AI 配置
AI_ANALYSIS_ENABLED=true
AI_API_KEY=sk-cp-***（MiniMax API Key）
AI_MODEL=minimax/MiniMax-M2.7-highspeed
AI_API_BASE=https://api.minimaxi.com/v1

# 运行模式
CRON_SCHEDULE=*/30 * * * *
RUN_MODE=cron
IMMEDIATE_RUN=true
```

### 6.2 代理说明

- **HTTP 代理**：`http://172.25.128.1:1080`（WSL 默认网关，指向 Windows Shadowsocks）
- WSL 中 `127.0.0.1:1080` 是 WSL 自己，不是 Windows 代理
- 容器内使用 `172.25.128.1:1080` 访问 Windows 代理

### 6.3 容器网络模式

- `trendradar` 使用 `network_mode: host`，直接使用宿主机网络
- 容器内 `localhost` = 宿主机

---

## 7. 文件结构

```
TrendRadar/
├── config/
│   ├── config.yaml              # 主配置文件（平台开关/关键词）
│   ├── frequency_words.txt      # 关键词过滤列表
│   └── ...
├── output/
│   ├── html/                    # 生成的 HTML 报告
│   ├── news/*.db               # SQLite 缓存数据库
│   └── ...
├── docker/
│   ├── docker-compose.yml       # 容器编排配置
│   ├── .env                     # 环境变量（API Keys）
│   └── Dockerfile
└── ...
```

---

## 8. 常用操作命令

### 8.1 容器管理

```bash
# 查看所有容器状态
docker ps -a

# 启动 trendradar
cd /home/administrator/.openclaw/workspace/TrendRadar/docker
docker-compose up -d trendradar

# 重启 trendradar
docker restart trendradar

# 查看 trendradar 日志
docker logs -f trendradar

# 停止 trendradar
docker-compose down trendradar
```

### 8.2 wechat-relay 管理

```bash
# 查看进程状态
ps aux | grep trendradar-wechat-relay

# 重启 relay（杀死后自动拉起或手动启动）
pkill -f trendradar-wechat-relay
python3 ~/.openclaw/workspace/scripts/trendradar-wechat-relay.py --port 8090 &

# 查看 relay 日志
tail -f /tmp/trendradar_relay.log
```

### 8.3 MCP 服务

```bash
# 测试 MCP 服务
curl http://localhost:3333/health

# 查看 MCP 日志
docker logs trendradar-mcp
```

---

## 9. 故障排查

### 9.1 微信收不到推送

```bash
# 1. 检查 relay 进程
ps aux | grep trendradar-wechat-relay

# 2. 检查 relay 日志
cat /tmp/trendradar_relay.log

# 3. 测试 relay 健康
curl http://localhost:8090/health

# 4. 检查 Hermes 微信 token 是否存在
ls ~/.hermes/weixin/accounts/
```

### 9.2 容器无法启动

```bash
# 查看容器日志
docker logs trendradar

# 检查 .env 配置
cat /home/administrator/.openclaw/workspace/TrendRadar/docker/.env

# 检查代理是否可用
curl -I --connect-timeout 5 --socks5 172.25.128.1:1080 https://www.baidu.com
```

### 9.3 代理问题

```bash
# 检查 Windows 代理状态（WSL 中）
curl -I --connect-timeout 5 --socks5 172.25.128.1:1080 https://www.baidu.com

# 检查系统代理配置
powershell.exe -Command "Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable, ProxyServer"
```

---

## 10. 配置修改

### 10.1 修改监控平台

编辑 `config/config.yaml` 中的 `platforms.sources`：

```yaml
platforms:
  enabled: true
  sources:
    - id: "toutiao"
      name: "今日头条"
    # 添加/删除平台...
```

### 10.2 修改推送关键词

编辑 `config/frequency_words.txt`，格式：

```
普通词      # 直接匹配
+必须词     # 必须包含
!过滤词     # 排除
```

### 10.3 修改定时任务

编辑 `docker/.env`：

```bash
CRON_SCHEDULE=*/30 * * * *  # 每30分钟
# 或
CRON_SCHEDULE=0 8,20 * * *  # 每天8点和20点
```

修改后重启容器：

```bash
docker restart trendradar
```

---

## 11. 安全注意

- `.env` 文件包含 API Key，**不要提交到 Git**
- `docker/.env` 已添加到 `.gitignore`
- MCP 服务 `trendradar-mcp` 仅监听 `127.0.0.1:3333`，不对外暴露

---

## 12. 参考链接

- GitHub: https://github.com/sansan0/TrendRadar
- 官方文档: https://github.com/sansan0/TrendRadar/blob/master/README.md
