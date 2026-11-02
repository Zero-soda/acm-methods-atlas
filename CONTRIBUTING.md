# 补充文献与纠错

欢迎通过Issue或Pull Request补充研究、方法定位及数据复用说明。

1. 提供DOI或稳定的原始来源，说明是否为原始研究、预印本、综述、指南或注册。
2. 检查同一研究的预印本、正式版及队列复用，避免重复。
3. 在`data/studies.json`新增研究元数据，在`data/method_annotations.json`新增有来源的方法阳性标注。
4. 每条标注提供方法概念、原创简短证据概括、原文章节或图注定位及核对层级。不得以“通常会做”为理由填方法。
5. 新概念在`data/methods.json`定义family与group；同义词参考`data/method_aliases.json`，不要按软件名重复建统计类别。
6. 如研究只在摘要中读到，使用`abstract_only`；没有确认的平台和数据来源保持未知。
7. 运行以下检查并提交重新生成的`docs/`统计。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_atlas.py
```

请提交原创归纳或有授权的内容。论文PDF、第三方图表、患者级资料、凭证与未发表稿件不属于本仓库的贡献范围。代码贡献按MIT许可，原创标注和说明按CC BY 4.0许可。

## 提交标注的建议格式

```json
{
  "study_id": "ExistingStudyID",
  "method_id": "existing_method_id",
  "evidence_basis": "用自己的话说明原文实际做了什么",
  "source_locator": "Methods: exact subsection / Figure number",
  "annotation_status": "verified_local_text",
  "data_origin": "not_classified",
  "source_url": "https://doi.org/verified-doi"
}
```

## 可选GitHub Actions模板

`contrib/github-actions-validate.yml`提供与本地一致的检查模板。维护者可按仓库权限配置将其放入`.github/workflows/`。模板仅使用读取仓库所需权限，第三方Actions固定到已核对的提交。
