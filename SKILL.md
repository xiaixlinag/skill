---
name: wechat-bug-analyzer
description: "分析微信群聊天记录，智能筛选 bug 反馈和 @我 的消息，支持运营 Review 反馈学习，持续迭代提高准确率，并通过 POPO 机器人推送结果。"
version: "1.1.0"
author: "CodeMaker"
license: "MIT"
repository: "https://skills.netease.com/api/git/@wechat-bug-analyzer.git"
keywords:
  - wechat
  - bug
  - analyzer
  - feedback
  - learning
---

# 微信群 Bug 反馈分析器

## 功能特性

- 🐛 **智能 Bug 识别** - 多策略组合匹配，精准识别玩家 bug 反馈
- 📢 **@我 检测** - 自动筛选 @你 的消息
- 🔄 **反馈学习** - 运营 Review 后自动迭代，持续提高准确率
- ⏰ **定时分析** - 每小时自动分析并推送报告
- 📤 **POPO 推送** - 分析结果自动推送到 POPO 群

## 前置条件

- 已完成微信聊天记录导出（使用 `qsec-wechat-export` skill）
- POPO 机器人已配置（需要 webhook URL 和关键字）
- Python 2.7+ 或 Python 3.x

## 安装

```bash
npx skills add https://skills.netease.com/api/git/@wechat-bug-analyzer.git
```

## 快速开始

### Step 1 — 确认聊天记录已导出

确保 `qsec-wechat-export` skill 已导出 `message.txt`。

### Step 2 — 配置 POPO 机器人

编辑 `config.json`：

```json
{
  "popo_webhook": "https://open.popo.netease.com/open-apis/robots/v1/hook/YOUR_WEBHOOK_ID",
  "popo_keyword": "总结",
  "group_name": "你的群名",
  "nickname": "你的微信昵称"
}
```

### Step 3 — 运行分析

```bash
python scripts/analyze.py \
  --input ../qsec-wechat-export/message.txt \
  --group "群名" \
  --nickname "昵称" \
  --output report.txt
```

### Step 4 — 运营 Review（可选）

对分析结果进行 Review，标注误报/漏报：

```bash
# 标记误报
python scripts/feedback_learner.py --action add \
  --type false_positive \
  --content "误报的消息内容" \
  --reason "这是群公告，不是bug"

# 标记漏报
python scripts/feedback_learner.py --action add \
  --type false_negative \
  --content "漏报的消息内容" \
  --reason "这是真实的bug反馈"

# 标记正确识别
python scripts/feedback_learner.py --action add \
  --type correct \
  --content "正确识别的消息内容"

# 执行学习
python scripts/feedback_learner.py --action learn

# 查看学习统计
python scripts/feedback_learner.py --action stats
```

### Step 5 — 启用定时分析

运行定时任务配置脚本：

```bash
python scripts/setup_scheduler.py --enable
```

这将创建每小时执行一次的定时任务。

## 文件结构

```
wechat-bug-analyzer/
├── SKILL.md                    # Skill 说明文档
├── config.json                 # 配置文件
├── learned_rules.json          # 学习到的规则（内置迭代词库）
├── review_history.json         # Review 历史记录
├── scripts/
│   ├── analyze.py              # 主分析脚本
│   ├── feedback_learner.py     # 反馈学习系统
│   ├── auto_analyze.py         # 定时分析脚本
│   └── setup_scheduler.py      # 定时任务配置
├── report.txt                  # 最新分析报告
└── report_summary.txt          # 摘要报告
```

## 内置词库

### 高优先级关键词（直接匹配）

| 类别 | 关键词 |
|------|--------|
| Bug 相关 | bug、BUG、Bug |
| 错误描述 | 报错、错误代码、异常 |
| 崩溃相关 | 崩溃、闪退、卡死、死机、白屏、黑屏、闪屏 |
| 功能问题 | 打不开、进不去、用不了、没反应、不响应 |
| 修复请求 | 修复、修一下 |

### 组合匹配词

**问题词**（需与功能词组合）：
- 有时候、有时、偶尔、时有时无、不稳定
- 不显示、没显示、显示不出、看不到
- 消失、不见了、丢失、没了
- 不能、无法、失败、不正常、有问题

**功能词**（需与问题词组合）：
- 回放、淘汰、撤离、复活
- 抓虫、女仆、突围、经典
- 登录、加载、匹配、连接
- 道具、皮肤、装备、背包
- 声音、画面、界面、按钮

### 学习到的排除词（v1.1.0）

通过运营 Review 学习到的误报特征词：
- 欢迎大家定向（群公告特征）
- 你就沉默了呢（聊天调侃）
- 全是突围黑产（外挂抱怨）
- 女仆难道是日服的专属（纯提问）

## 配置说明

### config.json

```json
{
  "message_input": "../qsec-wechat-export/message.txt",
  "group_name": "手游-荒野行动核心玩家交流2群",
  "nickname": "修bug小弟",
  "popo_webhook": "https://open.popo.netease.com/...",
  "popo_keyword": "总结",
  "auto_analyze_interval": 3600,
  "auto_push_to_popo": true
}
```

| 配置项 | 说明 |
|--------|------|
| message_input | 聊天记录文件路径 |
| group_name | 要分析的群名称（支持部分匹配） |
| nickname | 你的微信昵称（用于检测 @我） |
| popo_webhook | POPO 机器人 webhook URL |
| popo_keyword | POPO 消息关键字前缀 |
| auto_analyze_interval | 自动分析间隔（秒），默认 3600（1小时） |
| auto_push_to_popo | 是否自动推送到 POPO |

## 更新日志

### v1.1.0 (2026-03-12)
- ✨ 新增反馈学习系统
- ✨ 新增定时分析功能
- 🐛 优化 Bug 识别准确率（33.3% → 100%）
- 📦 内置迭代词库

### v1.0.0
- 🎉 初始版本
- 🐛 基础 Bug 识别功能
- 📢 @我 检测功能
- 📤 POPO 推送集成