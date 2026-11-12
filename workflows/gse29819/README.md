# 配对双室表达：可运行的 ACM 复现案例

本例回答：**ARVC 供者内 RV−LV 表达差异是否不同于非衰竭对照，这一判断对分析方法和个别供者是否敏感？**

输入为 GSE29819：54,675 个探针、38 份心室组织，来自 **19 位独立供者**（ARVC 6、DCM 7、NF 6），每人完整配对 LV/RV。原研究已讨论双室表达；本例提供独立重分析与敏感性示范，不作为新生物学发现，也不是执行原作者的分析代码。

[在线结果、图与下载](https://zero-soda.github.io/acm-methods-atlas/workflows/gse29819/index.html) · [原始研究](https://pubmed.ncbi.nlm.nih.gov/22085907/) · [输入与研究设计](source_manifest.json) · [依赖源代码版本](environment.lock.json)

## 运行

要求 Python 3.10+、R（参考运行：4.4.3）、Poppler 的 `pdftocairo`。Python 使用标准库。R 包固定为 limma 3.62.2 和 statmod 1.5.1；版本与源码提交、SHA256 一起锁定。

```bash
# macOS 安装 Poppler；Linux 可使用发行版的 poppler-utils。
brew install poppler

# 在仓库根目录运行；--install 仅在依赖缺失/版本不符时安装。
python3 workflows/gse29819/run.py --install
```

安装 R 源码包时需要与 R 匹配的 C/Fortran 构建工具；不修改全局 R 包库。已有符合版本的包可以直接使用：

```bash
python3 workflows/gse29819/run.py
```

参考运行使用本机已有、版本匹配的 R 包；本机缺少 R 配置指定的 Fortran 编译器，因此**未验证本机从零源码编译安装**。本项目没有把依赖二进制、原始表达矩阵或患者级临床表打包发布。完整操作系统未容器化，其他系统的字体与图形渲染可能不同。

默认将约 21 MB 的公开源文件下载至忽略的 `.cache/gse29819/sources`，逐一验证 SHA256。校验失败立即停止，不自动接受新版注释。准备好的供者元数据和表达矩阵留在缓存中；只发布分析实现、聚合统计和生成图。

默认结果写入 `docs/workflows/gse29819`。也可以使用其他目录：

```bash
python3 workflows/gse29819/run.py --out /tmp/acm-gse29819-results

# 独立重跑，比较所有数值表的解压内容；不比较图形字体与 PDF 元数据。
python3 workflows/gse29819/run.py \
  --out /tmp/acm-gse29819-repeat \
  --verify-against docs/workflows/gse29819
```

`--source-dir PATH` 可复用既有下载，但必须与固定校验值一致。`--prepare-only` 只校验和准备输入。程序在临时目录完成整个运行后才更新结果目录，失败不会产生新的成功报告。

## 分析设计

1. 从官方矩阵头部提取样本、诊断、心室和供者信息；验证 38 份组织属于 19 对完整供者配对，保留年龄/性别缺失。
2. 确认存档数据为 MAS5 全局缩放后的正值线性信号，使用 `log2(x)`，不加伪计数；这不等同于重新处理原始 CEL 或 RMA。
3. 固定 GPL570 注释快照；删除缺失或多基因歧义探针。主分析将同基因探针的 log2 表达取均值，保留有限且可变的基因。未使用诊断差异筛选特征。
4. 主估计量为 `(RV−LV)_ARVC − (RV−LV)_NF`，统计单位是供者（6 对 6）。limma 使用趋势经验贝叶斯方差，`trend=TRUE, robust=FALSE`；趋势的平均表达来自原组织而非接近零的差值。
5. 单心室病组差异、DCM 对照、各组内心室差异单列为次要分析。BH 校正分别覆盖每项对比的全基因范围，未在所有探索性对比间联合校正。
6. 固定主分析基因全集，比较代表探针、额外分位数归一化、关闭方差趋势、完整病例未调整/年龄性别调整。代表探针按全部样本平均表达选择，与诊断标签无关。完整病例模型使用相同 11 位供者，以区分缺失排除与协变量调整。
7. 每次移除一位完整供者及其两份心室组织，共 12 次主分析留一检查；报告效应相关、方向与阈值计数。它属于同数据内的敏感性检查，不是外部验证。
8. 用全组织固定供者模型独立参数化同一交互作用，对照差值模型的系数、标准误、moderated t/P。固定供者模型不同时估计共线的病组主效应。

上述设计随实现固定，未前瞻性注册。没有从既有结果反复选择“最佳”模型替代主模型；所有预设实现的对比与敏感性一并输出。

## 输出与复用

- `index.html`：中文结果解释、临床下一步及全部下载入口。
- `figures/`：4 组图，每组 PDF、SVG、PNG。R 生成矢量 PDF，Poppler 从同一 PDF 转换其他格式，不依赖 X11。
- `contrast_summary.tsv`：主、次要、敏感性、留一模型的计数与分母。
- `gene_statistics.tsv.gz`：所有模型的基因效应、区间、P 与 BH 校正值；仅为组级统计，不含个体表达。
- `primary_gene_stability.tsv.gz`、`primary_leave_one_out_summary.tsv`：供者留一稳定性。
- `primary_sensitivity_summary.tsv`：方法选择敏感性。
- `paired_model_check.tsv`：两种参数化的数值一致性核查。
- `source_manifest.json`（源码目录）、`run_manifest.json`（结果目录）、`sessionInfo.txt`：源数据校验、脚本摘要、运行环境与状态。

这是 **GSE29819 专用案例**，其分组、输入规模及图表已固定。可直接复现本例，也可参考供者配对接口开发自己的工作流；它尚不是任意疾病、平台或分组的一键通用分析器。其他输入需要明确修改设计和校验，不应仅替换文件名运行。

## 对临床证据的贡献

本例复核 **B-S1 分子状态与区域临床表型连接中的心室组织表达一侧**。bulk 表达不能解析细胞空间邻域，终末期横断面数据不能重建病程先后。年龄与性别、细胞组成和病组差异仍可能影响结论；未显著也不能证明左右室等价。

下一项研究应获取同患者、同区域、接近时间的组织分子测量与 CMR／电标测配准，再接入明确定义的前瞻性临床结局；本例没有完成这一步。

## 引用与许可

- Gaertner et al. *Myocardial transcriptome analysis of human arrhythmogenic right ventricular cardiomyopathy*. [DOI: 10.1152/physiolgenomics.00094.2011](https://doi.org/10.1152/physiolgenomics.00094.2011).
- Ritchie et al. *limma powers differential expression analyses for RNA-sequencing and microarray studies*. [DOI: 10.1093/nar/gkv007](https://doi.org/10.1093/nar/gkv007).
- 引用 ACM Methods Atlas 时记录本项目版本。项目原创实现遵循仓库 MIT，归纳与原创图表遵循 CC BY 4.0；limma/statmod 保留其自身 GPL 许可，公开来源数据保留原条款。
