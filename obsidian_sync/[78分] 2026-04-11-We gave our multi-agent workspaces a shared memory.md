---
title: "We gave our multi-agent workspaces a shared memory agents stopped rediscovering the same bugs"
source: "r/ai_agents (New)"
link: "https://www.reddit.com/r/AI_Agents/comments/1sihpbj/we_gave_our_multiagent_workspaces_a_shared_memory/"
score: 78
category: "AI开发工具/协作平台"
date: 2026-04-11 13:11:25
tags: [reddit-need, ai开发工具/协作平台]
---

# We gave our multi-agent workspaces a shared memory agents stopped rediscovering the same bugs

> **潜力评分**：78 | **商机分类**：AI开发工具/协作平台  
> **打分理由**：痛点明确且强烈（A高分），竞争环境有一定独特性（B中等分），但开发涉及云和安全，难度中等偏高（C中等分）。

---

## 📝 需求背景 (AI 翻译)
我们为多智能体工作空间添加了共享内存，智能体不再重复发现相同错误  
我们一直在构建一个AI智能体的云桌面平台（每个智能体获得一个完整的Linux虚拟机）。我们运行三种智能体类型：Claude Code、OpenClaw、Hermes，一个工作空间可以有多个智能体在同一项目上协作。我们反复遇到的问题是：智能体A运行部署，发现NFS挂载需要特定IP。完成后，该虚拟机上的知识就消失了。下周智能体B执行部署任务时，浪费20分钟重新发现相同问题。约定、错误修复模式、部署陷阱都需要从头重新发现。工作空间从未真正学习。  
因此，我们构建了一个共享知识库。每个工作空间在主机上获得一个与Obsidian兼容的Markdown存储库，通过NFS挂载到每个智能体虚拟机。每个虚拟机上运行一个轻量级MCP服务器，提供7种工具：搜索、列表、读取、写入、删除、列出标签、查找链接。关键设计决策是采用拉取模式。智能体自行决定何时搜索和何时写入。没有人强制向它们提供上下文。  
一个即将部署的智能体搜索“部署”，在skills/deploy-pattern.md中找到约定，遵循它们，发现新的超时问题，将其写入lessons-learned/。下一个智能体会自动找到它。  
为什么使用文件而不是数据库：智能体已经读写Markdown。零学习曲线。用户可以在Obsidian中打开存储库，免费获得图形视图。虚拟机上没有凭据，MCP服务器仅执行文件I/O，因此如果虚拟机被入侵，攻击者只能在一个工作空间中读写Markdown。这就是整个爆炸半径。  
每个工作空间的存储库结构：  
_workspace/（平台管理，对智能体只读）  
agents.md 谁在活跃  
task-history.md 发生了什么以及何时发生  
skills/ 运行手册、部署模式  
memories/ 智能体学到的项目信息  
lessons-learned/ 要避免的陷阱和模式  
issues/ 发现的错误  
fixes/ 解决方案（与问题wiki链接）  
安全模型：每个文件操作都防止路径遍历，对_workspace/进行写保护（我们在自己的安全审查中确实发现了一个绕过，其中./_workspace/跳过了检查，因为路径未规范化），仅允许写入Markdown，NFS挂载时使用noexec,nosuid。  
我们考虑过使用嵌入进行搜索，但在当前存储库规模下，关键字grep效果很好。在过度设计之前，我们会观察智能体实际搜索的内容。  
我们希望实现的是：工作空间中的任何智能体至少应该知道曾在该处工作过的最聪明智能体所知道的一切。  
如果有人想要详细信息，博客文章中有完整架构（评论中有链接）。

## 💬 社区评论精华
- 博客文章包含架构细节和安全模型：https://lebureau.talentai.fr/blog/shared-knowledge-base-ai-agents

## 💡 商业价值分析
A. 痛点强度：高。AI智能体在协作时重复发现相同问题（如部署配置、错误模式），导致效率低下和资源浪费（如“浪费20分钟”），用户有强烈意愿通过付费解决方案避免此类重复劳动。  
B. 竞争环境：中等。虽然存在一些AI智能体协作平台或知识管理工具（如Obsidian），但专门为多智能体工作空间设计的轻量级、安全、拉取式共享记忆系统较少，且该方案与现有工作流（Markdown）集成度高，免费替代品不直接解决该特定痛点。  
C. 开发难度：中等偏高。核心功能（文件存储、MCP服务器、基础搜索）适合独立开发者启动，但涉及云平台、虚拟机管理、安全模型（路径遍历防护、NFS配置）和与多种AI智能体集成，复杂度较高，需要一定基础设施和安全性考量。

---
[🔗 查看 Reddit 原贴](https://www.reddit.com/r/AI_Agents/comments/1sihpbj/we_gave_our_multiagent_workspaces_a_shared_memory/)
