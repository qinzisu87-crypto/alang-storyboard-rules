# -*- coding: utf-8 -*-
"""《阿良的分镜制作规则》三层文件机械自检。

用法：
    python check_rule.py --project <项目目录> --ep EP001
    跳过剧本（R33）：加 --skip-script，此时不要求 剧本.md，改查分镜场标题的来源

通过时退出码 0，有 FAIL 时退出码 1。
只查机械项；「段尾停得住」「拍摄手法有理由」这类判断项在结尾以「人工核对」列出。
"""
import argparse
import json
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

RE_SCENE_ID = re.compile(r"^##\s*(EP[A-Za-z0-9]+-SC[A-Za-z0-9]+)\b", re.M)
RE_DIALOGUE = re.compile(r"^([^\s：:\[\]#]{1,8})[：:]\s*(\S.*)$", re.M)
RE_BOARD_SCENE = re.compile(r"^##\s*第\s*(\d+)\s*场\s*[｜|]\s*(.+)$", re.M)
RE_SHOT = re.compile(r"^###\s*镜头\s*(\d+-\d+)\s*[｜|]\s*(.+)$", re.M)
RE_SEG = re.compile(r"^##\s*第\s*(\d+)\s*段\s*(?:[｜|]\s*(.+))?$", re.M)
RE_SEG_SECTION = re.compile(r"^([a-z_]+)\s*:\s*$", re.M)
RE_SHOT_TAG = re.compile(r"\[Shot\s+\d+\]")
RE_SUBJECT = re.compile(r"<Subject\s+\d+>")
RE_PICTURE = re.compile(r"<Picture\s+\d+>")
RE_SPEAKER = re.compile(r"\(S\d+(?:,[^)]*)?\)")
RE_DIALOG_TAG = re.compile(r"<d>\s*\[[^\]]+\][^<]*</d>")
TIME_CODE_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")

SHOT_FIELDS = ["拍摄手法", "动作", "动作先后", "表情", "自然规律", "声音", "台词", "参考图", "提示词"]
# 分段元数据行（供审阅对账，不贴给工具）；可贴给工具的六段标题在 SEG_SECTIONS 里单独校验
SEG_FIELDS = ["时长", "场景与轴线", "表演参考", "参考图", "标签映射", "说话人"]
SEG_SECTIONS = ["subject_definitions", "summary", "retention_analysis",
                "detailed_description", "overall_soundscape", "non_diegetic_music"]
SEG_TASK_TYPES = ["keyframe completion", "reference generation", "video editing",
                  "video continuation", "audio reuse", "audio reference"]
VIS_MARKERS = ["fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference"]
AUD_MARKERS = ["fully_copy", "partially_copy", "reference", "weak_reference"]
MONO_WORDS = ("内心", "独白", "VO", "画外音")
MOUTH_CONFLICT = ("嘴唇开始动", "说完合上", "嘴唇开合", "嘴唇张开", "嘴巴张开")
MOUTH_CLAUSE = "其他角色嘴唇闭合"
MUSIC_RE = re.compile(r"(BGM|bgm|背景音乐|背景纯音乐|纯音乐|垫乐|配乐)")
SLOT = re.compile(r"@图片\s*(\d+)")
RE_SCENE_ASSET_BLOCK = re.compile(r"^##\s*(S\d{2})\s*(.*)$", re.M)

SCENE_A_ITEMS = ["场景基础资料", "场景全景图", "正面视图", "侧面视图", "背面视图",
                 "平面布局图", "俯视图", "空间尺寸", "空间坐标",
                 "建筑细节", "门窗细节", "墙面细节", "地面细节"]
SCENE_B_ITEMS = ["固定家具", "可移动道具", "剧情道具", "清晨", "夜晚",
                 "晴天", "雪天", "墙面材质", "地面材质", "道具材质",
                 "远景", "中景", "近景", "摄影机运动",
                 "固定空间规则", "道具位置规则", "场景变化状态", "镜头连续性规范"]


def scan_music(text, where, fails, require_off=True, allow=False):
    """R25：默认零配乐。约束行（第一行）里的「无配乐…」不算，其余位置出现配乐词即报错。
    用户当次点名配乐时（声音栏带「用户指定」），放行。"""
    if allow or "用户指定" in text:
        return
    if require_off and "无配乐" not in text:
        fails.append("%s 缺「无配乐」声明（R25：不许主动配乐）" % where)
    lines = text.splitlines()
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
    for m in MUSIC_RE.finditer(body):
        ctx = body[max(0, m.start() - 6): m.end() + 2]
        if re.search(r"[无不禁非]", ctx):
            continue
        fails.append("%s 出现未经用户点名的配乐描述「%s」（R25 不许主动配乐）" % (where, m.group(0)))
        break


GAZE_RE = re.compile(
    r"(直视镜头|看向镜头|望向镜头|对着镜头|盯住镜头|盯紧镜头|锁住镜头"
    r"|找镜头|迎镜头|追镜头|目视镜头|注视镜头|镜头即"
    r"|眼睛[^，。；\n不]{0,4}镜头|目光[^，。；\n不]{0,4}镜头|眼神[^，。；\n不]{0,4}镜头"
    r"|眼球[^，。；\n不]{0,4}镜头|瞳孔[^，。；\n不]{0,4}镜头"
    r"|看向观众|望向观众|直视观众|对着观众"
    r"|第一人称主观|主观视角|视线[^，。；\n]{0,6}镜头)"
)
DIALOGUE_LINE = re.compile(r"^\s*(?!约束|起幅|切\s*[：:]|转场|镜头|画面)[^\s：:（]{1,8}(?:（[^）]*）)?[：:]")
BODY_RE = re.compile(r"(眉|眼|嘴|唇|下颌|下巴|喉|呼吸|手|指|肩|背|腰|膝|脚|腿|臂|腕|掌|视线|目光|重心|肌肉|咬肌|瞳孔|眼睑)")
BODY_RE_EN = re.compile(r"(eye|eyes|eyelid|pupil|gaze|brow|jaw|lip|lips|mouth|throat|breath|shoulder|hand|finger|wrist|palm|weight|neck|tendon|chin|face|spine|knee|foot)", re.I)
CJK = re.compile(r"[\u4e00-\u9fa5]")


def check_no_timecode(pr, where, fails):
    """R13：分镜提示词不写时间码；分段层按官方 Ref2VA 切点，不套本函数。"""
    hits = [(i, m.group(0)) for i, l in enumerate(pr.splitlines(), 1)
            for m in TIME_CODE_RE.finditer(l)]
    for line_no, code in hits[:3]:
        fails.append("%s 第 %d 行出现时间码「%s」（R13 分镜提示词不写时间码）" % (where, line_no, code))
    if len(hits) > 3:
        fails.append("%s 另有 %d 处时间码，未逐条列出（R13）" % (where, len(hits) - 3))
    return len(hits)


def _seg_sections(body):
    """把一段分段正文按官方字段行切开，返回 {段名: 正文}。"""
    hits = list(RE_SEG_SECTION.finditer(body))
    d = {}
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
        d[h.group(1)] = body[h.end():end]
    return d


def check_segment_sections(body, where, fails, warns):
    """R20：官方 Ref2VA 六段字段齐全、顺序固定、六段前无约束段；detailed_description 不成分镜缩写（R51）。"""
    sec = _seg_sections(body)
    hits = list(RE_SEG_SECTION.finditer(body))
    if not hits:
        fails.append("%s 没有官方六段字段行（应为 subject_definitions: 这种写法，不用 ###，R20）" % where)
        return sec
    first_pos = hits[0].start()
    prefix = body[:first_pos]
    if "约束" in prefix:
        fails.append("%s 六段前加了中文约束段；官方六段前不许加额外段（R20／R52）" % where)
    if re.search(r"^###\s*[a-z_]+\s*$", body, re.M):
        fails.append("%s 六段用了 ### 标题；官方要求字段行 subject_definitions: 这种写法（R20）" % where)
    order = [h.group(1) for h in hits if h.group(1) in SEG_SECTIONS]
    if order[:len(SEG_SECTIONS)] != SEG_SECTIONS:
        fails.append("%s 六段顺序不对：当前 %s；应为 %s（R20）"
                     % (where, " / ".join(order) or "无", " / ".join(SEG_SECTIONS)))
    missing = [x for x in SEG_SECTIONS if x not in sec]
    if missing:
        fails.append("%s 缺六段：%s（R20 六段缺一不可）"
                     % (where, "、".join(x + ":" for x in missing)))
        return sec

    detail = sec["detailed_description"]
    if not RE_SHOT_TAG.search(detail):
        fails.append("%s detailed_description 缺 [Shot N] 镜头编号（R20）" % where)
    if not any(BODY_RE.search(l) or BODY_RE_EN.search(l) for l in detail.splitlines()):
        fails.append("%s detailed_description 没有任何表情肌／身体／视线细节（R51 不是分镜缩写）" % where)

    subj_def = sec["subject_definitions"]
    subj_used = set(RE_SUBJECT.findall(detail))
    subj_decl = set(RE_SUBJECT.findall(subj_def))
    if subj_decl and not subj_used:
        fails.append("%s subject_definitions 定义了 %s，但 detailed_description 没有引用 <Subject N>（R53 标签一致）"
                     % (where, "、".join(sorted(subj_decl))))

    # <Picture N> 只允许当首帧/尾帧/关键帧/构图锚点/故事板；人物三视图、场景图只作主体来源
    for line in subj_def.splitlines():
        st = line.strip()
        if re.match(r"<Picture\s+\d+>\s*[:：]", st):
            if not re.search(r"(first frame|last frame|tail frame|key frame|keyframe|storyboard|composition anchor|start frame|end frame|首帧|尾帧|关键帧|构图锚点|故事板)", st, re.I):
                fails.append("%s 单独定义了 <Picture N>，但没写它作为首帧/尾帧/关键帧/构图锚点/故事板；人物/场景/道具参考图应折进 <Subject N>（R20）" % where)

    summary = sec["summary"].strip()
    m = re.match(r"\[([^\]]+)\]", summary)
    if not m:
        fails.append("%s summary 没有以方括号任务类型开头，例如 [reference generation]（R20）" % where)
    else:
        tasks = [t.strip() for t in re.split(r"\+|,", m.group(1)) if t.strip()]
        bad = [t for t in tasks if t not in SEG_TASK_TYPES]
        if bad:
            fails.append("%s summary 任务类型不在官方六类：%s（R20）" % (where, "、".join(bad)))
        if "video continuation" in tasks and "<Video" not in body:
            warns.append("%s summary 写了 video continuation，但本段没有 <Video N>；没有把上一段视频当输入时不许写（R20）" % where)

    ret = sec["retention_analysis"].strip()
    if not ret:
        fails.append("%s retention_analysis 为空（R20）" % where)
    else:
        bad = 0
        for line in ret.splitlines():
            st = line.strip()
            if not st:
                continue
            if st.startswith("<") and not any(k in st for k in VIS_MARKERS + AUD_MARKERS):
                bad += 1
                if bad <= 3:
                    fails.append("%s retention_analysis 缺合法保留度标记：%s（R20）" % (where, st[:60]))
        if bad > 3:
            fails.append("%s retention_analysis 另有 %d 条缺合法标记（R20）" % (where, bad - 3))

    words = len(re.findall(r"[A-Za-z]+", detail))
    if words and not (350 <= words <= 500):
        warns.append("%s detailed_description 约 %d 个英文词，官方建议 350–500（台词密集段可放宽，R51）" % (where, words))

    sound = sec["overall_soundscape"].strip()
    if not sound:
        fails.append("%s overall_soundscape 为空；环境声、动作声、非语言人声 1–4 句（R20）" % where)
    elif sound == "N/A" and "静音" not in body:
        warns.append("%s overall_soundscape 写了 N/A；只有用户明确要求全片静音才可写（R20）" % where)
    return sec


def check_official_timecodes(detail, declared, where, fails):
    """R18/R53：首镜 [Shot 1] 不写时间码；后续镜 At MM:SS.mmm 严格递增且小于段长。"""
    marks = [(int(m.group(1)), m) for m in re.finditer(r"\[Shot\s+(\d+)\]", detail)]
    if not marks:
        return 0
    nums = [n for n, _ in marks]
    if nums[0] != 1:
        fails.append("%s 第一镜不是 [Shot 1]（R18）" % where)
    for i, (n, m) in enumerate(marks):
        if n != i + 1:
            fails.append("%s 镜头编号不连续：第 %d 个是 [Shot %d]（R18）" % (where, i + 1, n))
            break
    times = []
    bad = 0
    for n, m in marks:
        line_end = detail.find("\n", m.end())
        tail = detail[m.end(): line_end if line_end != -1 else len(detail)]
        at = re.match(r"\s*At\s+(\d{2}):(\d{2})\.(\d{3})", tail)
        if n == 1:
            if at:
                fails.append("%s [Shot 1] 写了时间码；首镜不许写 At MM:SS.mmm（R18）" % where)
                bad += 1
            continue
        if not at:
            fails.append("%s [Shot %d] 缺 At MM:SS.mmm 切点（R18）" % (where, n))
            bad += 1
            continue
        secs = int(at.group(1)) * 60 + int(at.group(2)) + int(at.group(3)) / 1000.0
        times.append((n, secs))
    for i in range(1, len(times)):
        if times[i][1] <= times[i - 1][1]:
            fails.append("%s [Shot %d] 切点 %.3f 秒没有严格大于 [Shot %d] 的 %.3f 秒（R18）"
                         % (where, times[i][0], times[i][1], times[i - 1][0], times[i - 1][1]))
            bad += 1
    if declared and times and times[-1][1] >= declared:
        fails.append("%s 最后一个切点 %.3f 秒不小于段长 %d 秒（R18）" % (where, times[-1][1], declared))
        bad += 1
    return bad


def check_segment_dialogue(sec, where, fails):
    """R51/R53：台词挂 (Sx) 说话人编号并包进 <d>[Language] 原文</d>；独白写不张嘴。"""
    detail = sec.get("detailed_description", "")
    if not detail:
        return
    d_tags = RE_DIALOG_TAG.findall(detail)
    speakers = RE_SPEAKER.findall(detail)
    if d_tags and not speakers:
        fails.append("%s detailed_description 有 <d> 台词但没挂 (Sx) 说话人编号（R20.2）" % where)
    if speakers and not d_tags:
        fails.append("%s detailed_description 有 (Sx) 编号但台词没包进 <d>[Language] 原文</d>（R53）" % where)
    for line in detail.splitlines():
        if RE_DIALOG_TAG.search(line):
            continue
        if len(CJK.findall(line)) >= 6:
            fails.append("%s detailed_description 叙述句出现中文（除 <d> 内台词与画内可见引文外正文应为英文，R53）：%s"
                         % (where, line.strip()[:40]))
            break
    if "says in an off-screen voiceover" in detail.lower() and "lips remain completely closed" not in detail:
        fails.append("%s 画外音/独白没写 lips remain completely closed（R22 独白不张嘴）" % where)


def check_segment_music(sec, where, fails):
    """R25：non_diegetic_music 段为 N/A 或标注用户指定；其余段不出现配乐词。"""
    music = sec.get("non_diegetic_music", "")
    allow = "用户指定" in music or "user-specified" in music.lower()
    if not allow and music.strip() and music.strip() != "N/A":
        fails.append("%s non_diegetic_music 未写 N/A 且未标注「配乐（用户指定）」（R25 默认无配乐）" % where)
    for name in ("overall_soundscape", "detailed_description"):
        body = sec.get(name, "")
        for m in MUSIC_RE.finditer(body):
            fails.append("%s %s 出现未经用户点名的配乐词「%s」（R25）" % (where, name, m.group(0)))
            break


def check_segment_gaze(sec, where, fails):
    """R52：detailed_description 风格句后必须有英文「镜头是旁观者、人物不看镜头」硬句。"""
    detail = sec.get("detailed_description", "")
    low = detail.lower()
    if "outside witness" not in low or "no character looks into the lens" not in low:
        fails.append("%s detailed_description 缺英文不看镜头硬句（outside witness / No character looks into the lens，R52）" % where)
        return 1
    return 0


def check_camera_gaze(text, where, fails):
    """R49/R52：第三视角记录，只有镜头找人、没有人找镜头。分镜与分段里出现看镜头措辞即 FAIL。"""
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        m = GAZE_RE.search(s)
        if m:
            hits.append((i, m.group(0), s[:60]))
    if hits:
        for ln, kw, ctx in hits[:3]:
            fails.append("%s 第 %d 行出现看镜头写法「%s」：%s（R49／R52 第三视角，人物不看镜头）"
                         % (where, ln, kw, ctx))
        if len(hits) > 3:
            fails.append("%s 另有 %d 处看镜头写法，未逐条列出（R49／R52）" % (where, len(hits) - 3))
    return len(hits)


def check_prompt_detail(pr, where, fails):
    """R50：分镜提示词按动作顺序写细。缺起幅、动作句过短即 FAIL。"""
    lines = [l.strip() for l in pr.splitlines() if not DIALOGUE_LINE.match(l.strip())]
    lines = [l for l in lines if l and not l.startswith("约束")]
    if not lines:
        return 0
    bad = 0
    if not any(l.startswith("起幅") for l in lines):
        fails.append("%s 提示词缺「起幅：」（R50 起幅要写空间与机位）" % where)
        bad += 1
    short = 0
    for l in lines:
        if l.startswith(("切：", "切:", "转场")):
            continue
        n = len(CJK.findall(l))
        if n < 15:
            short += 1
            if short <= 3:
                fails.append("%s 提示词动作句过短（%d 字）：%s（R50 每句写细，至少 15 个汉字）"
                             % (where, n, l[:40]))
    if short > 3:
        fails.append("%s 另有 %d 句提示词过短，未逐条列出（R50）" % (where, short - 3))
    if not any(BODY_RE.search(l) for l in lines):
        fails.append("%s 提示词没有任何表情肌／身体／视线细节（R50 不许概括）" % where)
        bad += 1
    return bad + short


def read_text(p):
    raw = p.read_bytes()
    for enc in ("utf-8", "utf-8-sig"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("gb18030", errors="replace")


def split_blocks(text, head_re):
    ms = list(head_re.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.append({"m": m, "body": text[m.end():end]})
    return out


def field_lines(body):
    """返回 {字段名: 该字段所在行之后到下一个字段之前的原文}"""
    hits = list(re.finditer(r"^-\s*(%s)\s*[:：]" % "|".join(SHOT_FIELDS + SEG_FIELDS), body, re.M))
    d = {}
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
        d.setdefault(h.group(1), body[h.end():end])
    return d


def prompt_text(fields):
    """从「提示词」字段里取出可粘贴正文：优先围栏块，否则取到块尾。"""
    sec = fields.get("提示词", "")
    fence = re.search(r"```[a-zA-Z]*\s*\n(.*?)```", sec, re.S)
    if fence:
        return fence.group(1)
    return sec


def shot_duration(fields):
    """镜长从「拍摄手法」里的「镜长 N 秒」取；不按提示词时间码反推。"""
    m = re.search(r"镜长\s*(\d+)\s*秒", fields.get("拍摄手法", ""))
    return int(m.group(1)) if m else None


def check_slots(text, where, fails, notes):
    bad_fmt = set()
    for m in re.finditer(r"@图片(\s*)(\d*)", text):
        sp, num = m.group(1), m.group(2)
        if sp != " " or not num:
            bad_fmt.add(m.group(0))
            continue
        notes["slots"].add(int(num))
    if bad_fmt:
        fails.append("%s 槽号写法不对：%s（应为「@图片 N」，图片与数字之间有一个空格）"
                     % (where, "、".join("「%s」" % x for x in sorted(bad_fmt))))
    bad = set(re.findall(r"@图片\s*\d+\s*[、,，]", text))
    if bad:
        fails.append("%s 槽号后面多余标点：%s" % (where, "、".join(sorted(bad))))


RE_ASSET_SECTION = re.compile(r"^##\s*(人物|场景|道具)\s*$", re.M)
RE_ASSET_ITEM = re.compile(r"^-\s*([CSP])(\d{1,3})\s*(?:｜|\|)\s*(.+)$")
RE_ID_REF = re.compile(r"@([CSP])(\d+)([^\s，、；。：（）()@|｜/]*)")
ID_PREFIX = {"人物": "C", "场景": "S", "道具": "P"}


def check_assets(asset_txt, fails):
    """R27：三节齐全、编号唯一、前缀与小节一致、每条带图槽。R30：资产表只出提示词，不许贴图。"""
    defined = set()
    if not asset_txt:
        return defined
    for line in asset_txt.splitlines():
        if re.search(r"\.(png|jpg|jpeg|webp|bmp)", line, re.I) or any(
                k in line for k in ("已出图", "图片已生成", "见附图", "图已生成")):
            fails.append("资产表里不许出现图片文件／路径或「已出图」说法，资产只出提示词（R30）：%s"
                         % line.strip()[:36])
            break
    heads = list(RE_ASSET_SECTION.finditer(asset_txt))
    missing = [s for s in ("人物", "场景", "道具")
               if not any(h.group(1) == s for h in heads)]
    if missing:
        fails.append("资产提示词.md 缺小节：%s" % "、".join("## " + s for s in missing))
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(asset_txt)
        sec, body = h.group(1), asset_txt[h.end():end]
        items = 0
        for line in body.splitlines():
            m = RE_ASSET_ITEM.match(line.strip())
            if not m:
                continue
            items += 1
            kind, num, rest = m.group(1), m.group(2), m.group(3)
            aid = kind + num
            if len(num) != 2:
                fails.append("资产条目编号 %s 不是两位数字（应为 C01／S01／P01，缺的补零）" % aid)
                continue
            if ID_PREFIX[sec] != kind:
                fails.append("资产提示词.md「%s」小节里出现了 %s，前缀应与小节一致（人物 C／场景 S／道具 P）"
                             % (sec, aid))
            if aid in defined:
                fails.append("资产编号 %s 在资产提示词.md 里重复定义" % aid)
            defined.add(aid)
            if "@图片" not in rest:
                fails.append("资产条目 %s 没标图槽（应写「图槽：@图片 N …」）" % aid)
            if "提示词" not in rest:
                fails.append("资产条目 %s 没写提示词（应写「提示词：…」）" % aid)
        if not items:
            fails.append("资产提示词.md「## %s」小节没有任何 `- %s01 ｜ 名字 ｜ …` 条目"
                         % (sec, ID_PREFIX[sec]))
    return defined


def check_ids(text, where, defined, fails):
    """R27：@C／@S／@P 格式（两位数字、编号后留一格空格）与悬空引用。"""
    bad_fmt, undefined = set(), set()
    for m in RE_ID_REF.finditer(text):
        kind, num, tail = m.group(1), m.group(2), m.group(3)
        if len(num) != 2 or tail:
            bad_fmt.add(m.group(0))
            if len(num) != 2:
                continue
        aid = kind + num
        if defined and aid not in defined:
            undefined.add(aid)
    if undefined:
        fails.append("%s 引用了资产表里没有的编号：%s（R27）"
                     % (where, "、".join("@" + a for a in sorted(undefined))))
    if bad_fmt:
        fails.append("%s 编号写法不对：%s（应为「@C01 名字」，两位数字、编号与中文名之间留一个空格）"
                     % (where, "、".join("「%s」" % x for x in sorted(bad_fmt))))


def check_standing(blocks, source, defined, fails, warns, anchors):
    """R26：每场要有带 @Sxx 锚点的「场景站位」。"""
    for b in blocks:
        body = b["body"]
        g = b["m"]
        gname = g.group(2) if (g.lastindex and g.lastindex >= 2) else g.group(1)
        label = "%s 的场「%s」" % (source, gname)
        if "场景站位" not in body:
            fails.append("%s 缺「场景站位（锚点：@Sxx 物体名）」这一行（R26）" % label)
            continue
        stand = "\n".join(l for l in body.splitlines() if "场景站位" in l)
        sm = re.search(r"@S0\d*|@S\d{2}", stand)
        if "锚点" not in stand or not sm:
            fails.append("%s 的「场景站位」没写清锚点（应写「锚点：@S01 场景 · 物体」）（R26）" % label)
            continue
        anchors.add(sm.group(0)[1:])


RE_CHAR_BLOCK = re.compile(r"^##\s+(C\d{2})\s*(?:｜|\|)?\s*(.+)$", re.M)
RE_CHAR_CHOICE = re.compile(r"本集选择[：:]\s*(\S+)", re.M)
A_ITEMS = ["三视图", "面部特征", "服装结构", "发型与配饰", "身体比例"]


def check_char_assets(txt, fails, warns):
    """R28：首行选择与 A／B 节是否对得上、A 五项是否齐、A 内每条是否带图槽。"""
    m = RE_CHAR_CHOICE.search(txt)
    if not m:
        fails.append("人物资产.md 缺首行「本集选择：A／B／AB」（R28）")
        choice = ""
    else:
        choice = m.group(1).strip().upper()
        if choice not in ("A", "B", "AB"):
            fails.append("人物资产.md 的「本集选择」只能是 A／B／AB，当前是「%s」" % m.group(1).strip())

    blocks = list(RE_CHAR_BLOCK.finditer(txt))
    if not blocks:
        fails.append("人物资产.md 没有角色段（应为「## C01 周野」）（R28）")
        return set()

    ids = set()
    for i, b in enumerate(blocks):
        cid, name = b.group(1), b.group(2).strip()
        ids.add(cid)
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(txt)
        body = txt[b.end():end]
        has_a = "### A 资产" in body
        has_b = "### B 资产" in body
        if choice in ("A", "AB") and not has_a:
            fails.append("%s 缺「### A 资产」（本集选择是 %s）" % (cid, choice))
        if choice in ("B", "AB") and not has_b:
            fails.append("%s 缺「### B 资产」（本集选择是 %s）" % (cid, choice))
        if choice == "A" and has_b:
            fails.append("%s 写了 B 资产，但本集只选了 A（不许擅自补齐）" % cid)
        if choice == "B" and has_a:
            fails.append("%s 写了 A 资产，但本集只选了 B" % cid)
        if has_a:
            a_body = body.split("### A 资产", 1)[1]
            a_body = a_body.split("### B 资产", 1)[0]
            heads = re.findall(r"^####\s*A(\d)\s*(.*)$", a_body, re.M)
            digits = {h[0] for h in heads}
            if len(heads) < 5 or digits != set("12345"):
                fails.append("%s 的 A 资产小节应为 A1–A5 五项，当前是 %s（R28）"
                             % (cid, "、".join(sorted(digits)) or "无"))
            for kw in A_ITEMS:
                if kw not in a_body:
                    fails.append("%s 的 A 资产缺「%s」" % (cid, kw))
            lines = [l for l in a_body.splitlines() if l.strip().startswith("- ")]
            if not lines:
                fails.append("%s 的 A 资产没有任何条目" % cid)
            for l in lines:
                if "提示词" not in l:
                    fails.append("%s 的 A 资产有条目没写成提示词（应以「提示词：」开头，能直接粘去出图）：%s"
                                 % (cid, l.strip()[:36]))
                    break
            for l in lines:
                if not SLOT.search(l):
                    fails.append("%s 的 A 资产有条目没写「图槽：@图片 N」：%s" % (cid, l.strip()[:36]))
                    break
    if choice == "AB":
        warns.append("本集选了 AB，B 的发色／肤色／服装主色须与 A 一致（脚本查不了，见人工核对第 15 条）")
    return ids


def check_scene_assets(txt, fails, warns):
    """R29：场景资产按十章出、01–04 归 A、05–10 归 B；选择与节是否对得上；
    A1–A4 齐全，A2–A4 每条是可粘提示词并带图槽（A3 的尺寸与坐标除外），B 有 B1–B6 时查关键词。"""
    m = RE_CHAR_CHOICE.search(txt)
    if not m:
        fails.append("场景资产.md 缺首行「本集选择：A／B／AB」（R29）")
        choice = ""
    else:
        choice = m.group(1).strip().upper()
        if choice not in ("A", "B", "AB"):
            fails.append("场景资产.md 的「本集选择」只能是 A／B／AB，当前是「%s」" % m.group(1).strip())

    blocks = list(RE_SCENE_ASSET_BLOCK.finditer(txt))
    if not blocks:
        fails.append("场景资产.md 没有场景段（应为「## S01 出租屋」）（R29）")
        return set()

    ids = set()
    for i, b in enumerate(blocks):
        sid, name = b.group(1), b.group(2).strip()
        ids.add(sid)
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(txt)
        body = txt[b.end():end]
        has_a = "### A 资产" in body
        has_b = "### B 资产" in body
        if choice in ("A", "AB") and not has_a:
            fails.append("%s 缺「### A 资产」（本集选择是 %s）" % (sid, choice))
        if choice in ("B", "AB") and not has_b:
            fails.append("%s 缺「### B 资产」（本集选择是 %s）" % (sid, choice))
        if choice == "A" and has_b:
            fails.append("%s 写了 B 资产，但本集只选了 A（不许擅自补齐）" % sid)
        if choice == "B" and has_a:
            fails.append("%s 写了 A 资产，但本集只选了 B" % sid)

        if has_a:
            a_body = body.split("### A 资产", 1)[1].split("### B 资产", 1)[0]
            secs = {}
            cur = None
            for line in a_body.splitlines():
                hm = re.match(r"^####\s*A(\d)(?:\s*(.*))?$", line.strip())
                if hm:
                    cur = hm.group(1)
                    secs.setdefault(cur, [])
                    continue
                if cur and line.strip().startswith("- "):
                    secs[cur].append(line.strip())
            if set(secs) != set("1234"):
                fails.append("%s 的 A 资产小节应为 A1–A4（基础资料／全景三视图／空间布局／细节参考），当前是 %s（R29）"
                             % (sid, "、".join("A" + k for k in sorted(secs)) or "无"))
            for kw in SCENE_A_ITEMS:
                if kw not in a_body:
                    fails.append("%s 的 A 资产缺「%s」" % (sid, kw))
            for num in ("2", "3", "4"):
                for l in secs.get(num, []):
                    if num == "3" and re.match(r"-\s*(空间尺寸|空间坐标)", l):
                        continue
                    if "提示词" not in l:
                        fails.append("%s 的 A%s 有条目没写成提示词（应以「提示词：」开头）：%s"
                                     % (sid, num, l[:36]))
                    elif not SLOT.search(l):
                        fails.append("%s 的 A%s 有条目没写「图槽：@图片 N」：%s" % (sid, num, l[:36]))

        if has_b:
            b_body = body.split("### B 资产", 1)[1]
            heads = set(re.findall(r"^####\s*B(\d)", b_body, re.M))
            if heads and heads != set("123456"):
                fails.append("%s 的 B 资产小节应为 B1–B6（道具／光照／天气／材质／镜头参考／连续性），当前是 %s（R29）"
                             % (sid, "、".join("B" + k for k in sorted(heads))))
            missing = [k for k in SCENE_B_ITEMS if k not in b_body]
            if missing:
                fails.append("%s 的 B 资产缺条目：%s" % (sid, "、".join(missing)))
    if choice == "AB":
        warns.append("本集选了 AB，B 的道具位置／光照／材质须与 A 的画面一致（脚本查不了，见人工核对第 17 条）")
    return ids



STYLE_DECL = re.compile(r"画风[：:]\s*(REF-\d{3})")
STYLE_TAIL = re.compile(r"画风\s*按\s*(REF-\d{3})\s*[：:]")
STYLE_ANY = re.compile(r"(REF-\d{3})")


def check_multi_speaker(prompt, where, fails):
    """R34：多人同场要排队说；一人说时别人嘴不动。"""
    names = [DIALOGUE_LINE.match(l.strip()).group(0).split("（")[0].rstrip("：:") 
             for l in prompt.splitlines() if DIALOGUE_LINE.match(l.strip())]
    if len(set(names)) >= 2:
        first = prompt.splitlines()[0] if prompt.splitlines() else ""
        if MOUTH_CLAUSE not in first:
            fails.append("%s 多人对话，段首约束行没写「%s」（R34）" % (where, MOUTH_CLAUSE))


def check_line_order(field, where, label, fails):
    """R34：台词索引／说话人索引按 ①②③ 排，不许写时间码。"""
    text = field or ""
    if TIME_CODE_RE.search(text):
        fails.append("%s「%s」写了时间码：%s（R13 不写时间码，按 ①②③ 排）" % (where, label, text.strip()[:30]))
    nums = re.findall(r"[①②③④⑤⑥⑦⑧⑨]", text)
    if nums and nums != sorted(set(nums), key="①②③④⑤⑥⑦⑧⑨".index):
        fails.append("%s「%s」说话顺序颠倒：%s（R34）" % (where, label, text.strip()[:30]))


def check_style(texts, fails):
    """R31＋R47：画风只认用户给的参考图，分两次问——先人物，再场景／道具。
    允许一集两句锁：人物一句（REF-001）、场景与道具一句（REF-002，可沿用同号）。
    人物资产.md 用人物号；场景资产.md 用场景道具号；资产提示词.md 按小节分别对号；
    每条带「提示词」的条目都要有 `画风 按 REF-xxx：` 尾巴，且必须与所在层对号。"""
    def codes_of(txt):
        return sorted(set(STYLE_DECL.findall(txt)))

    decls = {}
    for name, txt in texts.items():
        cs = codes_of(txt)
        if cs:
            decls[name] = cs
    if not decls:
        fails.append("三份资产文件都没有「画风：REF-001 用户参考图 · …」声明：出资产前先要一张画风参考图（R31）")
        return ""

    all_codes = sorted({c for cs in decls.values() for c in cs})
    if len(all_codes) > 2:
        fails.append("画风声明超过两句锁：%s（一集最多「人物一句＋场景道具一句」，R47）"
                     % "、".join(all_codes))

    # 人物号与场景道具号：按声明里出现的顺序定，第一个当人物，第二个当场景／道具
    char_code = all_codes[0]
    scene_code = all_codes[1] if len(all_codes) > 1 else char_code

    for name, cs in decls.items():
        if len(cs) > 1 and name != "资产提示词.md":
            fails.append("%s 声明了多个画风编号：%s（人物资产只写人物锁，场景资产只写场景道具锁，R47）"
                         % (name, "、".join(cs)))

    for name, txt in texts.items():
        if name not in decls:
            fails.append("%s 缺「画风：REF-…」声明（R31）" % name)
            continue
        if name == "人物资产.md":
            expect = char_code
        elif name == "场景资产.md":
            expect = scene_code
        else:
            # 资产提示词.md：按「## 人物／## 场景／## 道具」小节分号
            expect = None

        section = "人物"
        bad = []
        for line in txt.splitlines():
            st = line.strip()
            hm = re.match(r"^#{1,3}\s*([人物场景道具]+)", st)
            if hm:
                section = hm.group(1)
                continue
            if not st.startswith("-") or "提示词" not in st:
                continue
            want = expect
            if want is None:
                want = scene_code if section in ("场景", "道具") else char_code
            tails = STYLE_TAIL.findall(st)
            if not tails:
                bad.append((st[:26], "缺尾巴", want))
                continue
            if any(c != want for c in tails):
                bad.append((st[:26], "用错号 " + "、".join(tails), want))
        if bad:
            sample = "；".join("%s（%s，应为 %s）" % (a, b, c) for a, b, c in bad[:3])
            fails.append("%s 有 %d 条提示词画风对不上：%s（R47）" % (name, len(bad), sample))

    return char_code if len(all_codes) == 1 else "%s／%s" % (char_code, scene_code)


def check_coverage(script_txt, board_txt, seg_txt, asset_txt, defined, fails, warns):
    """R44：剧本／分镜／分段里出现的人物、场景、道具，资产表必须有；未用到的资产标「未使用」。"""
    layers = (("剧本.md", script_txt), ("分镜.md", board_txt), ("分段视频提示词.md", seg_txt))
    used = set()
    for _, txt in layers:
        for m in RE_ID_REF.finditer(txt):
            if len(m.group(2)) == 2:
                used.add(m.group(1) + m.group(2))
    if defined:
        unused = sorted(defined - used)
        if unused:
            warns.append("资产表登记但本集三层都没用到：%s（标「未使用」，编号保留、不删，R44）"
                         % "、".join("@" + a for a in unused))
    if script_txt:
        for blk in split_blocks(script_txt, RE_SCENE_ID):
            head = blk["m"].group(0).strip()
            cids = set("C" + m.group(2) for m in RE_ID_REF.finditer(blk["body"])
                       if m.group(1) == "C" and len(m.group(2)) == 2)
            if not cids:
                fails.append("%s 本场没有任何 @Cxx 人物编号，资产无法核对（R44）" % head[:34])
    cnames = {}
    if asset_txt:
        for line in asset_txt.splitlines():
            m = RE_ASSET_ITEM.match(line.strip())
            if not m or m.group(1) != "C" or len(m.group(2)) != 2:
                continue
            parts = [p.strip() for p in m.group(3).lstrip("｜").split("｜")]
            if parts and parts[0]:
                cnames[parts[0]] = "C" + m.group(2)
    if script_txt and cnames:
        speakers = set(s for s in re.findall(r"^([^\s：:\[\]#]{1,8})[：:]", script_txt, re.M)
                       if not s.isdigit() and "*" not in s)
        unknown = sorted(s for s in speakers if s not in cnames
                         and s not in ("题材", "说话顺序", "系统", "画外", "电视播报"))
        if unknown:
            warns.append("剧本台词里的说话人未在资产表登记为人物：%s（若是画外音／播报可忽略，否则补编号，R44）"
                         % "、".join(unknown))


def check_handoff(project, ep, fails, warns, require=False):
    """R45：项目根必须有 项目交接.md，含小说进度／集间承接／已产出资产／画风／待办。"""
    p = project / "项目交接.md"
    if not p.is_file():
        msg = ("缺 项目交接.md（项目根）：要写小说改到哪里、本集结尾与下集承接、已产出资产清单、画风锁、待办（R45）")
        (fails if require else warns).append(msg)
        return
    txt = read_text(p)
    needed = [("小说", "小说改编进度"), ("承接", "集间承接"), ("资产", "已产出资产"), ("画风", "画风"), ("待办", "待办")]
    for _, label in needed:
        if label not in txt:
            (fails if require else warns).append("项目交接.md 缺小节「%s」（R45）" % label)
    if ep not in txt:
        warns.append("项目交接.md 里没有 %s 的记录，做完这一集要补一节（R45）" % ep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--ep", default="EP001")
    ap.add_argument("--skip-script", action="store_true", help="R33 跳过剧本模式：不要求 剧本.md")
    ap.add_argument("--require-handoff", action="store_true", help="R45：缺少或不完整的 项目交接.md 直接判 FAIL")
    args = ap.parse_args()

    project = pathlib.Path(args.project)
    ep_dir = project / "剧集" / args.ep
    fails, warns = [], []
    notes = {"slots": set()}

    if not ep_dir.is_dir():
        print("FAIL 找不到剧集目录：%s" % ep_dir)
        return 1

    script_p = ep_dir / "剧本.md"
    board_p = ep_dir / "分镜.md"
    seg_p = ep_dir / "分段视频提示词.md"
    asset_p = ep_dir / "资产提示词.md"
    char_p = ep_dir / "人物资产.md"
    scene_p = ep_dir / "场景资产.md"
    required = [board_p, seg_p] + ([] if args.skip_script else [script_p])
    for p in required:
        if not p.is_file():
            fails.append("缺少文件：%s" % p.name)
    if fails:
        report(fails, warns, notes, {}, {}, [])
        return 1

    script_txt = read_text(script_p) if script_p.is_file() else ""
    board_txt = read_text(board_p)
    seg_txt = read_text(seg_p)
    asset_txt = read_text(asset_p) if asset_p.is_file() else ""

    # ---------- R49 第三视角，人物不看镜头 ----------
    gaze_total = 0
    for name, txt in (("分镜.md", board_txt), ("分段视频提示词.md", seg_txt)):
        gaze_total += check_camera_gaze(txt, name, fails)
    notes["camera_gaze"] = gaze_total

    # ---------- 剧本 ----------
    if args.skip_script and not script_txt:
        notes["script_skipped"] = True
        warns.append("已按 R33 跳过剧本层：本集不出 剧本.md，分镜场标题须写小说来源（如「来源：第 3 章 第 2 段」）")
    scenes = RE_SCENE_ID.findall(script_txt)
    if script_txt and not scenes:
        fails.append("剧本.md 未找到场景标题（应为「## EPxxx-SCxxx 内/外 · 地点 · 时间」）")
    dialogue = [(m.group(1), m.group(2).strip()) for m in RE_DIALOGUE.finditer(script_txt)]
    # 排除非台词行：题材行、「**说话顺序**：① A → ② B」这类索引行
    dialogue = [(s, t) for s, t in dialogue
                if not s.isdigit() and "*" not in s and "→" not in t
                and s not in ("题材", "说话顺序")]
    for line in (script_txt.splitlines() if script_txt else []):
        if not re.match(r"^([^\s：:\[\]#]{1,9})[：:]", line):
            continue
        head = re.match(r"^([^\s：:\[\]#]{1,8})[：:]", line)
        if not head:
            fails.append("剧本台词行说话人超过 8 字或含标点，解析会漏检：%s" % line.strip()[:20])

    # ---------- 分镜 ----------
    for name, txt in (("分镜.md", board_txt), ("分段视频提示词.md", seg_txt)):
        glued = 0
        for line in txt.splitlines():
            s = line.strip()
            if s.startswith("#"):
                continue
            if re.search(r"#{2,3}\s*(?:镜头|第\s*\d+\s*场|第\s*\d+\s*段)", line):
                glued += 1
        if glued:
            fails.append("%s 有标题被挤到上一行末尾（标题粘连），共 %d 处" % (name, glued))

    board_scenes = split_blocks(board_txt, RE_BOARD_SCENE)
    if not board_scenes:
        fails.append("分镜.md 未找到场标题（应为「## 第 N 场 ｜ 场名（来源：EPxxx-SCxxx）」）")
    elif args.skip_script and not script_txt:
        for blk in board_scenes:
            head = blk["m"].group(0)
            if "来源：" not in head:
                fails.append("跳过了剧本，分镜场标题必须写小说来源：%s" % head.strip()[:40])

    shots = split_blocks(board_txt, RE_SHOT)
    if not shots:
        fails.append("分镜.md 未找到镜头标题（应为「### 镜头 场-镜 ｜ 中文名」）")

    # ---------- 资产表、编号与站位锚点（R26–R27） ----------
    legacy = (not asset_p.is_file()) and ("场景站位" not in script_txt)
    defined = set()
    if legacy:
        warns.append("本集既无 资产提示词.md 也无「场景站位」，按「不回溯」当作旧版文件，跳过 R26／R27；新集必须写。")
    else:
        if not asset_p.is_file():
            fails.append("缺文件：资产提示词.md（人物／场景／道具三节，带 C／S／P 编号）（R27）")
        defined = check_assets(asset_txt, fails)
        script_anchors, board_anchors = set(), set()
        if script_txt:
            check_standing(split_blocks(script_txt, RE_SCENE_ID), "剧本.md", defined, fails, warns, script_anchors)
        check_standing(board_scenes, "分镜.md", defined, fails, warns, board_anchors)
        if script_anchors and board_anchors and script_anchors != board_anchors:
            fails.append("剧本与分镜的锚点编号不一致：剧本 %s / 分镜 %s（R26）"
                         % ("、".join(sorted(script_anchors)), "、".join(sorted(board_anchors))))
        if script_txt:
            check_ids(script_txt, "剧本.md", defined, fails)
        check_ids(board_txt, "分镜.md", defined, fails)
        check_ids(seg_txt, "分段视频提示词.md", defined, fails)
    notes["assets"] = len(defined)
    check_coverage(script_txt, board_txt, seg_txt, asset_txt, defined, fails, warns)
    check_handoff(project, args.ep, fails, warns, require=args.require_handoff)

    if char_p.is_file():
        char_txt = read_text(char_p)
        cids = check_char_assets(char_txt, fails, warns)
        notes["char_ids"] = len(cids)
        cm = RE_CHAR_CHOICE.search(char_txt)
        notes["char_choice"] = cm.group(1).strip().upper() if cm else "?"

    if scene_p.is_file():
        scene_txt = read_text(scene_p)
        sids = check_scene_assets(scene_txt, fails, warns)
        notes["scene_ids"] = len(sids)
        sm2 = RE_CHAR_CHOICE.search(scene_txt)
        notes["scene_choice"] = sm2.group(1).strip().upper() if sm2 else "?"

    # ---------- 画风（R31） ----------
    texts = {"资产提示词.md": asset_txt}
    if char_p.is_file():
        texts["人物资产.md"] = read_text(char_p)
    if scene_p.is_file():
        texts["场景资产.md"] = read_text(scene_p)
    style = check_style(texts, fails)
    if style:
        notes["style"] = style

    board_prompt_all = []
    shot_durs = {}
    for s in shots:
        sid = s["m"].group(1)
        where = "镜头 %s" % sid
        f = field_lines(s["body"])
        for name in SHOT_FIELDS:
            if name not in f:
                fails.append("%s 缺「%s」栏" % (where, name))
        pr = prompt_text(f)
        board_prompt_all.append(pr)
        check_prompt_detail(pr, where, fails)
        check_no_timecode(pr, where, fails)
        dur = shot_duration(f)
        shot_durs[sid] = dur
        if dur and dur > 15:
            warns.append("%s 单镜 %d 秒，超过 H3 单次上限，须并进容器或拆镜" % (where, dur))
        if dur == 1:
            warns.append("%s 单镜只有 1 秒，低于 2 秒不宜单条送生成" % where)
        check_slots(f.get("参考图", "") + "\n" + pr, where, fails, notes)
        allow_music = "用户指定" in f.get("声音", "")
        scan_music(pr, where + " 提示词", fails, require_off=False, allow=allow_music)
        scan_music(f.get("声音", ""), where + " 声音栏", fails, require_off=False, allow=allow_music)
        # 台词栏只做索引
        tl = f.get("台词", "").strip()
        if tl and tl != "无":
            if re.search(r"[\u4e00-\u9fa5]{6,}", tl):
                fails.append("%s「台词」栏抄了原文，只该写说话顺序与说话人" % where)
            if not re.search(r"[①②③④⑤⑥⑦⑧⑨]", tl):
                fails.append("%s「台词」栏缺说话顺序（格式 ① 周野 → ② 小赵）" % where)
        check_multi_speaker(pr, where, fails)
        check_line_order(tl, where, "台词", fails)
        # 独白
        sound = f.get("声音", "")
        is_mono = any(w in sound for w in MONO_WORDS)
        if is_mono:
            if "不张嘴" not in pr:
                fails.append("%s 是独白镜，提示词里没写「不张嘴」" % where)
            exp = f.get("表情", "")
            bad = [w for w in MOUTH_CONFLICT if w in exp]
            if bad:
                fails.append("%s 独白镜「表情」栏出现冲突描写：%s" % (where, "、".join(bad)))
        # 动作里不用冒号
        act = f.get("动作", "")
        if "：" in act or ":" in act:
            fails.append("%s「动作」栏用了冒号，会被当成台词行；改用逗号" % where)

    if shot_durs and any(v is None for v in shot_durs.values()):
        fails.append("有镜头没在「拍摄手法」里写「镜长 N 秒」，时长合计不可信")

    # ---------- 分段 ----------
    segs = split_blocks(seg_txt, RE_SEG)
    if not segs:
        fails.append("分段视频提示词.md 未找到段标题（应为「## 第 N 段 ｜ 场名」）")

    seg_prompt_all = []
    seg_durs = []
    for g in segs:
        num = g["m"].group(1)
        where = "第 %s 段" % num
        f = field_lines(g["body"])
        for name in SEG_FIELDS:
            if name not in f:
                fails.append("%s 缺「%s」元数据字段" % (where, name))
        sec = check_segment_sections(g["body"], where, fails, warns)
        detail = sec.get("detailed_description", "")
        seg_prompt_all.append(detail)
        check_segment_dialogue(sec, where, fails)
        check_segment_music(sec, where, fails)
        check_segment_gaze(sec, where, fails)
        dl = re.sub(r"[^\d]", "", f.get("时长", "").split("\n")[0])
        declared = int(dl) if dl else None
        if declared is None:
            fails.append("%s「时长」字段没写整数秒" % where)
        else:
            if not (4 <= declared <= 15):
                fails.append("%s 时长 %d 秒不在 4–15 区间" % (where, declared))
            seg_durs.append(declared)
            check_official_timecodes(detail, declared, where, fails)
        check_slots(f.get("参考图", "") + "\n" + g["body"], where, fails, notes)
        # 说话人索引：只写 ①②③ 顺序与 (Sx)，不抄原文
        landing = f.get("说话人", "").strip()
        if landing and landing != "无":
            if re.search(r"[\u4e00-\u9fa5]{6,}", landing):
                fails.append("%s「说话人」抄了原文，只该写说话顺序与 (Sx) 编号" % where)
        check_line_order(landing, where, "说话人", fails)
        # 转场标注：跨场次切点
        scene_txt = f.get("场景与轴线", "")
        if ("转场" in scene_txt) and not re.search(r"hard cut|cuts to|transitions to", detail, re.I):
            fails.append("%s 声明了转场，但 detailed_description 切点没写 hard cut / cuts to（R19）" % where)

    # ---------- 跨文件 ----------
    board_total = sum(v for v in shot_durs.values() if v)
    seg_total = sum(seg_durs)
    if shots and segs and board_total != seg_total:
        fails.append("分镜合计 %d 秒 vs 分段合计 %d 秒，不相等" % (board_total, seg_total))

    # R37：一集 4 分钟（240 秒，落 220–260 秒）
    if seg_durs:
        if not (220 <= seg_total <= 260):
            fails.append("一集总时长 %d 秒，不在 4 分钟口径（220–260 秒，目标 240 秒）：少了补戏或并段，多了删并（R37）"
                         % seg_total)

    if scenes:
        covered = {sc for sc in scenes if sc in board_txt}
        missing = [sc for sc in scenes if sc not in covered]
        waived = "未拍场次" in board_txt
        if missing and not waived:
            fails.append("这些场景没有任何镜头承载：%s（确需省拍请写「未拍场次：…（理由：…）」）" % "、".join(missing))

    board_p = "\n".join(board_prompt_all)
    seg_p = "\n".join(seg_prompt_all)
    for spk, txt in dialogue:
        gap = txt
        if len(gap) < 2:
            continue
        expected = script_txt.count(gap)
        for name, blob in (("分镜.md", board_p), ("分段视频提示词.md", seg_p)):
            n = blob.count(gap)
            if n != expected:
                fails.append("台词「%s」在%s出现 %d 次（应为 %d 次，逐字一致且只说一遍）"
                             % (gap[:14], name, n, expected))

    info = {
        "scenes": len(scenes),
        "lines": len(dialogue),
        "shots": len(shots),
        "board_total": board_total,
        "segs": len(segs),
        "seg_total": seg_total,
        "shot_durs": shot_durs,
        "seg_durs": seg_durs,
        "assets": len(defined),
        "char_ids": notes.get("char_ids", 0),
        "char_choice": notes.get("char_choice", ""),
        "scene_ids": notes.get("scene_ids", 0),
        "scene_choice": notes.get("scene_choice", ""),
        "style": notes.get("style", ""),
    }
    report(fails, warns, notes, info, {}, segs)
    return 0 if not fails else 1


HUMAN = [
    "每镜「拍摄手法」是否每条都带理由（略仰＝被压、略俯＝看手、平视＝同行）",
    "每镜「动作先后」是否用 ①②③ 拆开了先后，没把两个动作写在同一拍",
    "「表情」是否先有一句情绪定调（什么情绪、几成、对着谁），再写它对应的肌肉执行清单；只有形容词、或只有肌肉没定调，都不合格",
    "跨段：前段最后一行与后段第一行能否连成一句完整动作，段尾是否停在静止点",
    "跨段：手持物余量、服装、脏污、光位、钟点是否接得上",
    "轴线：同一场是否只在一侧工作，画左画右站位是否跨段不变",
    "每场「场景站位」的锚点是否都在本场景里真实存在且不动，各人位置对锚点说得通，剧本与分镜同锚点同编号（R26）",
    "剧本、分镜里的 @C／@S／@P 是否都能在资产提示词.md 找到，编号跨集不重排，三节提示词能直接粘去文生图（R27）",
    "人物资产是否只出了用户点的那层（答 A 无 B 节、答 B 无 A 节），没替用户擅自补齐（R28）",
    "A 资产五项是否齐、三视图之间身高比例服装配饰是否一致，B 的固定特征与 A 的取值是否打架（R28）",
    "场景资产是否只出了用户点的那层，A2–A4 每条是否可粘提示词带图槽，A3 布局图里画不画得出锚点物，B6 空间规则与 R26 站位是否一致（R29）",
    "三类资产是否都只交了提示词与槽号，没有图片文件、路径或「已出图」说法，交付报告没把提示词说成图片已生成（R30）",
    "每段段数是否由镜长决定，不是硬凑",
]


def report(fails, warns, notes, info, _unused, segs):
    print("== 阿良分镜规则 · 机械自检 ==")
    if info:
        print("场次=%s 台词=%s 镜数=%s 分镜合计=%ss 段数=%s 分段合计=%ss"
              % (info["scenes"], info["lines"], info["shots"], info["board_total"],
                 info["segs"], info["seg_total"]))
        if info["shot_durs"]:
            print("逐镜时长：" + "/".join("%s=%ss" % (k, v) for k, v in info["shot_durs"].items()))
        if info["seg_durs"]:
            print("逐段时长：" + "/".join("段%d=%ss" % (i + 1, d) for i, d in enumerate(info["seg_durs"])))
        if info.get("assets"):
            print("资产编号已定义 %d 条（C／S／P）" % info["assets"])
        if info.get("char_ids"):
            print("人物资产：选择=%s，角色=%s 个" % (info.get("char_choice"), info["char_ids"]))
        if info.get("scene_ids"):
            print("场景资产：选择=%s，场景=%s 个" % (info.get("scene_choice"), info["scene_ids"]))
        if info.get("style"):
            print("画风声明：%s（REF 编号与尾巴见上）" % info["style"])
        if notes.get("camera_gaze"):
            print("R49 看镜头写法：%d 处（明细见 FAIL）" % notes["camera_gaze"])
        if notes["slots"]:
            print("用到的参考图槽：@图片 %s" % "、".join(str(x) for x in sorted(notes["slots"])))
            mx = max(notes["slots"])
            holes = [x for x in range(1, mx + 1) if x not in notes["slots"]]
            if holes:
                print("提示：本集未用到 @图片 %s（旧号不回收，缺号正常）" % "、".join(str(x) for x in holes))
    if warns:
        print("WARN %d 项：" % len(warns))
        for w in warns:
            print("  - " + w)
    if fails:
        print("FAIL %d 项：" % len(fails))
        for f in fails:
            print("  - " + f)
    else:
        print("PASS 机械项全部通过")
    print("仍需人工核对：")
    for h in HUMAN:
        print("  · " + h)


if __name__ == "__main__":
    sys.exit(main())
