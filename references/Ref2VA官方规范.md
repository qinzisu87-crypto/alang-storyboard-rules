# 官方 Ref2VA 分段视频提示词规范（H3 参考生视频）

> 来源：MiniMax 官方仓库 `MiniMax-AI/MiniMax-H3`，`skills/h3-prompt-writing/references/ref-en.txt` 与 `base-en.txt`。
> 本文件把官方 Ref2VA（full-reference）规则落成《阿良的分镜制作规则》的分段层硬规范。分段提示词以本文件为准；分镜层仍是中文连续动作提示词，不受本文件影响。
> 官方原文链接：
> - https://github.com/MiniMax-AI/MiniMax-H3
> - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/ref-en.txt
> - https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/main/skills/h3-prompt-writing/references/base-en.txt

---

## 一、十条硬口径

1. **六段，顺序固定，一段不能少**：`subject_definitions` → `summary` → `retention_analysis` → `detailed_description` → `overall_soundscape` → `non_diegetic_music`。
2. **六段之前不许再加中文约束段**。老版段首那条「约束，台词只念一遍……」不再贴进提示词；把它翻成英文写进 `detailed_description` 的开头（见第八节）。
3. **字段名照官方写**：每段用 `subject_definitions:` 这样的字段行，不用 Markdown `###`，不加编号，不加多余小标题。
4. **正文英文**。六段的叙述句一律英文；只有 `<d>` 内的台词、歌词、画面里真实可见的文字，以及 R20.3 的图片中文名保留原语言。
5. **时长 4–15 整数秒，和元数据「时长」一致**。`detailed_description` 里所有 `[Shot N]` 的切点必须落在该段时长之内。
6. **首镜不写时间码**。`[Shot 1]` 后面直接写内容；从 `[Shot 2]` 起写 `At MM:SS.mmm,`，切点严格递增（毫秒三位，如 `00:03.500`）。
7. **`detailed_description` 通常 350–500 英文词**。台词密集段优先把发声时间排满，不机械凑字数；单镜不因为镜头少就写短。
8. **参考标签先定义后使用，六段之间编号不变**。`<Subject N>`、`<Picture N>`、`<Video N>`、`<Audio N>` 只定义本段真正用到的。
9. **说话人有稳定 `(Sx)`**。按本段实际发声顺序分配，跨镜复用；不发声的人不给 ID；两人同时说写 `(S1,S2)`。
10. **默认零配乐**：`non_diegetic_music: N/A`。只有用户当次点名配乐才写配器、速度、节奏、动态，不写「悲伤」「燃」这类抽象情绪词。

---

## 二、六段各写什么

| 段 | 官方要求 | 本项目落法 |
|---|---|---|
| `subject_definitions` | 每条参考内容独占一行，写清标签指什么、参考角色、要跟住的主要特征；图片来源只在定义主体时引用，不单独开 `<Picture>` 行 | 把 `@Cxx`／`@Sxx`／`@Pxx` 映射成 `<Subject N>`；人物三视图、场景图、道具图只作主体定义来源，不单独算 `<Picture>` |
| `summary` | 一句话英文梗概，开头必须是方括号任务类型 | 例：`[reference generation] ...`；多关系用 ` + ` 连接，不重复同一类型 |
| `retention_analysis` | 每个标签一行，写保留关系与保留内容 | 可见参考用 `fully_preserved`／`partially_preserved`／`attribute_transfer`／`weak_reference`；音频用 `fully_copy`／`partially_copy`／`reference`／`weak_reference` |
| `detailed_description` | 按播放顺序写画面、主体、环境光、动作与状态变化、机位、声音、参考内容生效点；首镜无时间码，后续镜写切点 | 分镜的九栏在这里落成英文成稿；动作写到关节、肌肉、承重，表情写到眉／眼／嘴／下颌／喉／呼吸，视线必须有落点 |
| `overall_soundscape` | 1–4 句英文，写环境声、动作声、非语言人声；不重复台词与画内音乐 | 底声、脚步、衣物摩擦、呼吸、敲门、风声等；独白的气声与鼻息也在这里补 |
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
| `<Subject N>` | 可复用的可见内容：人、动物、物件、场景、服装、道具、界面、特效、风格、动作、表情、姿态 | `@C01` 人物 → `<Subject N>`；`@S01` 场景 → `<Subject N>`；`@P01` 道具 → `<Subject N>`；同一人物跨段复用同一编号 |
| `<Picture N>` | 真正当首帧、关键帧、尾帧、改过的关键帧、构图锚点或故事板参考的图片 | `@图片 N` 只有满足这几种用途才单开 `<Picture N>`；只用来定义人物长相、服装、场景材质的图，写进对应 `<Subject N>` 定义里，不单开 |
| `<Video N>` | 剪辑源、续接起点、整条视频的时间结构／运镜／节奏参考 | 只有真的挂了视频才写；`<Video N>` 与 `<Audio N>` 各自独立编号，不按同一文件强行配对 |
| `<Audio N>` | 独立音频，或参考视频里启用的同步音轨：音色、台词、歌词、音效、节拍、连续性 | 有音频参考才写；定义到具体说话人时写成 `<Audio 1> is the voice-timbre reference for 方源(S1).` |

### 4.1 人物图不能一律当 `<Picture>`

官方明确：图片只用来定义人物、场景、服装、风格时，**不创建独立 `<Picture N>` 条目**，而是写进 `<Subject N>` 定义：

```text
<Subject 1>（图片名：周野） is Zhou Ye, the man whose face and build come from 周野全身图 and 周野面部图, with close-cropped dark hair, a broken left eyebrow, a grey hoodie under a worn jacket, and thin shoulders.
```

只有这张图真的当首帧／尾帧／构图锚点时才单开：

```text
<Picture 3> is the first frame of [Shot 1], showing Zhou Ye seated on the bed beside the door.
```

同一张图可以既在 `<Subject 1>` 里当长相来源，又当首帧 `<Picture 3>`；两种角色要分别说清，编号各按各自类别排。

### 4.2 标签编号规则

- `<Subject N>`、`<Picture N>`、`<Video N>`、`<Audio N>` 四类各自从 1 开始，互不占号。
- 同一集内编号一经分配就固定，跨段沿用，不重排、不回收。
- 每段元数据加一行「标签映射」，把本段用到的槽号与标签写清，例：`@C01→<Subject 1>（方源）；@S01→<Subject 2>（荒山巅石台）；@图片 9→荒山巅石台全景图`。
- **本项目落地：图片中文名**（2026-11-18 增补，优先于官方示例里的裸标签写法）
  - 每条 `<Subject N>` 定义必须写成 `<Subject N>（图片名：方源） is ...`；每条 `<Picture N>` 写成 `<Picture N>（图片名：荒山巅石台全景图） is ...`。名字取自资产表，不许用「图1」「素材A」。
  - `summary`、`retention_analysis`、`detailed_description` 里引用人、场景、道具、首帧、尾帧、构图锚点，**一律写图片中文名**，不再出现裸 `<Subject N>`／`<Picture N>`。标签只保留在定义行与「标签映射」。
  - 同一段同一主体只用一个名字，跨镜不换称呼；两个角色同名时用资产编号区分，例 `方源（C01）`、`方源（C02）`。
  - 说话人写成 `方源(S1)`，不写 `<Subject 1> (S1)`。
  - 主体名与图片名分开：人物主体名 `方源`，人物图片名 `方源全身图`／`方源面部图`；场景主体名 `荒山巅石台`，场景图片名 `荒山巅石台全景图`。叙事用主体名，只有明确要挂某张帧／构图图时才写图片名。
  - 例：`<Subject 1>（图片名：方源） is the man whose face comes from 方源面部图（@图片 2）...`，正文写 `方源 sits on the stone platform...`。
- `detailed_description` 里第一次出现某主体时，把它指代的外形、画面位置、当前动作写清；后文复用同一个中文名，不重新定义。

---

## 五、保留度写法

可见参考，一条一行：

```text
方源（appears in [Shot 1], [Shot 2]): fully_preserved - face, hairstyle, outfit and body build follow the reference.
```

```text
荒山巅石台（appears in [Shot 1]): partially_preserved - room layout and door-on-the-right are kept; the lamp brightness is changed by the story.
```

| 标记 | 含义 |
|---|---|
| `fully_preserved` | 该参考内容被定义的职责全部保留 |
| `partially_preserved` | 仍在使用，但部分定义特征被改动，或只保留一部分 |
| `attribute_transfer` | 把参考特征迁移到另一个明确目标主体上 |
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

## 六、`detailed_description` 的镜头与时间码

1. **风格句写在 `[Shot 1]` 之前**，一到两句英文，与 REF 画风锁一致：`Cinematic, live-action realism, low-saturation cold grey-blue tone, soft volume light; REF-001 style lock.`
2. **首镜**：`[Shot 1]` 后面直接写内容，**不写时间码**。
3. **后续镜**：`[Shot 2] At 00:03.500, the camera cuts to ...`，切点严格递增，且小于本段总时长。
4. **普通切镜词**用 `the camera cuts to`／`the shot cuts to`／`the shot transitions to`／`the shot changes to`／`the shot switches to`。叠化、淡变、擦除只在用户明确要求时用。
5. **只改距离或轻微角度**时优先写机位运动，不另起切镜。
6. **每个镜头都要写全**：当前构图、主体外观与位置、环境与光、动作与状态变化、机位运动、当前声音、参考内容真正出现或生效的点。
7. **不许写成剧情梗概或参考关系清单**；`detailed_description` 是唯一主成稿，要比分镜更具体，不许更空。
8. **字数**：通常 350–500 英文词；台词密集段按发声时间排满；剪辑类按源视频复杂度伸缩。

---

## 七、机位运动、台词、画内文字

### 7.1 机位运动

必须写全三件事：**运动类型 ＋ 幅度 ＋ 速度**，写成镜头内自然英文句：

```text
The camera pushes in with small amplitude at slow speed toward 方源的手。
The camera pans right with large amplitude at fast speed, revealing the open doorway.
The camera holds a static shot as the runner exits the frame.
```

运动类型官方词表：`Zoom In / Zoom Out`、`Push In / Pull Out`、`Pan Left / Pan Right`、`Truck Left / Truck Right`、`Tilt Up / Tilt Down`、`Pedestal Up / Pedestal Down`、`Arc Shot`、`Tracking Shot`、`Static Shot`、`Shake Slightly / Shake Strongly`、`POV`、`Roll Clockwise / Roll Counterclockwise`。幅度用 `with small amplitude`／`with large amplitude`；速度用 `at slow speed`／`at fast speed`。中等幅度、正常速度可省略。

### 7.2 说话人与台词

- 说话人用稳定 ID：`(S1)`、`(S2)`；同一人跨镜、跨段复用同一 ID；不发声的人不给 ID；多人同时说用 `(S1,S2)`。
- 主体说话写成 `方源(Sx)`；画外说话保留同一形式并写 `off-screen`。
- 台词只放 `<d>[Language] 原文</d>`，`[Language]` 写 `Chinese`／`English` 等，原文逐字、标点保留，不翻译、不改写。
- 听不清写 `[unclear]`，不许猜、不许改写。
- 台词标点标准化为 `, . ? !`，去掉重复波浪号、emoji、装饰符号。
- 画外音（含内心独白）用官方固定句 `says in an off-screen voiceover`，并在 `<d>` 后紧跟 `his/her lips remain completely closed`。
- 同一句台词跨切时，在切口两侧写 `<scenetrans>`，并写明声音跨切连续；被片尾截断写 `<cutoff>`。
- 只参考音色、节奏、情绪、表演，不把参考音频里的原台词搬进目标视频。

### 7.3 画面可见文字

门牌、招牌、字幕贴纸、霓虹字这类真实出现在画面里的文字，用英文双引号原样写出，保留原文字与标点，不翻译：

```text
A red neon sign reading "营业中" glows above the doorway.
```

全局「不生成字幕／caption／文字叠加」照旧，但不能覆盖画面里真实存在的文字。

---

## 八、本技能旧约束怎么翻进官方六段

| 旧约束 | 官方六段里的落法 |
|---|---|
| 人物不看镜头，只有镜头找人 | 在 `detailed_description` 风格句后写：`The camera observes as an outside witness. No character looks into the lens; every eyeline stays on an in-scene object, opponent, or off-screen story target, while the camera may photograph faces and eyes.` |
| 同一时刻只有说话的人嘴唇动 | 有对话的段写：`Only the character who is speaking moves their lips; every other character keeps their lips closed and makes no lip-sync movement.` |
| 台词只念一遍、不复述 | 台词只出现一次 `<d>`；不复述、不回环、不叠句 |
| 内心独白不张嘴 | 用 `says in an off-screen voiceover` ＋ `lips remain completely closed` ＋ 气声走鼻腔与齿缝 |
| 不生成字幕／caption／文字叠加 | `No subtitles, captions, or text overlays are generated; only text physically present in the scene is shown.` |
| 无配乐 | `non_diegetic_music: N/A`；`overall_soundscape` 不写配乐 |
| 原文有光影才写 | 在对应镜头写光源、方向、强度／色温、落点、变化阶段；原文没写就不补 |
| 幻想特效写起中收 | 在特效出现镜头写形态、光源、起始、发展、收束，跨镜保持同一形态与亮度 |
| 第三视角、不拍人物主观 | 用 `outside witness` 句；POV 只有剧本明确要求才写 |

---

## 九、交付前逐段核对

1. 六段齐全、顺序对、字段名对，六段前没有中文约束段。
2. `summary` 方括号任务类型与实际资产角色一致；没有视频输入就不写 `video continuation`、不写 `<Video N>`。
3. `<Subject N>` 每人／每场景／每道具独立且跨段同号；人物图没有被误当成独立 `<Picture N>`。
4. `retention_analysis` 每个标签一行，标记只能是官方枚举值。
5. `detailed_description`：首镜无时间码；后续镜 `At MM:SS.mmm` 严格递增且小于段长；每镜有构图、主体、环境光、动作、机位、声音、参考生效点。
6. 说话人 `(Sx)` 稳定；每句台词都在 `<d>[Language] 原文</d>` 内；画外音写了 `off-screen voiceover` 与闭唇。
7. `overall_soundscape` 1–4 句，不重复台词与画内音乐。
8. `non_diegetic_music` 为 `N/A` 或用户指定配乐；没有主动加 BGM。
9. 英文正文里没有残留中文（`<d>`、画面可见引文与 R20.3 图片中文名除外）；正文没有裸 `<Subject N>`／`<Picture N>`。
10. 字数落在 350–500 英文词左右；台词密集段以排满发声时间为准。
11. 时间码、镜头数、切点数与分镜逐镜对得上；段总时长与元数据一致。
12. `check_rule.py` 的 Ref2VA 机械项全 PASS，再走人工核对。
