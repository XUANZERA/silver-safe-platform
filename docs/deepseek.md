# DeepSeek 行程助手配置

仓库不会保存真实 DeepSeek 密钥。后端只从运行环境读取密钥，前端也不会接触或保存密钥。

## 本地使用

1. 从示例创建本地配置：

   ```powershell
   Copy-Item .env.example .env
   ```

2. 编辑不会被 Git 跟踪的 `.env`，填入自己的密钥：

   ```dotenv
   DEEPSEEK_API_KEY=你的_DeepSeek_API_Key
   DEEPSEEK_MODEL=deepseek-v4-pro
   ```

3. 安装依赖并启动后端：

   ```powershell
   python -m pip install -r backend\requirements.txt
   python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
   ```

4. 启动前端，并确保 `VITE_API_BASE_URL` 指向后端的 `/api/v1`。使用老人演示账号登录后，在首页打开“AI 行程管家”即可对话。

## 验证

在已经设置 `DEEPSEEK_API_KEY` 的终端执行：

```powershell
python scripts\test_deepseek.py
```

成功时会显示模型名和 `DEEPSEEK_API_OK`。也可以登录后调用 `POST /api/v1/ai/chat`；该接口需要访问令牌。

## 部署

在服务器、容器平台或 CI/CD 的 Secret/Environment Variables 中配置 `DEEPSEEK_API_KEY`，不要写进 Dockerfile、前端环境变量、日志或提交记录。更换密钥后重启后端进程即可生效。
