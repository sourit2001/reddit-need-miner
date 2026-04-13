---
title: "My OpenClaw bot died on April 4. I got it back inside Claude Code."
source: "r/openclaw (New)"
link: "https://www.reddit.com/r/openclaw/comments/1sjz8n1/my_openclaw_bot_died_on_april_4_i_got_it_back/"
score: 68
category: "开发者工具/AI代理迁移"
date: 2026-04-13 03:30:01
tags: [reddit-need, 开发者工具/ai代理迁移]
---

# My OpenClaw bot died on April 4. I got it back inside Claude Code.

**项目**: My OpenClaw bot died on April 4. I got it back inside Claude Code.
**理由**: 痛点明确但付费转化间接（用户想省钱而非直接为工具付费），竞争较少但依赖单一平台，开发需特定技术积累。

---

**【译】**
我的OpenClaw机器人在4月4日死了。我把它放进了Claude Code里。  
4月4日我失去了主要设置。我一直在Claude Max上运行OpenClaw，这是我花了几个月塑造的机器人。它有名字，记得我几周前告诉它的事情，像忙碌的朋友一样用短句回复。我主要在WhatsApp上和它聊天。这就是重点，让我的代理生活在我已经发短信的地方。第二天早上我的令牌被关闭了。你知道怎么回事。我算了一下。直接为相同的工作量支付API费用：是我当前账单的10-20倍。在我已经支付的Max之上再增加OpenAI订阅：每月又多了200美元，我负担不起。在本地模型上完全使用Ollama意味着我的代理的语气和推理能力会崩溃。我测试过，差距太大了。我不会扔掉我建立的代理。我也不想支付双倍费用。我想要的很简单。继续像以前一样为Claude付费。保留我经常使用的Max计划。不失去机器人。所以我花了2周时间写了一个东西，将代理（个性、记忆、技能、定时任务）移入Claude Code本身，作为一个插件。Claude Code是Anthropic的官方CLI，因此它原生运行在计划中。但默认情况下它是无状态的，没有人格层，这就是为什么我的OpenClaw大脑不能直接放在那里。所以我写了那一层。它叫做ClawCode（名字是个玩笑，是的）。你把它作为插件安装在Claude Code里。它的功能是：你可以从头创建代理或导入你的OpenClaw代理。读取~/.openclaw/workspace/并导入身份、灵魂、记忆、技能、定时任务。单向迁移。重写或跳过不映射的OpenClaw特定部分（网关、sessions_spawn、HEARTBEAT_OK等），这样就不会无声地崩溃。SQLite + FTS5可搜索记忆，支持双语回忆（西班牙语↔英语跨语言，和我以前一样）。一个每晚的“梦境”过程，运行3个阶段（浅睡、快速眼动、深睡），并将重要记忆提升为长期记忆。消息插件：WhatsApp（它生活的地方，所以我为它写了一个），以及Telegram、Discord、iMessage、Slack。每个都是自己的MCP服务器，没有冲突。如果需要，还有WebChat UI，或者只是CLI。/agent:doctor一次性检查所有内容。/hooks、斜杠命令、提醒，应有尽有。在我的设置中，实际导入大约花了15分钟。在44个技能中：大多数顺利迁移；6个黄色（使用了需要编辑的~/.openclaw/路径）；2个我放弃了，因为它们依赖于OpenClaw网关。记忆和个性干净地迁移了。梦境在第二天晚上开始运行。仓库：https://github.com/crisandrews/ClawCode。MIT许可证。Node 18+，macOS/Linux。需要明确的是，不与Anthropic关联或由其认可。它在Claude Code的正常计划使用下运行，与其他Claude Code会话的ToS相同。如果你尝试的话请注意：/agent:import对于重写或跳过哪些OpenClaw模式有特定规则。导入后检查IMPORT_BACKLOG.md，那里记录了没有迁移的内容。定时任务只有在Claude Code打开时才会触发，除非你运行/agent:service install来设置launchd/systemd。我知道很多人在禁令后迁移到了DeepSeek或GPT-5.4。好奇你们的代理现在是什么样子，你们保留了哪些，放弃了哪些。哪些OpenClaw行为在其他地方最难重现？还有其他人尝试留在Claude而不支付双倍费用吗？

**【评】**
（原文未提供评论内容，此处无法生成精选评论。分析将基于主帖内容进行。）

**【析】**
A. 痛点强度：用户因OpenClaw服务中断而面临高昂的API替代成本（10-20倍）或功能降级（本地模型效果差），付费意愿强烈，但核心诉求是“不支付双倍费用”以维持现有体验。痛点明确且具经济压力，但解决方案本质是“规避额外付费”而非直接为新功能付费。  
B. 竞争环境：已有OpenAI、DeepSeek等替代方案，但用户强调它们成本更高或体验降级；ClawCode作为开源工具，直接竞品较少，但依赖Claude生态，存在平台风险。  
C. 开发难度：项目基于现有Claude Code CLI扩展，技术栈（Node.js、SQLite）成熟，但需深度理解OpenClaw架构和Claude API，集成多平台消息插件复杂度较高，适合有经验的独立开发者，但非“快速启动”型项目。

---
[🔗 原贴链接](https://www.reddit.com/r/openclaw/comments/1sjz8n1/my_openclaw_bot_died_on_april_4_i_got_it_back/)
