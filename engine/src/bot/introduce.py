"""
Bot self-introduction — group card + personal DM to each member.
Triggered via GET /introduce endpoint.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..config import load_companies, load_people
from ..destinations.lark import send_card_message, send_user_card
from ..destinations.lark_cards import _header, _text, _hr, _note

logger = logging.getLogger(__name__)


def build_intro_card_group() -> Dict[str, Any]:
    """群聊自我介绍卡片"""
    elements = []

    elements.append(_text(
        "大家好，我是 **WorkPlan Bot** — 你的 AI 邮件助手\n\n"
        "我会自动监控公司邮件、分析优先级、推送待办提醒。以下是我能帮你做的事："
    ))
    elements.append(_hr())

    elements.append(_text(
        "**📬 实时提醒**\n"
        "高优邮件第一时间私聊通知你，24小时没处理我会在群里再提醒\n\n"
        "**📋 每日待办**\n"
        "每天 9:30 给你推送个人待办清单，可以一键「已处理」或「稍后处理」\n\n"
        "**📊 每周报告**\n"
        "每周六自动生成你的个人周报：邮件量、处理进度、重点客户\n\n"
        "**💬 随时提问**\n"
        "群里 @我 或者私聊都可以，比如：\n"
        "— 「最近有什么需要处理的？」\n"
        "— 「帮我找关于XX客户的邮件」\n"
        "— 「上周有哪些高优邮件？」\n\n"
        "**📅 日历联动**\n"
        "邮件里提到的日程，我会推荐给你加到飞书日历"
    ))
    elements.append(_hr())

    elements.append(_text(
        "有任何问题直接 @我 或私聊我就行！"
    ))

    elements.append(_note(f"WorkPlan Bot · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header("👋 你好，我是 WorkPlan Bot", "purple"),
        "elements": elements,
    }


def build_intro_card_personal(person_name: str) -> Dict[str, Any]:
    """个人私聊自我介绍卡片"""
    elements = []

    elements.append(_text(
        f"Hi {person_name}，\n\n"
        "我是 **WorkPlan Bot**，你的 AI 邮件助手。从现在开始，我会帮你："
    ))
    elements.append(_hr())

    elements.append(_text(
        "**📬 紧急邮件实时通知**\n"
        "高优先邮件会第一时间推送给你，附带 AI 分析摘要\n\n"
        "**📋 每天 9:30 推送待办提醒**\n"
        "你的个人待办清单，支持一键「已处理」「稍后处理」\n\n"
        "**⏰ 24h 未处理自动升级**\n"
        "如果你没来得及处理，我会自动升级到群里提醒团队\n\n"
        "**📊 每周六推送个人周报**\n"
        "本周邮件量、任务完成率、重点客户一目了然\n\n"
        "**💬 随时向我提问**\n"
        "直接发消息给我就行，比如：\n"
        "— 「最近有什么需要处理的？」\n"
        "— 「帮我找关于报价的邮件」\n"
        "— 「这周XX客户有什么动态？」\n\n"
        "**📅 日历联动**\n"
        "检测到邮件中的日程安排，我会推荐你一键添加到飞书日历"
    ))
    elements.append(_hr())

    elements.append(_text(
        "有任何问题随时找我聊！"
    ))

    elements.append(_note(f"WorkPlan Bot · {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

    return {
        "config": {"wide_screen_mode": True},
        "header": _header("👋 你好，我是 WorkPlan Bot", "purple"),
        "elements": elements,
    }


async def send_introduce(to_group: bool = True, to_dm: bool = True) -> Dict[str, Any]:
    """
    Send bot self-introduction.
    - to_group: send intro card to all active company group chats
    - to_dm: send personal intro card to each active person via DM
    Returns summary of what was sent.
    """
    result = {"groups_sent": 0, "dm_sent": 0, "dm_failed": 0}

    # Send to group chats
    if to_group:
        companies = load_companies()
        group_card = build_intro_card_group()
        for company in companies:
            chat_id = company.get("lark_group_id")
            if not chat_id:
                continue
            msg_id = send_card_message(chat_id, group_card)
            if msg_id:
                result["groups_sent"] += 1
                logger.info(f"[Introduce] Sent group intro to {company['name']}")

    # Send personal DMs
    if to_dm:
        people = load_people()
        for person in people:
            open_id = person.get("lark_user_id")
            if not open_id or not person.get("is_active", True):
                continue
            name = person.get("name", "")
            personal_card = build_intro_card_personal(name)
            msg_id = send_user_card(open_id, personal_card)
            if msg_id:
                result["dm_sent"] += 1
                logger.info(f"[Introduce] Sent DM intro to {name}")
            else:
                result["dm_failed"] += 1

    logger.info(f"[Introduce] Done: {result}")
    return result
