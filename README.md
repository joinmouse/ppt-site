# Kimi PPT 提交站（ppt-site）

带**一次性邀请链接**的 PPT 生成提交网站：管理员批量生成链接发放，用户打开链接填写需求提交，链接即刻作废；生成过程在状态页排队展示，完成后提供下载。

## 功能

- **一次性 hash 链接**：`/submit?h=<hash>`，数据库原子消费，同一链接重复提交返回 409
- **提交页**：PPT 描述、参考资料上传（≤50 个 / 单个 ≤100MB）、页数分段选择、风格二选一
- **状态页**：`/status/{job_id}` 每 5 秒轮询，排队位置 / 生成中计时 / 完成下载 / 失败原因
- **管理后台**：`/admin`，Admin Token 登录，批量生成 1–500 个链接、一键复制、按状态过滤、用量统计
- **生成适配层**：`app/kimi_client.py`，配置 `KIMI_WEB_KEY` 走真实生成，未配置自动 mock 模式（全流程可演示）

## 截图

| 提交页 | 生成完成 | 已使用链接 |
|---|---|---|
| ![submit](docs/submit.png) | ![done](docs/status-done.png) | ![used](docs/used-link.png) |

## 快速开始

```bash
docker build -t ppt-site .
docker run -p 8000:8000 \
  -e ADMIN_TOKEN=换成一个长随机串 \
  -e KIMI_WEB_KEY=你的kimi网页版key \
  ppt-site
```

本地开发：

```bash
pip install -r requirements.txt pytest
ADMIN_TOKEN=dev123 uvicorn app.main:app --reload
# 后台: http://localhost:8000/admin  （输入 dev123）
```

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `ADMIN_TOKEN` | 是 | 管理后台令牌，未配置时 /admin 接口返回 503 |
| `KIMI_WEB_KEY` | 否 | kimi.com 网页版 key；留空为 mock 模式 |
| `DATA_DIR` | 否 | 数据目录（上传文件），默认 `data` / 容器内 `/data` |
| `DB_PATH` | 否 | SQLite 路径，默认 `$DATA_DIR/ppt-site.db` |

## 一次性链接流程

```
管理员 /admin ──生成 N 个 hash──▶ hashes 表(used=0)
                                     │ 发放 /submit?h=xxx
用户打开 ──check──▶ used=1? ──是──▶ “链接无效或已使用”
                     │否
                 填写表单提交
                     │ UPDATE ... WHERE hash=? AND used=0 （原子）
                     ├─ 影响 1 行 → 创建 job → 跳状态页
                     └─ 影响 0 行 → 409（并发/重复使用被拦截）
worker ──▶ queued → running → done(下载) / failed(原因)
```

## 接入真实 Kimi 生成

`app/kimi_client.py` 顶部有说明：kimi.com 网页版 PPT 接口为非公开接口，部署前请按自己浏览器会话核实 endpoint 与参数后填入，密钥只存于服务端环境变量，绝不下发前端。

## 测试

```bash
pip install pytest
pytest tests/ -q
```
