# 数据字典

所有源JSON为UTF-8。`docs/exports/`是可重新生成的副本；编辑时修改`data/`。

## 关系条件审计：connection_evidence.json

`relations` 的单位是选定研究内关系断言，不是论文、患者或完整全文断言全集。`study_id` 关联原始研究，`design_domain` 是该断言的主要支持设计，不能当整篇唯一设计或质量分；同论文可跨域。四个 `*_basis` 对象保存原始可解释 `code` 及 `description_zh`，不将不同细分code强制合为统一量表。每条保留来源定位、边界及人工复核状态。

`clinical_bridges` 是6个预先定义的临床问题，各列必要条件、已有片段、缺失对齐和不适用于该问题的要求。`not_identified_in_pilot_corpus` 表示当前先导审读未检出直接目标验证，不推断全领域不存在。人体观察性用药没有被编码为受控干预；病例真实时间记录也没有被当作前瞻比较试验。

`human_connection_review_template.csv` 为待两位研究者填写的空白复核列；空白不表示已确认。`searches/` 中记录均为 `not_screened_this_update`，重复平台记录经DOI/PMID去重后仍是候选，不能充当纳入分母。`current_run.json` 指向当前运行目录，初版和修订版保留各自精确策略及方案hash。PubMed出版日期与Europe PMC首次发表日期语义不同，正式筛选需核对版本/日期。

## 研究路径：research_paths.json

`paths` 保存三条问题路径；`stages` 记录阶段问题、代表研究及未解问题；`connections` 记录阶段之间的联系与推断边界。`relation_type` 仅接受 `research_synthesis`（跨研究整合）、`parallel_evidence`（并行互补）和 `proposed_bridge`（待验证桥接），不默认因果、直接引用或患者共同病程。

`study_summaries` 以已有 `study_id` 关联逐篇问题、方法、研究内发现、未解问题、原始来源及定位。`next_study` 为尚未执行的研究提议，包含问题、设计、测量、结局、可能削弱假说的结果及公开数据能完成的步骤。`cross_paper_tensions` 是有限的跨研究差异比较，`scholar_confirmation: pending` 表示解释尚待研究者确认。

路径图固定覆盖综述的23篇正式研究，独立于方法统计页面的队列切换；不是25条目录记录全部强行组成一条线。

## 研究目录：studies.json

| 字段 | 含义 |
|---|---|
| `study_id` | 稳定研究键，沿用文献核验记录 |
| `title`, `doi`, `url`, `year` | 原始来源元数据；年份可为卷期年，不据此推断全部实验发生时间 |
| `publication_status` | `peer_reviewed`或`preprint` |
| `in_manuscript` | 是否在本轮综述实际引用，用于默认统计队列 |
| `systems` | 已确认的临床/人体组织、动物、体外或工程化模型系统；不是患者数 |
| `reading_depth` | 相关段落阅读或既有核验的范围 |
| `clinical_question_ids` | 综述问题映射；可多标签 |
| `independence_note` | 同一研究版本、患者或数据复用等说明 |

## 方法定义：methods.json

`method_id`是稳定概念键；`label_zh`为名称；`family`为四类方法维度；`group_id`用于更高层级的去重汇总。详见[标注协议](annotation_protocol.md)。

细项可能属于重叠的技术层级，例如常规CMR、LGE及同人重复CMR；相加没有实验数意义。软件名通常保留在证据说明，不另建重复概念。

## 阳性长表：method_annotations.json

| 字段 | 含义 |
|---|---|
| `annotation_id` | `study_id::method_id`，唯一研究—方法组合 |
| `study_id`, `method_id` | 对应研究与方法 |
| `evidence_basis` | 本项目原创简短证据概括，不是论文原文转载 |
| `source_locator` | 原文章节/图注或明确标识的既有审读定位 |
| `annotation_status` | 原文相关段落核对、既有审读依据、或摘要级 |
| `data_origin` | `generated`、`reused`、`not_classified`；未确认时不猜测 |
| `source_url` | 稳定的原始来源链接 |

本表仅包含有依据的阳性标注。缺行不能转成“未使用”或阴性证据。

## 背景与版本

`context_sources.json`单列不进入方法统计的临床背景。`manifest.json`记录版本、证据截止日、标注日期、抽样范围与更正说明。`method_aliases.json`记录同义键归并。

## 导出统计

`n_studies`为确认标注的不同文章数，`denominator`为选定队列篇数，`percent`为二者比例，`study_ids`允许逐项追溯。方法共现只表示同篇报告，不表示验证了两方法间的机制联系。
