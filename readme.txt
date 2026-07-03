这是一个自动邮件回复工具，已改为通用版本并添加 AI 回复开关。

配置（config.json）中新增字段：
- `USE_AI_REPLY`：true/false，开启后将调用 AI 生成回复内容（优先）。
- `AI_PROVIDER`：目前支持 `openai`。
- `OPENAI_MODEL`：OpenAI 模型名称（如 `gpt-3.5-turbo`）。

注意：使用 OpenAI 时请通过环境变量 `OPENAI_API_KEY` 提供 API Key，避免将密钥写入仓库。

运行：
1. 安装依赖：
```
pip install -r requirements.txt
```
2. 配置 `config.json`（包括邮箱及规则），如需 AI 回复，将 `USE_AI_REPLY` 设为 `true` 并确保设置了 `OPENAI_API_KEY`。 
3. 运行：
```
python autoEmailReturn.py
```

开源说明：你可以将本仓库发布到 GitHub，记得不要把 `processed_uids.txt`、`last_check_time.txt` 或包含敏感信息的 `config.json`（若含密码）提交到公开仓库，建议在 `.gitignore` 中排除这些文件。