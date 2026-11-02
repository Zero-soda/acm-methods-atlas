# ACM Methods Atlas

**把致心律失常性心肌病研究连接为问题推进的路径，并提供方法目录与可复现统计。**

核心逻辑是：**研究问题 → 采用的方法 → 研究内发现 → 留下的缺口 → 下一项可检验的临床研究**。方法统计用于支撑这条路径；逐篇标注保留原始来源与核对层级。

[先看研究路径图](https://zero-soda.github.io/acm-methods-atlas/research_paths.html) · [浏览方法目录](https://zero-soda.github.io/acm-methods-atlas/) · [统计快照](docs/README.md) · [标注协议](docs/annotation_protocol.md) · [English](README_EN.md)

## v0.2 研究路径

三条路径覆盖综述中的23篇正式研究，包含12条跨研究连接，其中4条明确标为待验证桥接：

| 研究路径 | 希望补上的临床连接 |
|---|---|
| 早期电与代谢异常 | 基线电状态是否对应后续损伤或结构进展，怎样检验干预窗口？ |
| 损伤、炎症与修复 | 如何区分持续活动与持久损害，怎样分别评价炎症、电负荷与泵功能反应？ |
| 局部病灶与风险 | 分子状态如何与同区域影像、电信号及后续事件对齐？ |

每一步给出代表研究、已有贡献与未解问题；每条连接解释为什么能联结、推断边界在哪里；每条路径提出下一步设计及可能削弱假说的结果，并说明公开数据现在能完成哪一步。

这些是**问题驱动的证据连接**，不是已经核查的作者引用传承，也不是所有患者共同经历的病程顺序。研究年份、真实随访、动物分批时间点、空间位置和计算拟时序不能相互替代。[完整文字版](docs/research_paths.md)与[结构化数据](data/research_paths.json)均可复用。

## 文献与方法收录范围

| 内容 | 数量与口径 |
|---|---|
| 原始研究目录 | 25篇记录：24篇正式发表、1篇预印本 |
| 默认统计队列 | 综述实际引用的23篇正式原始研究，含1项两例病例系列 |
| 全库方法概念 | 122项，分为设计、测量、计算/统计及受控扰动 |
| 全库研究—方法阳性标注 | 232条；每条附证据概括、来源定位及核对层级 |
| 默认队列的阳性标注 | 223条，涉及121项方法概念 |
| 单列背景来源 | 14项指南/共识、综述、试验注册和会议资料，不进入方法统计分母 |
| 临床问题 | 早期进展、损伤与修复、治疗应答、区域风险解释 |

证据整理截至2026-11-01，标注版本日期2026-11-02。原文/PDF、第三方图表、患者级资料及未发表综述稿件不包含在仓库中。

## 能做什么

- 查询一篇文章实际使用的方法，并回到DOI/原始来源及具体方法定位。
- 查看计算方法、组学、影像、电生理、时间设计和空间取材的研究篇数。
- 查看方法共现以及它们对应的临床问题；下载JSON和CSV进行二次使用。
- 在三种队列口径之间切换，单独观察预印本及补充研究对统计的影响。
- 补充文献和修订标注，再用同一段代码重新生成统计和静态目录。
- 沿研究路径查询一项发现如何引出下一问题，并追溯到该研究的方法与原文。

## 统计含义

**这里统计的是当前定向文献库中已确认的方法标注频次。** 本库不是穷尽性系统检索，不估计整个ACM领域的方法使用率、研究热度或年度趋势。

比例 = 当前队列中确认使用该方法的**不同文章数** ÷ 当前队列文章数。文章可以有多个标签，因此百分比不应相加。上位分类按研究去重，不直接累加子方法。

核对深度不同会影响已记录的方法数量。**未标注表示未确认，而非未使用；方法数量不代表研究质量或复杂度。** 同一患者队列或公共数据可能被多篇论文复用，文章数也不等于独立队列数。

标注由AI辅助阅读和既有审读记录整理，经针对性独立AI核查；尚未经过双人独立人工全文编码。详见[标注协议](docs/annotation_protocol.md)。

## 快速运行

Python 3.10+，运行和统计不依赖第三方库。

```bash
git clone https://github.com/Zero-soda/acm-methods-atlas.git
cd acm-methods-atlas
python3 -m unittest discover -s tests -v
python3 scripts/build_atlas.py
```

生成的目录在`docs/index.html`，可直接打开。三种统计口径：

```bash
python3 scripts/build_atlas.py --cohort manuscript
python3 scripts/build_atlas.py --cohort peer_reviewed --out /tmp/acm-peer-reviewed
python3 scripts/build_atlas.py --cohort all --out /tmp/acm-all
```

`manuscript`为23篇，`peer_reviewed`为24篇，`all`为25篇。默认生成文件与仓库提交的快照一致；其他口径建议输出到新目录。

## 数据与输出

| 路径 | 内容 |
|---|---|
| `data/studies.json` | 研究元数据、发表状态、综述引用与队列独立性说明 |
| `data/methods.json` | 方法概念及family/group分类 |
| `data/method_annotations.json` | 可追溯的研究—方法阳性标注 |
| `data/clinical_questions.json` | 综述问题映射的定义 |
| `data/context_sources.json` | 单列临床背景来源 |
| `data/research_paths.json` | 三条研究路径、逐篇发现/缺口、连接依据、待验证设计与两组跨研究差异 |
| `data/method_aliases.json` | 同义方法名归并记录 |
| `docs/method_summary.csv` | 当前默认队列的全部方法计数 |
| `docs/computational_methods.csv` | 计算与统计方法计数 |
| `docs/method_groups.csv` | 去重后的上位分类计数 |
| `docs/method_cooccurrence.csv` | 方法共现，不作因果或优劣解释 |
| `docs/exports/` | 可下载的研究及标注JSON/CSV |
| `docs/research_paths.html` | 可切换、可展开证据的研究路径图 |
| `docs/research_paths.md` | 完整文字路径及逐篇来源 |

[数据字典](docs/data_dictionary.md)说明字段。`tests/`检查分母、重复标注、上下位去重及关键科学区别。`contrib/`提供可选GitHub Actions检查模板。

## 与临床及综述的关系

临床问题映射用于连接“方法能回答什么问题”和“已有证据支持到哪一步”。它不是验证过的临床分期、风险评分或处方规则；指南、观察性病例、在研注册和会议报告保持各自证据层级。

未来重点是扩大文献覆盖、引入人类研究者独立核对、完善原文定位和队列复用关系，并评估方法组合能否帮助提出更明确的临床研究设计。

## 贡献、引用和许可

欢迎附原始来源提交[方法纠错或文献补充](CONTRIBUTING.md)。引用本项目时请记录版本，并引用支撑具体论点的原始研究；项目引用格式见[CITATION.cff](CITATION.cff)。

- 程序、测试及构建模板：[MIT](LICENSE)。
- 本项目原创归纳、说明和标注：[CC BY 4.0](LICENSE-DATA)。
- 第三方论文、图表和原始数据仍适用其自身权利与使用条件；本许可不重新许可这些材料。
