# Release Checklist

每次公开发布 PosterFlow AI 前，按顺序完成以下检查。

## 数据与隐私

- [ ] `.env` 没有进入 Git
- [ ] `database/*.db` 没有进入 Git
- [ ] `uploads/` 和 `outputs/` 不包含客户文件
- [ ] 截图、演示数据和联系方式均为虚构或已匿名化
- [ ] 仓库中不存在真实 API Key、Token 或密码

## 质量

- [ ] `python -m pytest -q` 全部通过
- [ ] 应用可以启动并打开六个页面
- [ ] 演示数据脚本可以重复运行且不会重复写入
- [ ] README 的功能描述与当前实现一致
- [ ] CHANGELOG 和 ROADMAP 已更新

## Git

```bash
git status
git diff --check
git ls-files database uploads outputs .env
```

最后一条命令不应列出数据库、客户上传文件或 `.env`；目录中的 `.gitkeep` 除外。

## 发布

- [ ] 提交信息能准确说明本次改动
- [ ] GitHub Actions 测试通过
- [ ] 为稳定版本创建标签，例如 `v1.0.0`
- [ ] Release Notes 简要写明新增能力、验证结果和已知限制
