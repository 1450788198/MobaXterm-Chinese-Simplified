# 逆向汉化方法论总结（SKILLS）

> 从 MobaXterm v26.5（Delphi/C++Builder 混合体，16.6 MB，5 万+ 可见字符串）
> 做出「全界面中文 + 图标工具栏中文 + 无裁剪渲染」的可复现实战总结。
> 适用于任何 Delphi/VCL 系 Windows 桌面程序的界面汉化。

---

## 0. 一句话方法论

> **先建立「文本从哪来」的完整地图，再动一个字节。**
> 任何一次「改了没反应」都说明地图错了，此时不要换着法儿改，要做**排除实验**。

界面文本在 VCL 程序里只有三条来源，汉化就是三条通道全打通：

| 通道 | 载体 | 生效方式 | 本文对应 |
|---|---|---|---|
| ① 资源流 | DFM（RT_RCDATA）/ RT_STRING | 程序启动反序列化 | §3 §4 §5 |
| ② 代码常量 | Delphi `AnsiString` 常量（`ff ff ff ff + len + text`） | 运行时被引用 | §6 |
| ③ 运行时覆写 | 程序自己把某属性当显示文本重算 | 覆盖 ① 的结果 | §7（最容易踩） |

---

## 1. 解包链路：安装包不一定能直接开

```
MobaXterm_Installer_v26.5.zip
├── MobaXterm_installer.dat   （PKZIP，Cygwin 插件）
└── MobaXterm_installer_26.5.msi
      └── 内嵌 CAB
            ├── MobaXterm.exe
            └── Moba_*_ttf ×3
```

**坑**：MSI 是 CFB(OLE2) 容器，内嵌 CAB 的扇区链**不连续**（本例 `[4,3,5,6,7,8,9,…]`，3/4 互换）。
用 `olefile` 顺序读出来的 CAB 是坏的。必须自己走 FAT 扇区链，
拿到的 CAB 里 `CFDATA` 从文件偏移 **173 (0xAD)** 开始。

**判定技巧**：CAB 头 magic `MSCF` 出现在错误位置 = 扇区链走错，不是文件损坏。

---

## 2. 结构认知：先把「地图」画出来

### 2.1 PE 节表（本例）

| 节 | VA | VS | Raw | 用途 |
|---|---|---|---|---|
| CODE | 0x1000 | 0x752AB0 | 0x400 | 代码 **+ Delphi 字符串常量** |
| DATA | 0x754000 | 0x92BD0 | 0x753000 | 全局数据 |
| BSS | 0x7E7000 | 0x2A02D | — | 未初始化 |
| .idata / .tls / .rdata / .reloc | … | | | |
| .rsrc | 0x880000 | 0x7E7BAA | 0x7EA600 | 原资源树 |
| .mzcn | 0x1068000 | 0x200 | 0xFD2200 | **自建代码洞** |
| .rscn | 0x1069000 | 0x7E11D0 | 0xFD2400 | **自建新资源树** |

**关键点**：Delphi 把字符串常量放在 **CODE 段尾部**（本例 0x905xxx–0x90Axxx），
不是 `.rdata`。只扫 `.rdata` 会得出「这程序没有字符串」的错误结论。

**地址换算**：`raw = va - 0x401000 + 0x400`（仅对 CODE 成立），
其他节必须从节表逐节算。

### 2.2 资源树与 DFM

- `DataDirectory[2]` → 资源根（可指向自建节，无需重写原 `.rsrc`）
- 三级目录：`type → name → lang → data entry(RVA,Size)`
- 名字项带高位 `0x80000000`，偏移相对**目录根**，内容是 `[u16 len][UTF-16LE]`
- 类型 10 = RT_RCDATA = Delphi 窗体（`TPF0` 开头，73 个）
- 类型 6 = RT_STRING = 79 块、1200 条 UTF-16 界面文案（易被整块忽略）

**DFM 二进制格式**（`TPF0` + 对象树）值类型编号：

```
0 Null  1 List  2 Int8  3 Int16  4 Int32  5 Extended  6 String  7 Ident
8 False 9 True  10 Binary 11 Set 12 LString 13 Nil 14 Collection
15 Single 16 Currency 17 Date 18 WString 19 Int64 20 UTF8String
```

**坑（花了最久）**：`vaWString(18)` 的长度前缀是 **int32 字符数**，不是 u8 字节数。
按 u8 读会在某些窗体上「值类型 111/76 未知」崩掉，而且读到的对象树是错的
（因为它没崩，只是静默错位）。跨版本拿参考包解析时必踩。

---

## 3. 翻译注入：不要手写词库

### 3.1 结构对齐挖词（`xalign.py`）

从一份**已有的高质量汉化包**（参考实现）挖 EN→ZH 对照，而不是自己硬翻：

```python
def walk_obj(obj, prefix, vals):
    for pname, (pt, pv) in obj['props'].items():
        if pt in (VA_STRING, VA_LSTRING, VA_WSTRING, VA_UTF8STRING):
            if isinstance(pv, str):
                vals[prefix + (pname,)] = pv          # 路径键：form/对象名[序号]/属性
    for idx, ch in enumerate(obj['children']):
        walk_obj(ch, prefix + (ch['name'], idx), vals)
```

- **键 = 结构路径**（窗体名 / 对象名+序号 / 属性名），不是字符串本身。
  这样同名不同义的词（"Session" 按钮 vs "Session" 菜单项）不会串味。
- 对象名不一致时降级为 `(form, property)` 匹配。
- 只保留中文侧含 CJK 的配对 —— 自动过滤掉参考版没翻的部分。

本例：64 个窗体、2690 个属性 → **1286 条可信对照**，覆盖率 430 → 1421/1572。

### 3.2 词库优先级

```
ref_map.json（结构对齐挖出，最可信）
  > trans_map.json（长尾整句）
  > trans_zh.EXACT（人工补充）
  > brand()/phrase() 兜底替换
```

### 3.3 绝不翻译的清单（**血泪**）

| 类别 | 例子 | 后果 |
|---|---|---|
| INI 节名/键名 | `Toolbar`、`Session`、`TopToolbarBtns` | 配置读不到 → 界面回退英文/默认值 |
| 按钮 ID 表 | `Games,Settings,Session,Tools,Macro,Servers` | ID 匹配失败 → 按钮丢失或英文 |
| 文件名/进程名片段 | `MobaX`（`XWin_MobaX.exe` 的组成） | **启动报错：找不到文件** |
| 协议/命令 | `ssh`、`xterm-256color`、`chmod` | 功能失效 |
| URL/正则/格式串 | 含 `%`、`://`、`\\` 的串 | 崩溃或功能异常 |
| 组件名/属性名 | `BtnTunneling`、`Hint` | 引用断裂 |

**实现**：按**地址区间**保护，不要按字符串值保护——
同一个字符串在不翻的位置出现时，值保护会误伤：

```python
PROTECT = [(0x5042dc, 0x504350),   # TopToolbarBtns 默认值表
           (0x5b5e4c, 0x5b5e78)]   # Toolbar / Session 键名
if any(a <= off < b for a, b in PROTECT):
    continue
```

---

## 4. 字体：**什么都不要改**（反直觉但正确）

**症状**：汉化后大量控件「文本显示不全 / 被切成一半」。

**错误做法**：把 `Font.Name` 从 Arial 换成微软雅黑 + `GB2312_CHARSET`。
雅黑的字形度量比 Arial 大，`TSpeedButton`/`TLabel` 的 `Width/Height`
是按拉丁文算死的，中文直接被裁。

**正确做法**：原样保留 `Arial / Tahoma / Verdana + DEFAULT_CHARSET`。
中文 Windows 的 **GDI 字体链接（font-linking）** 会在缺字时自动回退到宋体，
度量与原字体一致，尺寸体系不崩。

**验证方法**：解析参考汉化包，统计 `Font.Name` / `Font.Charset` 分布——
本例参考版与原版**完全一致**（Arial 374、Tahoma 36、Verdana 23；DEFAULT 398 / ANSI 42），
一个都没改。这就是最硬的证据：**参考实现的做法 = 正确答案**。

---

## 5. RT_STRING：整块继承，别逐条翻

79 个块、1200 条 UTF-16 文本，逐条翻译是体力活且术语不一致。

**发现**：参考版与原版的块 ID + 序号**一一对应**
（`{blockID}#{index}` 键完全对齐），差异块 861 条。
→ 直接按 `(blockID, index)` 建映射整块继承，一次补齐 72%。

```python
# 块结构：[u16 len][len×UTF-16LE] ...  len==0 表示该序号为空
def split_block(d):
    i = idx = 0; out = {}
    while i + 2 <= len(d):
        ln = struct.unpack_from('<H', d, i)[0]; i += 2
        if ln == 0: idx += 1; continue
        out[idx] = d[i:i+ln*2].decode('utf-16-le'); i += ln*2; idx += 1
    return out
```

**注意**：改写后块长度变化必须重写资源目录里的 Size，
否则程序读到旧长度 → 截断。

---

## 6. 代码级字符串：Delphi 常量匹配的四个约束

常量格式：`dd -1（引用计数） / dd len / <chars> / 00`

匹配时四个约束缺一不可（本例 155 处 → 145 处，0 处超长）：

```python
if bytes(B[i-8:i-4]) != b'\xff\xff\xff\xff':   continue   # ① 头部校验
if stored > len(raw_s) + 8:                    continue   # ② 长度字段容错
end = i + len(raw_s)                                         # ③ 容忍尾随空格
while end < len(B) and end - (i+len(raw_s)) < 4 and B[end] == 0x20: end += 1
if B[end] != 0:                                continue
budget = zend + 1 - i                                        # ④ 可吃零填充
if len(gbk) + 1 > budget:                      continue   # 装不下就跳过，别硬塞
```

**编码**：宿主 ANSI 代码页 = 936 → 一律 **GBK** 写入，不要 UTF-8。

**必须重算 PE 校验和**，否则某些配置下镜像加载直接失败（表现为双击无反应）：

```python
# 累加除 CheckSum 字段外的所有 16 位字，折叠 + 加文件长度
```

---

## 7. 运行时覆写：那个「改了完全没反应」的 bug

**症状**：主工具栏 13 个按钮（Session / Servers / …）始终英文，
但 DFM 里的 `Caption` **确认是中文**（磁盘 + 进程内存双重验证）。

**排除实验清单**（每项都真跑过，全部无效）：

| 假设 | 实验 | 结果 |
|---|---|---|
| 读了旧 `.rsrc` 副本 | 把 `.rsrc` 整节清零重启 | 无变化 |
| 配置缓存 | 全新目录、清 `%TEMP%\Mxt265`、清注册表 | 无变化 |
| 加密资源 BASEPROF | 清零重启 | 无变化 |
| 常量表 / ID 表 / RT_STRING / SKINS | 静态比对 | 均已是中文 |
| 从组件名派生（`Btn` 前缀） | — | 名字与显示对不上（`X server`） |
| 内存里还有英文副本 | 全内存扫描 EN/UTF-16/ShortString | 只有映射副本 |

**决定性对照实验**：把 DFM `Caption` 改成同长度占位符 `ABCD` / `ABCDEFGH`，
**长度不变 → 不需要改资源尺寸，纯就地替换**：

```
'\x07Caption\x06\x04\xcb\xed\xb5\xc0\x04Flat'  →  '\x07Caption\x06\x04ABCD\x04Flat'
```

重启后按钮仍显示 `Tunneling` —— 证明 **Caption 根本没被使用**。

**破案点**：把「DFM 里所有字符串属性」按对象列出来看，`sPanel4` 下每个按钮的
`HelpKeyword` 恰好等于界面显示文字，顺序逐字吻合：

| 对象 | Caption（DFM） | HelpKeyword（实际显示） |
|---|---|---|
| BtnNewSession | 会话 | `Session` |
| BtnServices | 服务器 | `Servers` |
| BtnMenuComdes | 工具 | `Tools` |
| BtnBookmarks | 会话 | `Sessions` |
| BtnSplitMode | 分屏 | `Split` |
| BtnMultiExec | 多重执行 | `MultiExec` |
| BtnTunneling | 隧道 | `Tunneling` |
| sBitBtn7 | X 服务器 | `X server` |
| BtnClose | 退出 | `Exit` |

→ v26.5 用 `Caption := HelpKeyword` 渲染工具栏（HelpKeyword 同时是帮助主题 ID）。

**修法**：把已翻译好的中文 `Caption` 回写进 `HelpKeyword`：

```python
TOPBAR_HELPKEYS = {'Session','Servers','Tools','Sessions','View','Split',
                   'MultiExec','Tunneling','Packages','Settings','Help',
                   'X server','Exit'}
hk = props.get('HelpKeyword')
if hk and hk[1] in TOPBAR_HELPKEYS and 'Caption' in props:
    props['HelpKeyword'] = (dfm.VA_STRING, props['Caption'][1])
```

**教训**：`HelpKeyword` 这种「看起来是功能字段」的属性，可能正是显示源。
判定标准不是字段名，而是**值是否与界面逐字吻合**。

---

## 8. GUI 实测：自己骗自己最容易

- VCL 窗体常是 **owner-draw**：`EnumChildWindows` 返回 0，拿不到子控件，
  必须用 `PrintWindow` 截图（`BitBlt` 会截到空白/被遮挡）。
- 程序常有**单实例/缓存**行为：每次实测前 `kill` 全部旧进程，
  并用**本轮启动的 PID** 抓窗口，别按窗口标题匹配（会抓到旧实例）。
- 中文控制台输出编码：`tasklist` 是 GBK，`subprocess(text=True)` 会崩 →
  用 `CreateToolhelp32Snapshot + Process32FirstW` 自己枚举进程。
- 沙箱可能拦截 `reg.exe` → 用 Python `winreg`。

---

## 9. 内存取证的最小可用套路

静态找不到就去运行时拿证据：

```python
h = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
# 按 VirtualQueryEx 遍历可读区，逐区 ReadProcessMemory 后 find(needle)
# 命中后用 PE 节表把地址归类：image 哪一节 / heap
```

三种编码都要试：`AnsiString(ff ff ff ff+len)`、长 UTF-16、`ShortString(len byte)`。
本例正是靠「heap 记录里出现 `Sessions` / `Tunneling`」把方向从「DFM」拨到「运行时构建」。

---

## 10. 新版本上手 Checklist（30 分钟出结论）

1. 解包到 exe，记录大小/时间戳/编译特征（Delphi 版本）
2. 解析节表 + 资源树，导出三类清单：
   - 类型 10 的 `TPF0` 窗体（数量、大小）
   - 类型 6 的 RT_STRING 块
   - CODE/DATA 中的 `ff ff ff ff` 常量（**重点看 CODE**）
3. 找一份**同源不同版**的汉化包，跑结构对齐挖词（§3.1）
4. 自建 `.rscn` 节 + 重写 `DataDirectory[2]`，不改原 `.rsrc`（可回滚）
5. 注入顺序固定：**品牌/署名 → DFM/RT_STRING → 代码常量 → 重算校验和**
6. 每次实测：`kill` 旧进程 → 新目录 → `PrintWindow` → 比对截图
7. 遇到「改了没反应」，先做**清零/占位符对照实验**定位通道，再改代码

### 一次汉化的验收标准

- [ ] 所有窗体标题/菜单/按钮/提示/对话框正文为中文
- [ ] 工具栏、右键菜单、状态栏、气泡提示（容易漏的三处）
- [ ] 无文字裁剪（字体未改 / 控件未被压缩）
- [ ] 功能不回归：新建会话、打开本地终端、设置对话框可开、无启动报错
- [ ] 文件名、URL、协议名、配置键保持原样
- [ ] 程序可正常退出并再次启动（配置读写未被打断）

---

## 11. 工具清单（本仓库 `scripts/`）

| 文件 | 作用 |
|---|---|
| `dfm.py` | Delphi 二进制 DFM 读写（含 WString/UString 全类型），往返字节级一致 |
| `xalign.py` | 跨版本按结构路径对齐，挖 EN→ZH 对照 |
| `rtres.py` | RT_STRING 块级继承与重写 |
| `localize.py` | 资源汉化主流程（DFM + RT_STRING + 工具栏 HelpKeyword） |
| `patch_code.py` | 代码级 Delphi 常量替换 + 保护区间 + PE 校验和 |
| `trans_zh.py` / `trans_map.json` / `ref_map.json` | 三级词库 |
| `memscan*.py` | 运行时内存取证（找英文残留 / 定位数据源） |

---

## 12. 三条最贵的经验

1. **参考实现的做法就是标准答案。** 字体换不换、词怎么翻、哪些字段动不得——
   解析一遍参考包就有答案，比我猜十次都快。
2. **「改了没反应」= 通道判断错，不是改法不够多。** 用清零/占位符做对照实验，
   一次就能砍掉整条通道。
3. **字符串的可信度排序：值吻合 > 字段名。** 显示文本可能来自任何字段
   （`HelpKeyword`、组件名、配置项），只有「值逐字对得上」才是证据。
