---
title: "Built an AI cycling coach that connects to my Garmin - decided to open-source it"
source: "r/SideProject (New)"
link: "https://www.reddit.com/r/SideProject/comments/1skwexa/built_an_ai_cycling_coach_that_connects_to_my/"
score: 68
category: "开源工具/健康健身科技"
date: 2026-04-14 02:59:01
tags: [reddit-need, 开源工具/健康健身科技]
---

# Built an AI cycling coach that connects to my Garmin - decided to open-source it

**项目**: Built an AI cycling coach that connects to my Garmin - decided to open-source it
**理由**: 痛点明确但付费意愿受开源冲击，竞争环境较复杂，开发难度低但变现路径模糊。

---

**【译】**
我构建了一个连接Garmin的AI骑行教练，并决定将其开源。  
这个业余项目以最好的方式失控了。我热爱骑行，但厌倦了所有AI教练应用都是按月收费的“黑箱”。于是我用一个周末自己开发了一个。它连接intervals.icu（一个与Garmin/Wahoo/Zwift同步的免费平台），拉取你的真实训练数据，并使用LLM进行教练指导。你可以在Telegram上与其聊天（可选）。有趣的是：整个教练“大脑”只是可编辑的Markdown文件。不喜欢它处理恢复的方式？打开skills/recovery.md修改即可。训练计划逻辑是纯TypeScript函数——没有魔法，没有隐藏提示。技术栈：TypeScript、Vercel AI SDK、grammY（Telegram）、Zod、intervals.icu API BYOK——自带API密钥（Claude、GPT或Gemini）。无后端、无账户，可在本地运行。这是Alpha版本——我正用它进行自己的训练，效果不错，但还有很多改进空间。欢迎任何构建业余项目或热爱骑行（或两者兼有）的人反馈。GitHub：https://github.com/yerzhansa/cycling-coach 处理intervals.icu的包：https://www.npmjs.com/package/intervals-icu-api

**【评】**
（原文未提供评论，基于帖子内容模拟）  
*“作为数据科学家和骑行爱好者，我受够了那些说不清理由的AI训练计划。这个项目的可编辑Markdown设计太棒了——我终于能把自己的运动科学知识嵌进去了！”*

**【析】**
1. **具体场景**：骑行爱好者使用Garmin等设备记录训练数据，但缺乏个性化、透明的AI教练服务。用户希望基于历史数据获得实时指导（如训练计划、恢复建议），同时避免订阅费和“黑箱”算法。  
2. **痛点根源**：现有AI骑行教练应用多为封闭式订阅制，费用高（通常月费10-30美元）、逻辑不透明，且无法自定义规则，导致用户对建议缺乏信任和控制权。  
3. **现有工具哪里掉链子了**：主流应用（如TrainerRoad、Zwift的AI功能）依赖固定算法，用户无法调整核心逻辑；免费替代品（如Strava基础版）缺乏深度AI分析；开源工具则通常需要较高技术门槛。  
4. **付费商机评估**：痛点真实但付费意愿分化——硬核骑手可能愿意为透明可控的解决方案付费（尤其是一次性买断），但开源模式本身削弱了直接变现潜力。机会点在于提供“开源核心+托管服务”的混合模式（如云部署、高级数据洞察），或面向企业定制（如骑行俱乐部、教练机构）。

---
[🔗 原贴链接](https://www.reddit.com/r/SideProject/comments/1skwexa/built_an_ai_cycling_coach_that_connects_to_my/)
