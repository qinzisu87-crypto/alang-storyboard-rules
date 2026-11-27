# 官方 Ref2VA 分镜视频规范（H3 参考生视频）

> 来源：MiniMax 官方仓库 `MiniMax-AI/MiniMax-H3`，`skills/h3-prompt-writing/references/ref-en.txt` 与 `base-en.txt`。
> 2026-11-24 起，分段成稿格式以用户提供的 `references/分镜视频模板.md` 为准（R56）；本文件把官方 Ref2VA 规则落成《阿良的分镜制作规则》的分镜视频层规范，与模板冲突时以模板为准。
> 官方原文链接：
> - https://github.com/MiniMax-AI/MiniMax-H3
> - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/ref-en.txt
> - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/base-en.txt

---

## 一、十条硬口径

1. **六段，顺序固定，一段不能少**：`subject_definitions` → `summary` → `retention_analysis` → `detailed_description` → `overall_soundscape` → `non_diegetic_music`。
2. **六段之前不许再加中文约束段**。老版段首那条「约束，台词只念一遍……」不再贴进提示词；相应限定改写成英文，落进 `detailed_description`。
3. **字段名照模板写**：每段用 `subject_definitions:` 这种字段行，各缩进两个空格；不用 Markdown `###`，不加编号，不加多余小标题。
4. **叙述骨架英文**。六段叙述句用英文；人物名、场景名、道具名、台词、屏显文字、`[Chinese]` 标签保留中文。正文不出现中文整句。
5. **时长 4–15 整数秒，和元数据「时长」一致**。`detailed_description` 里所有 `[Shot N]` 的切点必须落在该段时长之内。
6. **首镜不写时间码**。`[Shot 1]` 后面直接写内容；从 `[Shot 2]` 起写 `At MM:SS.mmm`，时间后不写逗号，切点严格递增（毫秒三位，如 `00:03.000`）。
7. **不套固定字数**。按 `分镜视频模板.md` 的密度写，通常 150–350 英文词；台词密集段优先把发声时间排满。
8. **参考标签先定义后使用，六段之间编号不变**。`<Subject N>`、`<Picture N>`、`<Video N>`、`<Audio N>` 只定义本段真正用到的。
9. **说话人按台词行顺序编号**。本段第一句台词是 `(S1)`，第二句 `(S2)`，依此类推；同一角色连续多句也各占一号（照 `分镜视频模板.md`）；不发声的人不给 ID；两人同时说写 `(S1,S2)`。
10. **默认零配乐**：`non_diegetic_music: N/A`。只有用户当次点名配乐才写配器、速度、节奏、动态，不写「悲伤」「燃」这类抽象情绪词。

---

## 二、六段各写什么

| 段 | 官方要求 | 本项目落法（R56） |
|---|---|---|
| `subject_definitions` | 每条参考内容独占一行，写清标签指什么、参考角色、要跟住的主要特征；图片来源只在定义主体时引用，不单独开 `<Picture>` 行 | `<Subject N>（图片名：中文名）: The reference supplies <职责> only; <姿态／机位从句> follow the shot description. main orientation: <本段主朝向>.` 人物／群体／场景／道具各用固定职责句 |
| `summary` | 一句话英文梗概，开头必须是方括号任务类型 | `[reference generation] N shots ...` 一句；多关系用 ` + ` 连接，不重复类型 |
| `retention_analysis` | 每个标签一行，写保留关系与保留内容 | 每个 Subject 一行：`<Subject N>（图片名：中文名）: fully_preserved；head angle and eyeline are reblocked per shot; reference frontal orientation is not preserved.`；群演／远景可 `weak_reference` |
| `detailed_description` | 按播放顺序写画面、主体、环境光、动作与状态变化、机位、声音、参考内容生效点；首镜无时间码，后续镜写切点 | 固定开头 `The scene is ... An outside witness ... No subject looks into the lens ...`；第二句 `Only the character who is speaking moves their lips; the rest keep lips closed.`；再写 `[Shot N]` 块；台词块放全部镜头之后 |
| `overall_soundscape` | 1–4 句英文，写环境声、动作声、非语言人声；不重复台词与画内音乐 | 一句英文底声、脚步、衣物摩擦、呼吸、风声等；独白的气声与鼻息也在这里补 |
| `non_diegetic_music` | 1–3 句英文，只写观众能听到的配乐；没有就 `N/A` | 默认 `N/A`；用户点名才写 |

---

## 三、任务类型（summary 开头方括号）

| 任务类型 | 什么时候用 |
|---|---|
| `keyframe completion` | 有图当首帧、关键帧、尾帧、改过的关键帧或具体帧锚点 |
| `reference generation` | 图／视频／音频只提供人物、场景、风格、动作、运镜、故事板等生成参考，不当具体帧，也不是被剪辑或续接的源视频 |
| `video editing` | 直接修改一条已有源视频 |
| `video continuation` | 从一条已有源视频的末尾继续、延伸、恢复或转场接下去 |
| `audio reuse` | 原音频信号整段或局部直接复用 |
| `audio reference` | 不直接复制音频，只参考音色、音乐风格、台词内容、音效质感、节拍或连续性 |

- 只是「上一段剧情承接」但并没有把上一段视频当输入，**不算 `video continuation`**，应按实际资产写 `reference generation` 或 `keyframe completion`。
- 真的把上一段视频挂进来续接，才在 `subject_definitions` 定义 `<Video N>`，summary 写 `video continuation`。
- 同时有首帧图和人物参考，写 `[keyframe completion + reference generation]`，不重复类型。

---

## 四、四类参考标签

| 标签 | 指什么 | 本项目怎么来 |
|---|---|---|
| `<Subject N>` | 可复用的可见内容：人、动物、物件、场景、服装、道具、界面、特效、风格、动作、表情、姿态 | 资产表人物／场景／道具 → `<Subject N>`；同一人物跨段复用同一编号 |
| `<Picture N>` | 真正当首帧、关键帧、尾帧、改过的关键帧、构图锚点或故事板参考的图片 | 只有满足这几种用途才单开 `<Picture N>`；只用来定义人物长相、服装、场景材质的图，写进对应 `<Subject N>` 定义里，不单开 |
| `<Video N>` | 剪辑源、续接起点、整条视频的时间结构／运镜／节奏参考 | 只有真的挂了视频才写；`<Video N>` 与 `<Audio N>` 各自独立编号，不按同一文件强行配对 |
| `<Audio N>` | 独立音频，或参考视频里启用的同步音轨：音色、台词、歌词、音效、节拍、连续性 | 有音频参考才写；定义到具体说话人时写成 `<Audio 1> is the voice-timbre reference for 方源(S1).` |

### 4.1 人物图不能一律当 `<Picture>`

官方明确：图片只用来定义人物、场景、服装、风格时，**不创建独立 `<Picture N>` 条目**，而是写进 `<Subject N>` 定义：

```text
<Subject 1>（图片名：周野）: The reference supplies facial identity, hair and costume only; pose, head angle and eyeline follow the shot description. main orientation: standing left, facing frame right.
```

只有这张图真的当首帧／尾帧／构图锚点时才单开：

```text
<Picture 3> is the first frame of [Shot 1], showing Zhou Ye seated on the bed beside the door.
```

同一张图可以既在 `<Subject 1>` 里当长相来源，又当首帧 `<Picture 3>`；两种角色要分别说清，编号各按各自类别排。

### 4.2 标签编号与「标签映射」

- `<Subject N>`、`<Picture N>`、`<Video N>`、`<Audio N>` 四类各自从 1 开始，互不占号。
- 同一集内编号一经分配就固定，跨段沿用，不重排、不回收。
- 每段元数据写一行「标签映射」，只写 `Subject N 名字 / Subject N 名字`，不写 `@Cxx／@Sxx／@Pxx`，例：`Subject 1 方源 / Subject 2 荒山巅石台 / Subject 3 春秋蝉`。
- 每条 `<Subject N>` 定义写成 `<Subject N>（图片名：中文名）: ...`；名字取自资产表，不许用「图1」「素材A」。
- `summary`、`detailed_description` 里引用人、场景、道具、首帧、尾帧、构图锚点，**一律写图片中文名**，不再出现裸 `<Subject N>`／`<Picture N>`；`retention_analysis` 行首写 `<Subject N>（图片名：中文名）`，这是唯一例外。
- 同一段同一主体只用一个名字，跨镜不换称呼；两个角色同名时用资产编号区分，例 `方源（C01）`、`方源（C02）`。
- 主体名与图片名分开：人物主体名 `方源`；人物图片名 `方源全身图`／`方源面部图`。场景主体名 `荒山巅石台`；场景图片名 `荒山巅石台全景图`。叙事用主体名，只有明确要挂某张帧／构图图时才写图片名。

---

## 五、保留度写法

每个 Subject 一行，固定句式：

```text
<Subject 1>（图片名：李云）: fully_preserved；head angle and eyeline are reblocked per shot; reference frontal orientation is not preserved.
```

```text
<Subject 3>（图片名：帐中众将）: weak_reference；head angle and eyeline are reblocked per shot; reference frontal orientation is not preserved.
```

| 标记 | 含义 |
|---|---|
| `fully_preserved` | 该参考内容被定义的职责全部保留 |
| `partially_preserved` | 仍在使用，但部分定义特征被改动，或只保留一部分（本技能默认不写，除非用户明确要） |
| `attribute_transfer` | 把参考特征迁移到另一个明确目标主体上（本技能默认不写） |
| `weak_reference` | 只保留风格、类别、构图、氛围上的大致相似 |

音频参考：

```text
<Audio 1>: reference - its vocal timbre guides 方源(S1) without copying the original signal.
```

| 标记 | 含义 |
|---|---|
| `fully_copy` | 整条源音频作为目标视频完整最终音轨 |
| `partially_copy` | 只复制部分时间线或部分音层，或复制后增删替换了其他声音 |
| `reference` | 不直接复制，只参考音色、节奏、音乐风格、台词内容或声音质感 |
| `weak_reference` | 只保留类别或氛围上的大致相似 |

---

## 六、`detailed_description` 的固定写法

1. **不写画风句**。模板不在每段重复画风锁；画风由 `REF-xxx` 与参考图承担。
2. **第一句固定**：`The scene is <场景>. An outside witness records <一句英文场景与事件>. No subject looks into the lens, and no subject adopts the frontal gaze of the reference sheets; everyone is held in profile or three-quarter view, pupils directed off frame at the opponent.`
   - `records` 可换 `observes`／`watches`；后半句逐字固定。
3. **第二句固定**：`Only the character who is speaking moves their lips; the rest keep lips closed.`
4. **首镜**：`[Shot 1] <景别>, <机位>: ...`，**不写时间码**。
5. **后续镜**：`[Shot 2] At 00:03.000 <景别>: ...`，时间后不写逗号，切点严格递增，且小于本段总时长。
6. **普通切镜**直接进新 `[Shot N]`，不强制 `the camera cuts to`；要写时可用 `cuts to / transitions to / changes to / switches to`。叠化、淡变、擦除只在用户明确要求时用。
7. **每个镜头都要写全**：当前构图、主体外观与位置、环境与光、动作与状态变化、机位、当前声音、参考内容真正出现或生效的点。
8. **不许写成剧情梗概或参考关系清单**；`detailed_description` 是唯一主成稿，要比分镜更具体，不许更空。
9. **字数**：通常 150–350 英文词；台词密集段按发声时间排满；不为了凑字数灌水。

---

## 七、机位、台词、画内文字

### 7.1 机位

镜头行冒号前写清景别与机位，用自然句即可：

```text
[Shot 1] Medium close-up, fixed camera: ...
[Shot 3] Medium shot, handheld sway, low angle: ...
[Shot 2] At 00:03.000 Medium shot tracking laterally in parallel with the path: ...
```

不强制 `with small amplitude at slow speed` 三要素模板；但必须读得出：这一镜怎么拍、景别、机位在哪、固定还是运动。

### 7.2 说话人与台词

- 说话人按台词行顺序编号：`(S1)`、`(S2)`、`(S3)`；同一角色连续多句也逐句各占一号（照样本）；不发声的人不给 ID；多人同时说用 `(S1,S2)`。
- 台词行固定：`(Sx) 角色：[Chinese] 原文`；同一角色连续多句逐句换行，不合并。
- **不用 `<d>`，不写 `says`，不写 `方源(S1) says ...`**。
- 画外音（含内心独白）固定：`(Sx) 角色（VO 不张嘴）：[Chinese] 原文`；`detailed_description` 的闭唇句保证画面上不张嘴。
- 台词原文逐字、标点保留，不翻译、不改写；听不清写 `[unclear]`。
- 台词标点标准化为 `, . ? !`，去掉重复波浪号、emoji、装饰符号。
- 只参考音色、节奏、情绪、表演，不把参考音频里的原台词搬进目标视频。

### 7.3 画面可见文字

门牌、招牌、字幕贴纸、霓虹字这类真实出现在画面里的文字，用英文双引号原样写出，保留原文字与标点，不翻译：

```text
A red neon sign reading "营业中" glows above the doorway.
```

---

## 八、本技能旧约束怎么落进模板

| 旧约束 | 模板里的落法 |
|---|---|
| 人物不看镜头，只有镜头找人 | `detailed_description` 第一句：`An outside witness records ... No subject looks into the lens, and no subject adopts the frontal gaze of the reference sheets; everyone is held in profile or three-quarter view, pupils directed off frame at the opponent.` |
| 同一时刻只有说话的人嘴唇动 | 第二句：`Only the character who is speaking moves their lips; the rest keep lips closed.` |
| 台词只念一遍、不复述 | 台词只出现一次，每句一行 `(Sx) 角色：[Chinese] 原文`；不复述、不回环、不叠句 |
| 内心独白不张嘴 | `(Sx) 角色（VO 不张嘴）：[Chinese] 原文`；画面上唇不动，气声走鼻腔与齿缝 |
| 无配乐 | `non_diegetic_music: N/A`；`overall_soundscape` 不写配乐 |
| 原文有光影才写 | 在对应镜头写光源、方向、强度／色温、落点、变化阶段；原文没写就不补 |
| 幻想特效写起中收 | 在特效出现镜头写形态、光源、起始、发展、收束，跨镜保持同一形态与亮度 |
| 第三视角、不拍人物主观 | 用 `outside witness` 句；POV 只有剧本明确要求才写 |
| 参考图只继承身份、不继承正脸与视线 | `subject_definitions` 每条写参考供给句与 `main orientation`；`retention_analysis` 每条写 `per shot` 朝向重排；机位优先侧向，禁正面平视（R54） |
| 投喂参考图必须单脸、够像素、干净 | 同一主体≤3 张；短边≥1024、纯色背景、均匀柔光、中性表情、一张图一张脸、脸身分开；资产设定表可多格，投喂图不整张表情板（R55.7） |
| 生图提示词不写负面词与装饰词 | 资产提示词不写「不要模糊／不要畸形／不要多余手指／8K／超清／大师之作／质感拉满」；H3 分段英文否定约束句保留（R55.8） |

---

## 九、交付前逐段核对

1. 六段齐全、顺序对、字段名对、各缩进两个空格，六段前没有中文约束段。
2. `summary` 方括号任务类型与实际资产角色一致；没有视频输入就不写 `video continuation`、不写 `<Video N>`；句式是 `[reference generation] N shots ...` 一句。
3. `<Subject N>` 每人／每场景／每道具独立且跨段同号；人物图没有被误当成独立 `<Picture N>`；每条定义带 `（图片名：中文名）`。
4. `retention_analysis` 每个标签一行，句式固定 `...: fully_preserved；head angle and eyeline are reblocked per shot; reference frontal orientation is not preserved.`；标记只用 `fully_preserved`／`weak_reference`。
5. `detailed_description`：第一句 `The scene is ...`＋outside witness＋双禁令＋侧脸／三分之二侧＋`pupils` 离轴；第二句闭唇句；首镜无时间码；后续镜 `At MM:SS.mmm` 严格递增且小于段长；每镜有构图、主体、环境光、动作、机位、声音、参考生效点。
6. 台词块在全部镜头之后；每句 `(Sx) 角色：[Chinese] 原文`；不用 `<d>`、不写 `says`；画外音写 `（VO 不张嘴）`。
7. `overall_soundscape` 一句英文，不重复台词与画内音乐。
8. `non_diegetic_music` 为 `N/A` 或用户指定配乐；没有主动加 BGM。
9. 正文里没有中文整句（人物名、场景名、道具名、台词、屏显文字除外）；正文没有裸 `<Subject N>`／`<Picture N>`，但 `retention_analysis` 行首写 `<Subject N>（图片名：…）`。
10. 字数落在 150–350 英文词左右；台词密集段以排满发声时间为准。
11. 时间码、镜头数、切点数与分镜逐镜对得上；段总时长与元数据一致。
12. `check_rule.py` 的 Ref2VA 机械项全 PASS，再走人工核对。
13. **R54 视线与朝向**：每个主体定义句有参考供给句与 `main orientation`；`retention_analysis` 带 `per shot` 朝向重排声明；`detailed_description` 双禁令齐全；每个角色有具体注视对象，近景/中近景有 `pupils` 离轴方向；正面或近正面机位不超过三分之一；同一主体参考图不超过三张且上传顺序与编号一致。
14. **R55 方法论吸收**：复杂接触／交互动作有指定关键帧；动作句是「施力→受力→结果」因果链；没有用具体 IP 角色／演员／品牌名作概念；动态道具写了人物侧＋机位侧；投喂图单脸、短边≥1024、纯色背景、中性表情、脸身分开且≤3 张；生图提示词没有负面词、8K、大师之作；器材只写效果。
15. **R56 模板对号**：逐项对照 `references/分镜视频模板.md`——元数据 `*` 行、`时长` 带「秒」、`标签映射` 只写 `Subject N 名字`、`说话人` 是 `① (S1) 名字`、台词块后置、`non_diegetic_music` 是 `N/A`。

