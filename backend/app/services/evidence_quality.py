"""T08.0 P0-2 EvidenceQualityGate：导航/footer/热线类内容不得成为 Signal Evidence。

Evidence 必须引用真正支持 Signal 的原文（采购单位/项目名称/预算金额/公告时间/
采购品目/事件事实句）。低质模式 reject，并在证据生成前拦截。
"""
from __future__ import annotations

import re

# 导航/footer/平台介绍特征（整段主要由这些词构成 → reject）
_NAV_NOISE_PATTERN = re.compile(
    r"(首页|政采法规|购买服务|监督检查|信息公告|国际专栏|当前位置|网站地图|无障碍|"
    r"登录|注册|收藏本站|设为首页|服务热线|客服热线|投诉电话|版权所有|备案号|"
    r"ICP备|公网安备|技术支持|官方网站|唯一指定|国家级政府采购专业网站|"
    r"招标|中标|采购|公告){1}",
)
# 单独出现"招标/采购/公告"等业务词不能救活整段噪音，必须看噪音密度
_NAV_TOKENS = (
    "首页", "政采法规", "购买服务", "监督检查", "信息公告", "国际专栏", "当前位置",
    "网站地图", "无障碍浏览", "登录", "注册", "收藏本站", "设为首页", "服务热线",
    "客服热线", "投诉电话", "服务投诉", "版权所有", "备案号", "ICP备", "公网安备",
    "技术支持", "财政部唯一指定", "政府采购专业网站", "信息网络发布媒体",
    "唯一指定", "政府采购信息网络发布媒体", "统计信息", "举报", "温馨提示",
)
_MIN_SUBSTANTIVE_LENGTH = 12
_HOTLINE_PATTERN = re.compile(r"(\d{3,4}-\d{3,4}-?\d{3,4}|\d{3,4}-?\d{7,8}|1[3-9]\d{9}|400-?\d{2,4}-?\d{3,4})")
# T08.2：菜单条带特征 —— 多个 2~8 字纯中文词以空白分隔、无任何标点（"新闻资讯 展会资讯 交付案例 公司动态"）
_MENU_STRIP_PATTERN = re.compile(
    r"[\u4e00-\u9fffA-Za-z]{2,10}(\s+[&/|]?[\u4e00-\u9fffA-Za-z]{2,10}){5,}"
)


def _is_menu_strip(cleaned: str) -> bool:
    """疑似站点导航菜单条带：多短词空白分隔、无句读、无数字细节。
    该类片段即使词表未收录（各站菜单不同）也应拒绝作为证据。"""
    if "。" in cleaned or "！" in cleaned or "？" in cleaned or "，" in cleaned or "、" in cleaned:
        return False
    if not _MENU_STRIP_PATTERN.search(cleaned):
        return False
    # 菜单条带通常无数字/金额等事实细节
    facts = re.findall(r"\d+(?:\.\d+)?", cleaned)
    return len(facts) <= 1


def evaluate_evidence(text: str | None) -> tuple[bool, list[str]]:
    """评估 Evidence 质量。返回 (通过, reject 理由列表)。

    reject 条件（任务书 P0-2）：主要由导航/footer/网站介绍/服务热线组成。
    """
    reasons: list[str] = []
    if not text or not text.strip():
        return False, ["evidence 为空"]
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) < _MIN_SUBSTANTIVE_LENGTH:
        reasons.append(f"evidence 过短（<{_MIN_SUBSTANTIVE_LENGTH} 字）")

    # 噪音 token 密度：出现的导航/热线 token 数占片段"词"的大致比例
    nav_hits = [token for token in _NAV_TOKENS if token in cleaned]
    if nav_hits:
        # 把噪音 token 从文本中移除后，看剩余实质内容
        residual = cleaned
        for token in nav_hits:
            residual = residual.replace(token, " ")
        # 分隔符（含全角箭头/冒号）与热线号码不计入实质内容
        residual_no_phone = _HOTLINE_PATTERN.sub(" ", residual)
        residual_len = len(re.sub(r"[\s|｜/·>》»>-：:（()）￥¥0-9.]+", "", residual_no_phone))
        # 剩余实质字符过少 → 整段就是导航/footer/热线
        if residual_len < max(_MIN_SUBSTANTIVE_LENGTH, int(len(cleaned) * 0.3)):
            reasons.append(f"evidence 主要由导航/页脚/热线组成（命中：{'、'.join(nav_hits[:5])}）")

    # 电话号码密集（服务热线块）：号码多且实质文字少
    phones = _HOTLINE_PATTERN.findall(cleaned)
    prose_len = len(re.sub(r"[\d\s\-—()（）+：:｜|/|.，,]+", "", cleaned))
    if len(phones) >= 2 and prose_len < 30:
        reasons.append("evidence 主要由电话/热线号码组成")

    # 中文字符多样性过低（重复字符堆砌）
    chinese = re.findall(r"[\u4e00-\u9fff]", cleaned)
    if len(chinese) >= 10 and len(set(chinese)) / len(chinese) < 0.25:
        reasons.append("中文字符多样性过低（疑似噪音堆砌）")

    # T08.2：站点导航菜单条带（词表无法穷举，按结构特征识别）
    if _is_menu_strip(cleaned):
        reasons.append("evidence 疑似站点导航菜单条带（多短词空白分隔无句读）")

    return (len(reasons) == 0), reasons


def is_platform_boilerplate(text: str | None) -> bool:
    """快捷判断：整段是否平台样板文字（首页/热线/版权）。"""
    ok, _ = evaluate_evidence(text)
    return not ok


_SENTENCE_SPLIT = re.compile(r"(?<=[。！？；;])|\n")


def extract_valid_evidence(text: str | None, match_start: int, match_end: int, *, window: int = 60) -> str | None:
    """从原文为信号匹配提取有效 Evidence（P0-2 接入点）。

    优先取匹配点所在句（导航噪音句 reject 时向后找下一个实质句）；
    全部低质返回 None —— 该信号命中因无有效证据而放弃，绝不把导航当证据。
    """
    if not text:
        return None
    body = text[:60_000]
    start = max(0, match_start - window)
    end = min(len(body), match_end + window)
    candidate = body[start:end].strip()
    ok, _ = evaluate_evidence(candidate)
    if ok:
        return candidate

    # 低质窗口：按句扫描，找包含匹配关键词区域所在/之后的第一个实质句
    keyword = body[match_start:match_end]
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(body) if s.strip()]
    offset = 0
    for sentence in sentences:
        sentence_end = offset + len(sentence)
        if sentence_end >= match_end and keyword in sentence:
            ok_sentence, _ = evaluate_evidence(sentence)
            if ok_sentence:
                return sentence[:400]
        offset = sentence_end
    # 关键词句本身低质（如导航行）→ 只接受"含匹配关键词核心"的实质句兜底。
    # T08.2 修复：不得把任意含业务词的句子（如岗位JD）配给不相关匹配 —— 无亲和句则放弃。
    core = keyword.strip()
    if len(core) >= 2:
        for sentence in sentences:
            if core not in sentence:
                continue
            ok_sentence, _ = evaluate_evidence(sentence)
            if ok_sentence and len(sentence) >= _MIN_SUBSTANTIVE_LENGTH:
                return sentence[:400]
    return None
