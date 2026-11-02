# 数据字典

所有源JSON为UTF-8。`docs/exports/`是可重新生成的副本；编辑时修改`data/`。

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
