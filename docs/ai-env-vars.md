# AI 凭据配置

本项目不在 `config.yaml` 提交真实 API key。请通过环境变量注入：

| 变量 | 覆盖字段 | 必填 |
|---|---|---|
| `AI_API_KEY` | `ai.api_key` | 是（生产环境） |
| `AI_API_BASE` | `ai.api_base` | 否（默认走 config.yaml） |
| `AI_MODEL` | `ai.model` | 否 |
| `AI_PROVIDER` | `ai.provider` | 否 |

加载顺序：环境变量 > `config.yaml`。

## 本地开发

```bash
export AI_API_KEY="sk-..."
export AI_API_BASE="https://api.openai.com/v1"
python -m trendradar
```

## Docker 部署

在 `docker/.env` 配置（已在 `.gitignore`）：
```
AI_API_KEY=sk-...
AI_API_BASE=https://api.openai.com/v1
```

## 安全提示

- 不要把真实 API key 提交到 git
- 如意外提交，立即在提供方后台 revoke 并 rotate
- CI/CD 使用 secrets manager 注入环境变量
