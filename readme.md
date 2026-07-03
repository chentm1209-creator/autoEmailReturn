这是一个自动邮件回复工具，基于规则自动回复符合条件的来信。

运行：
1. 安装依赖：
```
pip install -r requirements.txt
```
2. 配置 `config.json`（包括邮箱及规则）。
3. 运行：
```
python autoEmailReturn.py
```

**配置说明（config.json 字段）**

- `EMAIL_ACCOUNT`：用于收发邮件的邮箱地址（发送方账号）。
- `EMAIL_PASSWORD`：对应邮箱的密码或应用专用密码（不要把它提交到仓库）。
- `POP3_SERVER`：接收邮件所用的 POP3 服务器地址（例如 `pop.example.com`）。
- `SMTP_SERVER`：发送邮件所用的 SMTP 服务器地址（例如 `smtp.example.com`）。
- `ALLOWED_SENDER`：白名单发件人地址或地址片段；只有来自该发件人的邮件才会被处理。留空则不按发件人过滤。
- `CC_LIST`：发送回复时要抄送的邮箱列表（数组）。
- `SLEEP_TIME`：轮询检查新邮件的间隔，单位为秒。
- `REPLY_RULES`：基于关键字的固定回复规则，格式为 {"关键字": "回复内容"}；脚本会在邮件的主题（Subject）中匹配关键字并使用对应回复，**不会匹配邮件正文**。
- `DEFAULT_REPLY`：当没有匹配到任何规则时的默认回复文本。

`config.example.json` 已提供一个可复制的示例配置模板，建议复制为 `config.json` 并填入你的账号与服务器信息。
