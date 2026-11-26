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
RE_SEG_SECTION = re.compile(r"^[ \t]{0,6}([a-z_]+)\s*:\s*$", re.M)
RE_SHOT_TAG = re.compile(r"\[Shot\s+\d+\]")
RE_SUBJECT = re.compile(r"<Subject\s+\d+>")
RE_PICTURE = re.compile(r"<Picture\s+\d+>")
RE_SUBJECT_NAME = re.compile(r"<Subject\s+(\d+)>\s*[（(]\s*图片名[：:]\s*([^）)\n]+?)\s*[）)]")
RE_PICTURE_NAME = re.compile(r"<Picture\s+(\d+)>\s*[（(]\s*图片名[：:]\s*([^）)\n]+?)\s*[）)]")
RE_SPEAKER = re.compile(r"\(S\d+(?:,[^)]*)?\)")
RE_SEG_DIALOGUE = re.compile(r"^\s{2,}\((S\d+(?:,S\d+)*)\)\s+([^：:\n]{1,20})[：:]\s*\[Chinese\]\s*(.+)$", re.M)
RE_DIALOG_TAG = re.compile(r"<d>\s*\[[^\]]+\][^<]*</d>")
MD_ESC = re.compile(r"\\([_<>\[\]])")
TIME_CODE_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
RE_ENTRY = re.compile(r"^[ \t]{0,8}Entry[：:]\s", re.M)
RE_EXIT = re.compile(r"^[ \t]{0,8}Exit[：:]\s", re.M)
# R57：转场六选一；黑场／闪白／叠化／淡入淡出默认禁用
TRANSITION_WORDS = ("同向运镜", "动作匹配", "遮挡", "出入画", "光影过渡", "硬切",
                    "push-in", "pull-out", "push in", "pull out", "pan", "tracking",
                    "match cut", "action match", "occlusion", "wipe", "hard cut", "tilt",
                    "seamless")
TRANSITION_BAN = ("黑场", "闪白", "叠化", "淡入淡出", "淡出")

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
DIALOGUE_LINE = re.compile(r"^\s*(?!约束|起幅|切\s*[：:]|转场|镜头|画面|台词原文)[^\s：:（]{1,8}(?:（[^）]*）)?[：:]")
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


def _norm_md(text):
    r"""去掉 Markdown 反斜杠转义，供解析 `\_`、`\<`、`\[`。"""
    return MD_ESC.sub(r"\1", text)


def _seg_sections(body):
    """把一段分段正文按官方字段行切开，返回 {段名: 正文}。"""
    body = _norm_md(body)
    hits = list(RE_SEG_SECTION.finditer(body))
    d = {}
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
        d[h.group(1)] = body[h.end():end]
    return d


def check_segment_sections(body, where, fails, warns):
    """R20：官方 Ref2VA 六段字段齐全、顺序固定、六段前无约束段；detailed_description 不成分镜缩写（R51）。"""
    body = _norm_md(body)
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
    subj_nums = set(re.findall(r"<Subject\s+(\d+)>", subj_def))
    subj_names = {m.group(1): m.group(2).strip() for m in RE_SUBJECT_NAME.finditer(subj_def)}
    missing_name = [num for num in sorted(subj_nums) if num not in subj_names]
    if missing_name:
        fails.append("%s 这些主体定义没写「（图片名：中文名）」：%s（R20.3）"
                     % (where, "、".join("<Subject %s>" % n for n in missing_name)))
    pic_nums = set(re.findall(r"<Picture\s+(\d+)>", subj_def))
    pic_names = {m.group(1): m.group(2).strip() for m in RE_PICTURE_NAME.finditer(subj_def)}
    missing_pic = [num for num in sorted(pic_nums) if num not in pic_names]
    if missing_pic:
        fails.append("%s 这些帧/构图定义没写「（图片名：中文名）」：%s（R20.3）"
                     % (where, "、".join("<Picture %s>" % n for n in missing_pic)))
    for num in sorted(pic_nums):
        name = pic_names.get(num)
        if name and name not in detail:
            fails.append("%s 定义了 <Picture %s>（图片名：%s），但 detailed_description 没用这个名字（R20.3）"
                         % (where, num, name))
    if RE_SUBJECT.findall(detail) or RE_PICTURE.findall(detail):
        fails.append("%s 正文仍有裸 <Subject N>／<Picture N>；六段正文一律写图片中文名（R20.3）" % where)
    for num in sorted(subj_nums):
        name = subj_names.get(num)
        if name and name not in detail:
            fails.append("%s 定义了 <Subject %s>（图片名：%s），但 detailed_description 没用这个名字（R20.3）"
                         % (where, num, name))

    for line in subj_def.splitlines():
        st = line.strip()
        if not re.match(r"<Subject\s+\d+>", st):
            continue
        if "no visual reference" in st.lower():
            continue
        if "The reference supplies" not in st or "only;" not in st:
            fails.append("%s 主体定义缺「参考图只提供身份」限定句（R54）：%s" % (where, st[:60]))
        if "pose, head angle and eyeline follow the shot description" not in st \
                and "camera angle and view direction follow the shot description" not in st:
            fails.append("%s 主体定义缺「姿态/朝向/视线以分镜为准」限定句（R54）：%s" % (where, st[:60]))
        if "main orientation" not in st.lower():
            fails.append("%s 主体定义缺本段主朝向预声明（R54）：%s" % (where, st[:60]))

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
            if st.startswith("<Subject"):
                if not re.match(r"<Subject\s+\d+>\s*[（(]\s*图片名[：:]", st):
                    fails.append("%s retention_analysis 主体条目不是以 <Subject N>（图片名：…） 开头（R54）：%s" % (where, st[:60]))
                if "head angle and eyeline are reblocked" not in st.lower() \
                        or "reference frontal orientation is not preserved" not in st.lower():
                    fails.append("%s retention_analysis 主体条目缺朝向重排声明（R54）：%s" % (where, st[:60]))
                if "partially_preserved" in st or "attribute_transfer" in st:
                    fails.append("%s retention_analysis 用了 R54 不允许的档位；只许 fully_preserved／weak_reference：%s" % (where, st[:60]))
            elif any(k in st for k in VIS_MARKERS) and "appears" in st:
                fails.append("%s retention_analysis 主体条目没有以 <Subject N>（图片名：…） 开头（R54）：%s" % (where, st[:60]))
        if bad > 3:
            fails.append("%s retention_analysis 另有 %d 条缺合法标记（R20）" % (where, bad - 3))

    words = len(re.findall(r"[A-Za-z]+", detail))
    if words and not (150 <= words <= 350):
        warns.append("%s detailed_description 约 %d 个英文词，模板密度为 150–350（台词密集段按发声时间排满，R56）" % (where, words))

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


def check_segment_dialogue(sec, where, fails, warns=None):
    """R56：台词块后置、每句 `(Sx) 角色：[Chinese] 原文`；不用 <d>、不写 says；说话人按行递增。"""
    detail = _norm_md(sec.get("detailed_description", ""))
    if not detail:
        return
    names = [m.group(2).strip() for m in RE_SUBJECT_NAME.finditer(_norm_md(sec.get("subject_definitions", "")))]
    if RE_DIALOG_TAG.search(detail) or "<d>" in detail:
        fails.append("%s detailed_description 仍用 <d> 包台词；R56 模板要求 (Sx) 角色：[Chinese] 原文（不用 <d>）" % where)
    if re.search(r"\bsays\b", detail, re.I):
        fails.append("%s detailed_description 出现 says；R56 模板不写 says，台词只写 (Sx) 角色：[Chinese] 原文" % where)

    lines = list(RE_SEG_DIALOGUE.finditer(detail))
    if not lines:
        if warns is not None:
            warns.append("%s detailed_description 没有 (Sx) 台词行；若本段剧本有人说话，必须按 (Sx) 角色：[Chinese] 原文 补台词块（R56）" % where)
        return

    last_shot = max((m.start() for m in RE_SHOT_TAG.finditer(detail)), default=-1)
    if lines[0].start() < last_shot:
        fails.append("%s 台词出现在镜头块之前；R56 要求所有台词集中在全部镜头之后（R56.9）" % where)

    # 说话人 ID 按台词行顺序递增；同一角色多句各占一号（样本口径）
    seq_bad = False
    for i, m in enumerate(lines, 1):
        sid = m.group(1)
        if "," in sid:
            continue
        try:
            num = int(sid[1:])
        except ValueError:
            seq_bad = True
            break
        if num != i:
            seq_bad = True
            break
    if seq_bad:
        fails.append("%s 台词行 (Sx) 没有按行从 (S1) 递增；同一角色多句也逐句各占一号（R56.9）" % where)

    for m in lines:
        role = re.sub(r"[（(]\s*VO\s*不张嘴\s*[）)]", "", m.group(2)).strip()
        if names and role not in names and not any(n and n in role for n in names):
            fails.append("%s 台词行说话人「%s」不在本段 Subject 图片中文名里（R20.3／R56）：%s" % (where, role, m.group(0).strip()[:50]))

    if len(lines) >= 2 and "only the character who is speaking moves their lips" not in detail.lower():
        fails.append("%s 多人对话，detailed_description 没写「Only the character who is speaking moves their lips…」（R34 一人说时别人嘴不动）" % where)

    for line in detail.splitlines():
        if RE_SEG_DIALOGUE.match(line):
            continue
        if RE_ENTRY.match(line) or RE_EXIT.match(line):
            continue
        if re.match(r"^[ \t]{0,8}Transition\s+(?:out|in)[:：]", line, re.I):
            continue
        clean = line
        for name in names:
            clean = clean.replace(name, "")
        if len(CJK.findall(clean)) >= 6:
            fails.append("%s detailed_description 叙述句出现中文（除台词、画内可见引文与图片中文名外正文应为英文，R53）：%s"
                         % (where, line.strip()[:40]))
            break





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
    """R52/R54：风格句必须同时写「镜头是旁观者、人物不看镜头」与「不复制参考图正面取向」。"""
    detail = sec.get("detailed_description", "")
    low = detail.lower()
    has_lens_ban = "no subject looks into the lens" in low or "no character looks into the lens" in low
    has_frontal_ban = "no subject adopts the frontal gaze of the reference sheets" in low
    has_side_view = "profile or three-quarter view" in low
    if "outside witness" not in low or not has_lens_ban:
        fails.append("%s detailed_description 缺英文不看镜头硬句（outside witness / no subject looks into the lens，R52／R54）" % where)
        return 1
    if not has_frontal_ban or not has_side_view:
        fails.append("%s detailed_description 缺「不复制参考图正面取向 + 侧脸/三分之二侧」硬句（R54）" % where)
        return 1
    if "pupil" not in low:
        fails.append("%s detailed_description 没有任何瞳孔方向描述（R54 近景/中近景需 pupils 离轴）" % where)
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


def check_transitions(pr_pairs, seg_pairs, allow_transition, fails, warns):
    """R57：分镜每镜写「承接：」／「转场出：」，分段每段写 Entry:／Exit: 且段段成对。
    整份文件没有任何转场标记的旧稿只 WARN（不回溯），新写的镜／段缺行即 FAIL。"""
    board_marked = any("转场出" in pr for _, pr in pr_pairs)
    if pr_pairs and not board_marked:
        warns.append("分镜：整份没有「转场出：」标记，按旧稿不回溯保留；新写的镜要在「提示词」首行写 `承接：`、末行写 `转场出：<方式>｜末帧：<状态>｜接：<下一镜要接的五项>`（R57）")
    elif board_marked:
        for where, pr in pr_pairs:
            if "承接：" not in pr and "承接:" not in pr:
                fails.append(where + "：提示词缺「承接：」行（R57：本集首镜写「本集开篇，首帧状态」，同场接下镜写上一镜末帧的姿势／重心／手持物／朝向／光位，跨场写「hard cut 至 场名，不沿用上一场轴线」）")
            if "转场出：" not in pr and "转场出:" not in pr:
                fails.append(where + "：提示词缺「转场出：」行（R57：应写「<方式>｜末帧：<定格状态>｜接：<下一镜要接的五项>」）")
            m = re.search(r"转场出[：:]([^\n]*)", pr)
            if m and not any(k in m.group(1) for k in TRANSITION_WORDS):
                warns.append(where + "：「转场出」没写清单内的方式（同向运镜／动作匹配／遮挡转场／出入画跟随／光影过渡／跨场硬切），请确认（R57）")

    seg_marked = any(RE_ENTRY.search(d) or RE_EXIT.search(d) for _, d in seg_pairs)
    if seg_pairs and not seg_marked:
        warns.append("分段：整份没有 `Entry:`／`Exit:`，按旧稿不回溯保留；新写的段要在 detailed_description 里镜头块前写 Entry、末镜之后台词块之前写 Exit（R57）")
    elif seg_pairs:
        for where, d in seg_pairs:
            if not RE_ENTRY.search(d):
                fails.append(where + "：detailed_description 缺 `Entry:`（R57：写上一段末帧状态，首拍只停不新起动作）")
            if not RE_EXIT.search(d):
                fails.append(where + "：detailed_description 缺 `Exit:`（R57：写定格状态＋停留三五帧＋交接方式，本集末段写 held to the last frame）")
            m = RE_EXIT.search(d)
            if m:
                tail = (d[m.end():].split("\n")[0] or "")
                if "episode ends" in tail.lower():
                    continue
                if not any(k in tail for k in TRANSITION_WORDS):
                    warns.append(where + "：`Exit:` 没写清单内的交接方式，请确认（R57）")

    if not allow_transition:
        for where, txt in list(pr_pairs) + list(seg_pairs):
            for w in TRANSITION_BAN:
                if w in txt:
                    fails.append(where + "：出现「" + w + "」；黑场／闪白／叠化／淡入淡出默认禁用，只有用户当次点名才写（R57）")
                    break


def check_prompt_detail(pr, where, fails):
    """R50：分镜提示词按动作顺序写细。缺起幅、动作句过短即 FAIL。"""
    lines = [re.sub(r"^[*-]\s+", "", l.strip()) for l in pr.splitlines() if not DIALOGUE_LINE.match(l.strip())]
    lines = [l for l in lines if l and not l.startswith("约束")]
    if not lines:
        return 0
    bad = 0
    if not any(l.startswith("起幅") for l in lines):
        fails.append("%s 提示词缺「起幅：」（R50 起幅要写空间与机位）" % where)
        bad += 1
    short = 0
    for l in lines:
        if l.startswith(("切：", "切:", "转场", "承接")):
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
    """返回 {字段名: 该字段所在行之后到下一个字段之前的原文}。
    分段六段是裸字段行（subject_definitions: 等，无 `- ` 前缀），
    元数据字段取值必须在第一个裸字段行处截断，否则会把六段正文吞进元数据。"""
    body = _norm_md(body)
    hits = list(re.finditer(r"^[*-]\s*(%s)\s*[:：]" % "|".join(SHOT_FIELDS + SEG_FIELDS), body, re.M))
    bare = list(re.finditer(r"^[ \t]{0,6}[a-z_]+\s*:\s*$", body, re.M))
    d = {}
    for i, h in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
        for b in bare:
            if b.start() > h.end():
                end = min(end, b.start())
                break
        # 分镜九栏：下一个同层级「- 字段：」行即截断，子行（台词原文）随主栏保留
        tail = body[h.end():end]
        next_sub = re.search(r"^[*-]\s*", tail, re.M)
        if next_sub:
            tail = tail[:next_sub.start()]
        d.setdefault(h.group(1), tail)
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


def check_prompt_terms(txt, where, fails):
    """R55.8/R55.10：生图提示词不许写画面负面词、8K 装饰词与实体器材名。"""
    if not txt:
        return
    banned = ("8K", "8k", "超清", "大师之作", "质感拉满",
              "不要模糊", "不要畸形", "不要多余手指", "不要四仰八叉")
    hits = 0
    for line in txt.splitlines():
        if "提示词" not in line:
            continue
        for term in banned:
            if term in line:
                hits += 1
                fails.append("%s 生图提示词出现 R55 禁用词「%s」：%s"
                             % (where, term, line.strip()[:60]))
    if hits > 3:
        fails.append("%s 另有 %d 处 R55 禁用词，未逐条列出（R55）" % (where, hits - 3))


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
A_ITEMS = ["面部特写", "正面", "侧面", "背面"]
LEGACY_A_NAMES = ("三视图", "面部特征", "服装结构", "发型与配饰", "身体比例")


def check_char_assets(txt, fails, warns):
    """R28：人物资产只有四项（面部特写／正面／侧面／背面），不分 A／B 层、不写本集选择；
    每条须是可粘提示词并带图槽；旧式 A／B 分层与 A1–A5 只提醒不判失败（不回溯）。"""
    blocks = list(RE_CHAR_BLOCK.finditer(txt))
    if not blocks:
        fails.append("人物资产.md 没有角色段（应为「## C01 周野」）（R28）")
        return set()

    ids = {b.group(1) for b in blocks}
    if RE_CHAR_CHOICE.search(txt) or "### A 资产" in txt or "### B 资产" in txt:
        warns.append("人物资产.md 仍是旧式 A／B 分层（`本集选择` 或 `### A 资产`／`### B 资产`）；"
                     "新口径只出四项提示词（面部特写／正面／侧面／背面），不分层、不写选择行。"
                     "旧资产按不回溯保留，下次重出该角色时改四项（R28）")
        return ids

    for i, b in enumerate(blocks):
        cid = b.group(1)
        end = blocks[i + 1].start() if i + 1 < len(blocks) else len(txt)
        body = txt[b.end():end]
        heads = re.findall(r"^####\s*A(\d)\s*(.*)$", body, re.M)
        digits = {h[0] for h in heads}
        head_names = " ".join(h[1] for h in heads)
        if digits == set("12345") or any(k in head_names for k in LEGACY_A_NAMES):
            warns.append("%s 是旧式五项资产（%s）；新口径为 A1 面部特写、A2 正面、A3 侧面、A4 背面，四个图槽。"
                         "旧资产按不回溯保留，下次重出该角色时改四项（R28）"
                         % (cid, "、".join(sorted(digits))))
            continue
        if len(heads) < 4 or digits != set("1234"):
            fails.append("%s 的小节应为 A1–A4 四项（面部特写／正面／侧面／背面），当前是 %s（R28）"
                         % (cid, "、".join(sorted(digits)) or "无"))
        for kw in A_ITEMS:
            if kw not in body:
                fails.append("%s 缺「%s」一节（R28）" % (cid, kw))
        lines = [l for l in body.splitlines() if l.strip().startswith("- ") and "｜" in l]
        if not lines:
            fails.append("%s 没有任何条目" % cid)
        for l in lines:
            if "提示词" not in l:
                fails.append("%s 有条目没写成提示词（应以「提示词：」开头，能直接粘去出图）：%s"
                             % (cid, l.strip()[:36]))
                break
        for l in lines:
            if not SLOT.search(l):
                fails.append("%s 有条目没写「图槽：@图片 N」：%s" % (cid, l.strip()[:36]))
                break
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



STYLE_DECL = re.compile(r"参考画风[：:]\s*(REF-\d{3})")
STYLE_DECL_OLD = re.compile(r"画风[：:]\s*(REF-\d{3})")
STYLE_TAIL = re.compile(r"参考画风\s*(?:按)?\s*(REF-\d{3})")
STYLE_TAIL_OLD = re.compile(r"画风\s*按\s*(REF-\d{3})\s*[：:]")
STYLE_ANY = re.compile(r"(REF-\d{3})")
STYLE_STORY = re.compile(r"本剧|剧情|形象|人设")


def check_line_order(field, where, label, fails):
    """R34：台词索引／说话人索引按 ①②③ 排，不许写时间码。"""
    text = field or ""
    if TIME_CODE_RE.search(text):
        fails.append("%s「%s」写了时间码：%s（R13 不写时间码，按 ①②③ 排）" % (where, label, text.strip()[:30]))
    nums = re.findall(r"[①②③④⑤⑥⑦⑧⑨]", text)
    if nums and nums != sorted(set(nums), key="①②③④⑤⑥⑦⑧⑨".index):
        fails.append("%s「%s」说话顺序颠倒：%s（R34）" % (where, label, text.strip()[:30]))


def check_style(texts, fails, warns):
    """R64（2026-11-26 起）：画风由「锁」改成「参考」——参考图只给质感／配色／材质／打光，
    形象一律按剧情写，不符就以剧情为准。
    允许一集两套参考：人物一套（REF-900 默认／REF-001 用户图／REF-000 文字），
    场景与道具一套（REF-902 默认／REF-002 用户给，可沿用人物号）。
    人物资产.md 用人物号；场景资产.md 用场景道具号；资产提示词.md 按小节分别对号；
    每条带「提示词」的条目都要写 `参考画风 REF-xxx`（可后跟一句取舍说明），编号与本层对号，
    并且提示词里要写到本剧形象；旧的 `画风：REF-…` / `画风 按 REF-…：` 按不回溯只提醒。"""
    def codes_of(txt):
        return sorted(set(STYLE_DECL.findall(txt)))

    decls, legacy = {}, {}
    for name, txt in texts.items():
        cs = codes_of(txt)
        if cs:
            decls[name] = cs
            continue
        olds = sorted(set(STYLE_DECL_OLD.findall(txt)))
        if olds:
            legacy[name] = olds
    if legacy and not decls:
        warns.append("画风声明还是旧口径「%s」（R64 起改「参考画风：REF-…（参考，不照搬）」＋第二行「本剧形象：…」；旧稿不回溯）"
                     % "、".join("%s 写「画风：%s」" % (n, "、".join(c)) for n, c in legacy.items()))
        decls = legacy
    if not decls:
        fails.append("三份资产文件都没有画风声明：人物写「参考画风：REF-900 冰蓝仙侠·三维写实（参考，不照搬）」，场景道具写「参考画风：REF-902 雨雾仙侠·实景质感（参考，不照搬）」，再各写一行「本剧形象：…」（R31／R64）")
        return ""

    all_codes = sorted({c for cs in decls.values() for c in cs})
    if len(all_codes) > 2:
        fails.append("参考画风超过两套：%s（一集最多「人物一套＋场景道具一套」，R64）"
                     % "、".join(all_codes))

    # 新口径要求两行头：参考画风＋本剧形象
    for name, txt in texts.items():
        if name in decls and name not in legacy and not re.search(r"^.*本剧形象[：:]", txt, re.M):
            fails.append("%s 缺「本剧形象：…」一行：参考画风只给质感，形象必须按剧情写（R64）" % name)

    # 人物号：REF-900 是内置默认人物锁，出现时优先；否则取第一个不是 REF-902 的编号。
    # 场景道具号：REF-902 是内置默认场景道具锁，出现时优先；否则取不同于人物号的编号。
    if "REF-900" in all_codes:
        char_code = "REF-900"
    else:
        char_code = next((c for c in all_codes if c != "REF-902"), all_codes[0])
    if "REF-902" in all_codes:
        scene_code = "REF-902"
    else:
        scene_code = next((c for c in all_codes if c != char_code), char_code)

    for name, cs in decls.items():
        if len(cs) > 1 and name != "资产提示词.md":
            fails.append("%s 声明了多个参考画风编号：%s（人物资产只写人物那套，场景资产只写场景道具那套，R64）"
                         % (name, "、".join(cs)))

    legacy_tails = []
    for name, txt in texts.items():
        if name not in decls:
            fails.append("%s 缺「参考画风：REF-…」声明（R31／R64）" % name)
            continue
        if name == "人物资产.md":
            expect = char_code
        elif name == "场景资产.md":
            expect = scene_code
        else:
            # 资产提示词.md：按「## 人物／## 场景／## 道具」小节分号
            expect = None

        section = "人物"
        bad, old_tail, no_story = [], 0, []
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
                if STYLE_TAIL_OLD.findall(st):
                    old_tail += 1
                else:
                    bad.append((st[:26], "缺「参考画风 REF-…」", want))
                continue
            if any(c != want for c in tails):
                bad.append((st[:26], "用错号 " + "、".join(tails), want))
            if not STYLE_STORY.search(st):
                no_story.append(st[:26])
        if old_tail:
            legacy_tails.append("%s %d 条" % (name, old_tail))
        if bad:
            sample = "；".join("%s（%s，应为 %s）" % (a, b, c) for a, b, c in bad[:3])
            fails.append("%s 有 %d 条提示词参考画风对不上：%s（R64）" % (name, len(bad), sample))
        if no_story:
            warns.append("%s 有 %d 条提示词没写到本剧形象（%s）：参考画风只作质感参考，形象要按剧情写，不符就以剧情为准（R64）"
                         % (name, len(no_story), "、".join(no_story[:3])))

    if legacy_tails:
        warns.append("提示词尾巴还是旧口径「画风 按 REF-…：」（%s）：R64 起改「参考画风 REF-xxx（取其质感，形象按本剧）」，旧稿不回溯"
                     % "、".join(legacy_tails))

    return "%s／%s（参考，不照搬）" % (char_code, scene_code) if len(all_codes) > 1 \
        else "%s（参考，不照搬）" % char_code


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


PLACEHOLDER_RE = re.compile(r"(人物|场景|道具)[一二三四五六七八九十]{1,3}")
REAL_ID_RE = re.compile(r"@(?:C|S|P)\d{2}")


def check_placeholders(shots, board_txt, seg_txt, fails, warns):
    """R58：反推没有实拍资产图，图槽一律写人物一／场景一／道具一占位，不编 C／S／P 真编号。"""
    for name, txt in (("分镜.md", board_txt), ("分段视频提示词.md", seg_txt)):
        if "已出图" in txt or "见附图" in txt:
            fails.append("%s 出现「已出图」／「见附图」；反推只交提示词与占位，不出图、不暗示有图（R58／R30）" % name)
        ids = REAL_ID_RE.findall(txt)
        if ids:
            fails.append("%s 出现 %d 处 C／S／P 真编号（如 %s）；反推时没有资产表，图槽必须改写成占位名（R58）"
                         % (name, len(ids), ids[0]))
    names = set()
    for s in shots:
        sid = s["m"].group(1)
        where = "镜头 %s" % sid
        ref = field_lines(s["body"]).get("参考图", "")
        found = [m.group(0) for m in PLACEHOLDER_RE.finditer(ref)]
        for f in found:
            names.add(f)
        if "无" in ref and not found and "@图片" not in ref:
            continue
        if not found:
            fails.append("%s「参考图」栏没有占位名（应写 `@图片 N 人物一（空缺占位）`／`场景一（空缺占位）`／`道具一（空缺占位）`，R58）" % where)
    if not names:
        warns.append("分镜.md 里没有任何 `人物一／场景一／道具一` 占位名；若本片确有主体入画，按 R58 补占位并顺排人物二、场景二")
    else:
        warns.append("反推占位：人物 %d 名、场景 %d 名、道具 %d 名（人物：%s／场景：%s／道具：%s）"
                     % (len([n for n in names if n.startswith("人物")]),
                        len([n for n in names if n.startswith("场景")]),
                        len([n for n in names if n.startswith("道具")]),
                        "、".join(sorted(n for n in names if n.startswith("人物"))) or "—",
                        "、".join(sorted(n for n in names if n.startswith("场景"))) or "—",
                        "、".join(sorted(n for n in names if n.startswith("道具"))) or "—"))
    if "空缺占位" not in board_txt:
        warns.append("分镜.md 的图槽没写「（空缺占位）」标注；建议在每个 `@图片 N 人物一` 后补这四个字，方便后续挂真图（R58）")
    for n in sorted(names):
        if n not in seg_txt:
            warns.append("占位名「%s」在 分段视频提示词.md 里没出现；分段的 `<Subject N>（图片名：…）` 要与分镜占位同名（R58）" % n)


VFX_KEYS = ("形态", "光源", "起", "中", "收")
VFX_BANNED = ("炫酷", "特效拉满", "光效强烈", "光效拉满", "特效炸裂", "大片感特效")


FIGHT_EN = ("blades lock", "blade lock", "cross-parry", "shockwave", "dust wave",
            "stone cracks", "cracks", "debris", "gravel", "stagger", "bracing back",
            "bracing", "thrown back", "rebound", "sparks", "armor chips", "motion blur",
            "upward cut", "downward chop", "horizontal sweep", "ground-skimming",
            "airborne spin", "charge", "drive off", "send the shoulder")

FIGHT_BANNED = ("两人激烈交锋", "激烈交锋", "一顿猛攻", "不分胜负", "打成一片",
                "激战正酣", "打得难分难解", "打得难解难分")

RE_FIGHT_ROUND = re.compile(r"^[ \t]*[-*]?\s*回合\s*[0-9一二三四五六七八九十]+\s*[：:]")
RE_FIGHT_TAG = re.compile(r"^[ \t]*\[FIGHT\]", re.I)
RE_CIRCLED = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")


def check_fight(script_txt, board_txt, seg_txt, fails, warns):
    """R61：有打斗的场，回合三段齐全、声音分层、分镜一镜一回合且受力有结果、分段有打斗英文词。"""
    if not script_txt:
        return (0, 0)
    scenes = []
    cur = None
    for line in script_txt.splitlines():
        m = RE_SCENE_ID.match(line)
        if m:
            cur = [m.group(1), []]
            scenes.append(cur)
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is not None:
            cur[1].append(line)

    fight_scenes = 0
    rounds_total = 0
    for sid, lines in scenes:
        rounds = []
        for ln in lines:
            s = ln.strip()
            if RE_FIGHT_ROUND.match(ln) or RE_FIGHT_TAG.match(ln):
                rounds.append(s)
        if not rounds:
            if any("打斗回合" in l for l in lines):
                fails.append("%s 写了「打斗回合」标题但没有回合行；每回合一行 `- 回合 N：谁先动｜接触点：…｜结果：…`（R61.2）" % sid)
            continue
        fight_scenes += 1
        rounds_total += len(rounds)
        if len(rounds) > 6:
            warns.append("%s 有 %d 个回合／一组超过 6 个回合；按剧情拆成 2–3 组打斗，一组 3–6 回合（R61.2）" % (sid, len(rounds)))
        for r in rounds:
            body = r.split("：", 1)[-1] if "：" in r else r
            body = re.sub(r"^\[FIGHT\]\s*", "", body).strip()
            segs = [p for p in re.split(r"[｜|]", body) if p.strip()]
            if len(segs) < 3:
                fails.append("%s 的回合行缺段：`%s`；必须写全 谁先动｜接触点｜结果 三段（R61.2）" % (sid, r[:40]))
                continue
            if "接触点" not in r:
                warns.append("%s 的回合行没标「接触点」；写成 `谁先动｜接触点：在哪一高度哪一角度接上｜结果：谁被推成什么姿态`（R61.2）" % sid)
        sfx = [l for l in lines if l.strip().startswith("[SFX]")]
        if not sfx:
            fails.append("%s 有打斗但没有任何 `[SFX]` 行；打斗声音要分层（低频底／瞬时声／空间余响），一句「打斗声」不合格（R61.5）" % sid)
        elif len(rounds) >= 3 and len(sfx) < 2:
            warns.append("%s 有 %d 个回合但只有 %d 条 `[SFX]`；建议一回合一行写三层声（R61.5）" % (sid, len(rounds), len(sfx)))
        for w in FIGHT_BANNED:
            if any(w in l for l in lines):
                fails.append("%s 出现空词「%s」；每一击都要写成可见的接触点与受力结果（R61.7）" % (sid, w))
                break

    if not fight_scenes:
        return (0, 0)

    # 分镜层：打斗场的镜数、镜长、「动作先后」拍数
    board_scenes = split_blocks(board_txt, RE_BOARD_SCENE)
    checked = 0
    for blk in board_scenes:
        head = blk["m"].group(0) + "\n" + blk["body"][:300]
        if not any(k in head for k in ("打斗", "激战", "交手", "对冲", "为战", "厮杀")) and "来源：" not in head:
            continue
        shots = split_blocks(blk["body"], RE_SHOT)
        if not shots:
            continue
        checked += 1
        if len(shots) < 6:
            warns.append("%s 的打斗场只有 %d 镜；起势 1 ＋ 交手 ≥4 ＋ 收势 1，一场 ≥6 镜（R61.6）"
                         % (blk["m"].group(0).strip(), len(shots)))
        for sh in shots:
            where = "镜头 " + sh["m"].group(1)
            fields = field_lines(sh["body"])
            dur = re.search(r"镜长\s*(\d+)\s*秒", fields.get("拍摄手法", ""))
            if dur and int(dur.group(1)) > 3:
                warns.append("%s 打斗镜 %s 秒，超过 3 秒；打斗镜 1–2 秒为主、最长 3 秒（R61.6）"
                             % (where, dur.group(1)))
            beats = RE_CIRCLED.findall(fields.get("动作先后", ""))
            if len(beats) < 3:
                warns.append("%s 的「动作先后」只写了 %d 拍；打斗镜 ≥3 拍（蹬地／送肩 → 挥出 → 咬合 → 爆开 → 后仰／退步）（R61.6）"
                             % (where, len(beats)))
    if checked:
        for w in FIGHT_BANNED:
            if w in board_txt:
                fails.append("分镜.md 出现空词「%s」；打斗镜要写具体接触点与受力结果（R61.7）" % w)
                break

    # 分段层：打斗英文词与受力结果
    if seg_txt:
        low = seg_txt.lower()
        if not any(k in low for k in FIGHT_EN):
            warns.append("分段视频提示词.md 没有任何打斗英文词（blades lock／shockwave／dust wave／stone cracks／stagger…）；"
                         "打斗回合要落进 detailed_description，术语见 `references/打斗模板.md` 第三节（R61.8）")
    return (fight_scenes, rounds_total)


RE_SEQ_HEAD = re.compile(r"^[ \t]*[①②③④⑤⑥⑦⑧⑨⑩]")
RE_TURN_HEAD = re.compile(r"^[ \t]*\*\*说话顺序\*\*[：:]", re.M)
RE_VOICE_TBL = re.compile(r"^##\s*声音设定", re.M)
RE_PERF_TBL = re.compile(r"^##\s*表演总则", re.M)
RE_CN_PAREN = re.compile(r"（[^）]{1,12}）")
DIALOGUE_PAREN_OK = ("（听不清）", "(听不清)")


def check_dialogue_perf(script_txt, board_txt, seg_txt, fails, warns):
    """R62：对话与人物表情三层——说话顺序、台词干净、分镜台词栏只写次序、分段说话人与口型句。"""
    dlg_total = 0
    turns_total = 0

    if script_txt:
        blocks = split_blocks(script_txt, RE_SCENE_ID)
        no_turn_scenes = []
        for blk in blocks:
            sid = blk["m"].group(1)
            body = blk["body"]
            turns = [m for m in RE_TURN_HEAD.finditer(body)]
            turns_total += len(turns)
            lines = []
            for m in RE_DIALOGUE.finditer(body):
                spk = m.group(1).strip()
                if any(ch in spk for ch in "*-—|｜"):
                    continue
                if spk in ("说话顺序", "表演总则", "声音设定", "本集结尾状态"):
                    continue
                lines.append((spk, m.group(2)))
            if len(lines) >= 5 and not turns:
                no_turn_scenes.append(sid)
            for spk, text in lines:
                dlg_total += 1
                if "[Chinese]" in text:
                    fails.append("%s 剧本台词行带了 `[Chinese]`；`[Chinese]` 只出现在分段台词块（R62.3）：%s：%s"
                                 % (sid, spk, text.strip()[:30]))
                hits = [p for p in RE_CN_PAREN.findall(text) if p not in DIALOGUE_PAREN_OK]
                if hits:
                    warns.append("%s 剧本台词行带括注「%s」；语气与表情写进叙述句，台词只留原文（R62.3）"
                                 % (sid, hits[0]))
        if no_turn_scenes:
            warns.append("%s 有台词但没有「**说话顺序**：① … → ② …」；对话场先排话轮次序（R62.2）"
                         % "、".join(no_turn_scenes[:3]))
        if dlg_total >= 40:
            if not RE_VOICE_TBL.search(script_txt):
                warns.append("剧本写了 %d 句台词却没有 `## 声音设定`（一人一行：音色／语速／音量／句尾／特殊情况）（R62.6）" % dlg_total)
            if not RE_PERF_TBL.search(script_txt):
                warns.append("剧本写了 %d 句台词却没有 `## 表演总则`（情绪先定调／独白不张嘴／一句一人／全片不配乐）（R62.6）" % dlg_total)

    if board_txt:
        board_shots = split_blocks(board_txt, RE_SHOT)
        few_tone = []
        for sh in board_shots:
            where = "镜头 " + sh["m"].group(1)
            fields = field_lines(sh["body"])
            line = fields.get("台词", "").strip()
            if not line:
                continue
            if "[Chinese]" in line:
                fails.append("%s「台词」栏抄了带 [Chinese] 的台词原文；分镜只写次序（R62.7）" % where)
            elif not RE_SEQ_HEAD.match(line) and line != "无":
                fails.append("%s「台词」栏不是 `① 名 → ② 名` 次序（也不是「无」）；分镜不抄台词原文（R62.7）：%s"
                             % (where, line[:30]))
            expr = fields.get("表情", "")
            if expr and ("成" not in expr) and ("特写" not in fields.get("拍摄手法", "")):
                few_tone.append(where)
        if dlg_total >= 40 and len(few_tone) * 2 > len(board_shots):
            warns.append("%d/%d 镜的「表情」栏没写「几成」；表情两层＝情绪＋几成＋对着谁，再写肌肉清单（R62.8）"
                         % (len(few_tone), len(board_shots)))

    if seg_txt:
        segs = split_blocks(seg_txt, RE_SEG)
        for g in segs:
            num = g["m"].group(1)
            where = "第 %s 段" % num
            f = field_lines(g["body"])
            spk = f.get("说话人", "").strip()
            sec = _seg_sections(g["body"])
            detail = _norm_md(sec.get("detailed_description", ""))
            lines = list(RE_SEG_DIALOGUE.finditer(detail))
            if spk and spk != "无" and not re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩]", spk):
                fails.append("%s「说话人」行不是 `① (S1) 名字 → ② (S2) 名字` 格式（R62.10）：%s" % (where, spk[:30]))
            elif spk and spk != "无" and "(S1)" not in spk:
                fails.append("%s「说话人」行缺 `(S1)` 首个台词编号（R62.10）：%s" % (where, spk[:30]))
            if spk == "无" and lines:
                fails.append("%s「说话人」写「无」但 detailed_description 有 %d 句台词（R62.10）" % (where, len(lines)))
            if spk and spk != "无" and not lines:
                fails.append("%s「说话人」写了说话人但台词块是空的（R62.10）" % where)
    return (dlg_total, turns_total)


def check_vfx(script_txt, board_txt, seg_txt, fails, warns):
    """R59：有特效的场，[VFX] 五段写全、[SFX] 一特效一行、[LIGHT] 不缺席，特效词进分镜与分段。"""
    if not script_txt:
        return 0
    scenes = []
    cur = None
    for line in script_txt.splitlines():
        m = RE_SCENE_ID.match(line)
        if m:
            cur = [m.group(1), []]
            scenes.append(cur)
            continue
        if line.startswith("## "):
            cur = None
            continue
        if cur is not None:
            cur[1].append(line)

    total = 0
    for sid, lines in scenes:
        vfx = [l.strip() for l in lines if l.strip().startswith("[VFX]")]
        sfx = [l.strip() for l in lines if l.strip().startswith("[SFX]")]
        light = [l.strip() for l in lines if l.strip().startswith("[LIGHT]")]
        if not vfx:
            continue
        total += len(vfx)
        if len(vfx) > 4:
            fails.append("%s 有 %d 条 [VFX]，一场超过 4 个特效；拆场或并成同一条（R59.2）" % (sid, len(vfx)))
        for v in vfx:
            body = v[len("[VFX]"):]
            name = re.split(r"[｜|]", body)[0].strip()
            miss = [k for k in VFX_KEYS if ("%s" % k) not in body]
            if miss:
                fails.append("%s 的 [VFX]「%s」缺 %s 段；应写 `名称｜形态｜光源｜起｜中｜收`（R59.3／R39）"
                             % (sid, name[:18], "／".join(miss)))
            parts = [p.strip() for p in re.split(r"[｜|]", body)][1:]
            labels = [p.split("：")[0].strip() for p in parts if p]
            if labels[:5] and labels[:5] != list(VFX_KEYS):
                warns.append("%s 的 [VFX]「%s」五段顺序是 %s，应为 形态→光源→起→中→收（R59.3）"
                             % (sid, name[:18], "→".join(labels[:5])))
            for w in VFX_BANNED:
                if w in v:
                    fails.append("%s 的 [VFX] 出现禁用词「%s」；必须写成可拍的材质、颜色、结构与体积（R39.5／R59.3）"
                                 % (sid, w))
        if len(sfx) < len(vfx):
            fails.append("%s 有 %d 条 [VFX] 但只有 %d 条 [SFX]；一特效一行声音，写三层（低频底／瞬时声／余响），R59.7"
                         % (sid, len(vfx), len(sfx)))
        if not light:
            warns.append("%s 有特效但没有 [LIGHT] 行；特效自发光就是主光，必须写照亮谁、投影朝哪（R40／R59.4）" % sid)

    if total:
        warns.append("特效场合计 [VFX] %d 条（R59）" % total)
        # 分镜层：每场至少要把本场一个特效名落进这一场（场标题括号或提示词里）
        board_scenes = split_blocks(board_txt, RE_BOARD_SCENE)
        for sid, lines in scenes:
            vfx = [l.strip()[5:].split("｜")[0].strip() for l in lines if l.strip().startswith("[VFX]")]
            if not vfx:
                continue
            nm = [n for n in vfx if re.split(r"[｜|]", n)[0].strip()]
            keys = [re.sub(r"^(?:道具|场景|人物)[一二三四五六七八九十]+", "", n).strip() for n in nm]
            keys = [k for k in keys if k]
            hit = None
            for blk in board_scenes:
                head = blk["m"].group(0)
                if sid in head:
                    hit = blk["body"] + head
                    break
            if hit is None:
                warns.append("%s 有 [VFX] 但分镜.md 找不到这一场的场块；场标题必须带「来源：%s」（R59.5）" % (sid, sid))
            elif keys and not any(k in hit for k in keys):
                warns.append("%s 的特效名（%s）一个都没出现在分镜这一场；场标题括号里要先列本场特效清单，再落进四处（R59.5）"
                             % (sid, "、".join(keys[:3])))
        # 分段层：英文术语是否真落进去了
        if not re.search(r"rune|arc|halo|pillar|formation|array|vortex|chain|lightning|flame|glow|ward",
                         seg_txt, re.I):
            warns.append("分段视频提示词.md 里没有任何特效英文词（rune／arc／halo／pillar／formation…）；"
                         "特效阶段要写进 detailed_description，术语见 `references/特效模板.md` 第三节（R59.6）")
        for name, txt in (("剧本.md", script_txt), ("分镜.md", board_txt)):
            if re.search(r"配乐\s*[:：]|背景音乐|BGM|b\s?g\s?m", txt):
                fails.append("%s 写了配乐／BGM；特效声只写画内 `[SFX]`／`overall_soundscape`（R25／R59.7）" % name)
    return total


def check_seam(seg_detail_pairs, fails, warns):
    """R60：相邻段之间必须二选一——A 无缝接（两段都写 hand-off seamless），
    或 B 显式转场（前段 Transition out: 方式 — 可见动作；后段 Transition in: 同一方式）。"""
    if len(seg_detail_pairs) < 2:
        return 0
    declared_any = any(("seamless" in d) or ("Transition out:" in d) or ("Transition in:" in d)
                       for _, d in seg_detail_pairs)
    pairs = 0
    issues = []
    for i in range(len(seg_detail_pairs) - 1):
        (w1, d1), (w2, d2) = seg_detail_pairs[i], seg_detail_pairs[i + 1]
        pairs += 1
        seamless = ("seamless" in d1) and ("seamless" in d2)
        out_m = re.search(r"Transition out:\s*([^\n]+)", d1)
        in_m = re.search(r"Transition in:\s*([^\n]+)", d2)
        if out_m and in_m:
            m1 = re.split(r"[—–]", out_m.group(1))[0].strip().strip("，,;；:：")
            m2 = re.split(r"[—–]", in_m.group(1))[0].strip().strip("，,;；:：")
            # 方式只取方法名：`cut — to 场景`／`cut to 场景` 都归一到 `cut`
            m1 = re.sub(r"\s*(?:to|from|到|从)\s+.*$", "", m1).strip()
            m2 = re.sub(r"\s*(?:to|from|到|从)\s+.*$", "", m2).strip()
            if m1 and m2 and (m1 not in m2) and (m2 not in m1):
                issues.append("%s 的 `Transition out:` 方式「%s」与 %s 的 `Transition in:` 方式「%s」不一致；两行必须同名（R60）"
                              % (w1, m1, w2, m2))
            if re.search(r"Transition out:[^\n]*[—–][^\n]*", d1) is None:
                issues.append("%s 的 `Transition out:` 只有方式、没写看得见的转场动作；要写成「方式 — 甩镜／前景遮挡／推入虚焦／光效吞满」这样的一拍（R60）" % w1)
            if re.search(r"Transition in:[^\n]*[—–][^\n]*", d2) is None:
                issues.append("%s 的 `Transition in:` 只有方式、没写从什么画面进来；要写成「方式 — 从哪个画面进来」（R60）" % w2)
            continue
        if seamless:
            continue
        if out_m or in_m:
            issues.append("%s → %s 的段间转场只写了一半：`Transition out:` 在前段、`Transition in:` 在后段，两段都要写（R60）"
                          % (w1, w2))
        else:
            issues.append("%s → %s 没写段间衔接：要么两段都写 `hand-off seamless`（A 无缝接），要么前段 `Exit` 后写 `Transition out: <方式> — <看得见的转场动作>`、后段 `Entry` 后写 `Transition in: <同一方式>`；只在 Exit 里写 hard cut 不算（R60）"
                          % (w1, w2))
    if declared_any:
        fails.extend(issues)
        a_cnt = sum(1 for i in range(len(seg_detail_pairs) - 1)
                    if "seamless" in seg_detail_pairs[i][1] and "seamless" in seg_detail_pairs[i + 1][1])
        b_cnt = sum(1 for i in range(len(seg_detail_pairs) - 1)
                    if "Transition out:" in seg_detail_pairs[i][1] and "Transition in:" in seg_detail_pairs[i + 1][1])
        warns.append("段间衔接（R60）：%d 对相邻段，A 无缝接 %d 处、B 显式转场 %d 处" % (pairs, a_cnt, b_cnt))
        if pairs and b_cnt > pairs / 2:
            warns.append("B 显式转场 %d 处，超过段间数量一半；同场能无缝就优先走 A（R60.7）" % b_cnt)
    else:
        warns.append("整份分段没有段间衔接声明（`hand-off seamless` 或 `Transition out:`／`Transition in:`），%d 对相邻段按旧稿不回溯；新写的段必须按 R60 二选一：同场写 A 无缝接，换场写 B 显式转场（只写 hard cut 不算）" % pairs)
    return pairs


def check_one_shot(shots, segs, shot_durs, fails):
    """R63：一镜一段。段数=镜数、一段只有一个 [Shot 1]、段时长=对应镜镜长。
    旧格式（段内仍写 At MM:SS.mmm 的打包稿）按不回溯原则只提示、不判错。"""
    at_re = re.compile(r"At\s+\d{2}:\d{2}\.\d{3}")
    n_shots, n_segs = len(shots), len(segs)
    legacy = any(at_re.search(g["body"]) for g in segs)
    multi = []
    for g in segs:
        n = len(RE_SHOT_TAG.findall(g["body"]))
        if n > 1:
            multi.append((g["m"].group(1), n))
    if not legacy:
        if n_segs > n_shots:
            fails.append("分段 %d 段多于分镜 %d 镜：一镜一段不许拆段（R63）" % (n_segs, n_shots))
        elif n_segs < n_shots:
            fails.append("分段 %d 段少于分镜 %d 镜：一镜一段要求段数＝镜数，别把镜头组合进一段（R63）"
                         % (n_segs, n_shots))
        for num, n in multi:
            fails.append("第 %s 段有 %d 个 [Shot]：一段只许一个 [Shot 1]（R63）" % (num, n))
        if n_shots == n_segs:
            ids = [s["m"].group(1) for s in shots]
            for idx, g in enumerate(segs):
                num = g["m"].group(1)
                dd_s = field_lines(g["body"]).get("时长", "").split("\n")[0]
                dd_s = re.sub(r"[^\d]", "", dd_s)
                dd = int(dd_s) if dd_s else None
                sd = shot_durs.get(ids[idx]) if idx < len(ids) else None
                if sd and dd and sd != dd:
                    fails.append("第 %s 段时长 %d 秒 ≠ 镜头 %s 镜长 %d 秒（R63 段长＝镜长）"
                                 % (num, dd, ids[idx], sd))
    return {"shots": n_shots, "segs": n_segs, "legacy": legacy, "multi": len(multi)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--ep", default="EP001")
    ap.add_argument("--skip-script", action="store_true", help="R33 跳过剧本模式：不要求 剧本.md")
    ap.add_argument("--require-handoff", action="store_true", help="R45：缺少或不完整的 项目交接.md 直接判 FAIL")
    ap.add_argument("--reverse", action="store_true",
                    help="R58 视频反推模式：只要求 分镜.md 与 分段视频提示词.md，不要求剧本与三类资产；另查占位命名（人物一／场景一／道具一）")
    ap.add_argument("--allow-transition", action="store_true",
                    help="放行黑场／闪白／叠化／淡入淡出（只在反推原片本身用了这些转法时用）")
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
    required = [board_p, seg_p] + ([] if (args.skip_script or args.reverse) else [script_p])
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

    if args.reverse:
        notes["reverse"] = True
        warns.append("反推模式（R58）：只校验 分镜.md 与 分段视频提示词.md；剧本、三类资产、项目交接均不要求。交付只许给这两份。")
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
    if args.reverse:
        notes["assets"] = 0
    elif legacy:
        warns.append("本集既无 资产提示词.md 也无「场景站位」，按「不回溯」当作旧版文件，跳过 R26／R27；新集必须写。")
    else:
        if not asset_p.is_file():
            fails.append("缺文件：资产提示词.md（人物／场景／道具三节，带 C／S／P 编号）（R27）")
        defined = check_assets(asset_txt, fails)
        check_prompt_terms(asset_txt, "资产提示词.md", fails)
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
    if args.reverse:
        check_placeholders(shots, board_txt, seg_txt, fails, warns)
    else:
        check_coverage(script_txt, board_txt, seg_txt, asset_txt, defined, fails, warns)
        check_handoff(project, args.ep, fails, warns, require=args.require_handoff)

    if char_p.is_file():
        char_txt = read_text(char_p)
        cids = check_char_assets(char_txt, fails, warns)
        check_prompt_terms(char_txt, "人物资产.md", fails)
        notes["char_ids"] = len(cids)
        cm = RE_CHAR_CHOICE.search(char_txt)
        notes["char_choice"] = cm.group(1).strip().upper() if cm else "—"

    if scene_p.is_file():
        scene_txt = read_text(scene_p)
        sids = check_scene_assets(scene_txt, fails, warns)
        check_prompt_terms(scene_txt, "场景资产.md", fails)
        notes["scene_ids"] = len(sids)
        sm2 = RE_CHAR_CHOICE.search(scene_txt)
        notes["scene_choice"] = sm2.group(1).strip().upper() if sm2 else "?"

    # ---------- 画风（R31／R64 参考画风） ----------
    texts = {"资产提示词.md": asset_txt}
    if char_p.is_file():
        texts["人物资产.md"] = read_text(char_p)
    if scene_p.is_file():
        texts["场景资产.md"] = read_text(scene_p)
    style = "" if args.reverse else check_style(texts, fails, warns)
    if style:
        notes["style"] = style

    board_prompt_all = []
    shot_pr_pairs = []
    shot_durs = {}
    stray = []
    for s in shots:
        sid = s["m"].group(1)
        where = "镜头 %s" % sid
        f = field_lines(s["body"])
        for name in SHOT_FIELDS:
            if name not in f:
                fails.append("%s 缺「%s」栏" % (where, name))
        pr = prompt_text(f)
        board_prompt_all.append(pr)
        shot_pr_pairs.append((where, pr))
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
        check_line_order(tl, where, "台词", fails)
        # R14／R23：台词原文只写在「提示词」里；抄进「声音」「台词」栏就是复述，汇总告警
        for _, dtxt in dialogue:
            if len(dtxt) < 2:
                continue
            for col in ("台词", "声音"):
                if dtxt in f.get(col, ""):
                    stray.append("%s「%s」栏" % (where, col))
                    break
            else:
                continue
            break
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

    if stray:
        warns.append("%d 处把台词原文抄进了「声音」／「台词」栏（台词原文只该写在「提示词」，R14 台词只说一遍）；例：%s"
                     % (len(stray), "、".join(stray[:3])))

    if shot_durs and any(v is None for v in shot_durs.values()):
        fails.append("有镜头没在「拍摄手法」里写「镜长 N 秒」，时长合计不可信")

    # ---------- 分段 ----------
    segs = split_blocks(seg_txt, RE_SEG)
    if not segs:
        fails.append("分段视频提示词.md 未找到段标题（应为「## 第 N 段 ｜ 场名」）")

    seg_prompt_all = []
    seg_detail_pairs = []
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
        seg_detail_pairs.append((where, detail))
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

    # ---------- 一镜一段（R63） ----------
    notes["oneshot"] = check_one_shot(shots, segs, shot_durs, fails)

    # ---------- 转场（R57） ----------
    allow_trans = args.allow_transition or ("用户指定转场" in script_txt) or ("转场（用户指定" in board_txt) or ("转场（用户指定" in seg_txt)
    check_transitions(shot_pr_pairs, seg_detail_pairs, allow_trans, fails, warns)

    # ---------- 段间衔接（R60） ----------
    notes["seams"] = check_seam(seg_detail_pairs, fails, warns)

    # ---------- 特效（R59） ----------
    notes["vfx"] = check_vfx(script_txt, board_txt, seg_txt, fails, warns)

    # ---------- 打斗（R61） ----------
    notes["fight"] = check_fight(script_txt, board_txt, seg_txt, fails, warns)

    # ---------- 对话与表情（R62） ----------
    notes["talk"] = check_dialogue_perf(script_txt, board_txt, seg_txt, fails, warns)

    # ---------- 跨文件 ----------
    board_total = sum(v for v in shot_durs.values() if v)
    seg_total = sum(seg_durs)
    if shots and segs and board_total != seg_total:
        fails.append("分镜合计 %d 秒 vs 分段合计 %d 秒，不相等" % (board_total, seg_total))

    # R57/R58：反推按原片时长，不套一集 220–260 秒口径
    if seg_durs and not args.reverse:
        user_sec = re.search(r"用户指定\s*(\d+)\s*秒", script_txt)
        if user_sec:
            if seg_total != int(user_sec.group(1)):
                fails.append("一集总时长 %d 秒，与剧本头部用户指定 %d 秒不一致（R37）"
                             % (seg_total, int(user_sec.group(1))))
        elif not (220 <= seg_total <= 260):
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
    for spk, txt in ([] if args.reverse else dialogue):
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
    "人物资产是否只写了四项（面部特写／正面／侧面／背面）、不分 A／B 层、不写本集选择行、没有擅自补人物档案（R28）",
    "人物资产四项是否齐（面部特写／正面／侧面／背面）、有没有多余的 A／B 分层或本集选择行，四张之间同一张脸与身高比例服装配饰是否一致（R28）",
    "场景资产是否只出了用户点的那层，A2–A4 每条是否可粘提示词带图槽，A3 布局图里画不画得出锚点物，B6 空间规则与 R26 站位是否一致（R29）",
    "三类资产是否都只交了提示词与槽号，没有图片文件、路径或「已出图」说法，交付报告没把提示词说成图片已生成（R30）",
    "一镜一段（R63）：分镜有多少镜、分段是否就有多少段，段名与镜名是否同名，每段是否只有一个 [Shot 1] 且没有段内时间码；不足 4 秒的镜是否已在分镜层并进相邻镜（动作一句没丢），超过 15 秒的镜是否已拆成两镜",
    "转场（R57）：每镜「转场出」的末帧状态与下一镜「承接」的五项（动作／朝向／重心／手持物／光位）是否真对得上；前段 Exit 与后段 Entry 的方式与末帧是否同一套说法；是否出现黑场／闪白／叠化／淡入淡出，或转场遮脸遮嘴、拦腰打断正在说的台词",
    "打斗（R61）：该场「打斗回合」每回合三段（谁先动／接触点／结果）是否都写得出；正文四句式是否落地、身体是否写到关节肌肉承重；有没有连续三回合同一人进攻、有没有一处局面变化；分镜是不是一镜一回合、起势→接触→受力顺序不乱、每击是否都落了可见结果（R61）",
    "对话与表情（R62）：台词是不是一句一人、每 1–4 句之间有一句身体准备；表情两层（情绪＋几成＋对着谁／眉·眼·鼻·嘴·颈·手）是否齐；正反打有没有连切超过 3 次、听者反应镜有没有抢戏；说话人与听者的口型是否分开写、独白镜是否唇齿闭合；`overall_soundscape` 是否写了嗓音质感而不是台词（R62）",
    "参考画风（R64）：三份资产头两行是不是「参考画风：REF-…（参考，不照搬）」＋「本剧形象：…」；每条提示词是否先写本剧形象（身份／年龄／体型／发型发色／服装款式与磨损／伤势／随身物；场景写剧情要求的布局与时代痕迹；道具写剧情要求的形状尺寸材质磨损），再写参考画风只取质感／配色／材质／打光；有没有照搬参考图里的人脸长相、姿态、构图、服装款式、建筑与道具种类；参考图与剧情冲突时是不是以剧情为准",
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
            print("人物资产：角色=%s 个（四项，不分层）" % info["char_ids"])
        if info.get("scene_ids"):
            print("场景资产：选择=%s，场景=%s 个" % (info.get("scene_choice"), info["scene_ids"]))
        if info.get("style"):
            print("参考画风：%s（只作质感参考，形象按剧情）" % info["style"])
        if notes.get("camera_gaze"):
            print("R49 看镜头写法：%d 处（明细见 FAIL）" % notes["camera_gaze"])
        if notes.get("fight") and notes["fight"][0]:
            print("R61 打斗：%d 场、%d 个回合" % (notes["fight"][0], notes["fight"][1]))
        if notes.get("talk") and notes["talk"][0]:
            print("R62 对话：%d 句台词、%d 个话轮" % (notes["talk"][0], notes["talk"][1]))
        if notes.get("oneshot"):
            o = notes["oneshot"]
            tail = "（旧格式多镜打包，按不回溯未判错）" if o["legacy"] else ""
            print("R63 分段＝镜数 %d／段数 %d%s" % (o["shots"], o["segs"], tail))
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

