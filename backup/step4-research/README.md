# 备份：第 4 步 ④–⑧（研究部分）

这里是第 4 步重做中 ④ 之后的内容的**备份**，不参与主项目运行。主项目到 ③ 为止。

## 内容
- `scripts/step4_peel.py`：④ 往里剥，按 |X| 空隙逐颗折叠（找到 16.7 天、7.15 天两颗）。
- `scripts/step4_inner.py`：④b 内侧两颗一起找（偏差 + "该在却不在"打分）。
- `scripts/step4_joint.py`：⑤ 四颗一起归属光点；⑥ "每天多转一圈"对手；⑦ 扁圆（离线摆动）；⑧ 周期比、P–a 关系。
- `tests/test_step4_joint.py`：joint 的单元测试。
- `output/`：三个脚本的输出 JSON。
- `demo/view.html`、`demo/step4_data.json`：含 ①–⑧ 的完整页面和数据。
- `page_and_docs.diff`：相对主项目（到 ③）的页面、页面测试和 PROGRESS 的改动。

## 恢复到主项目
```bash
cp backup/step4-research/scripts/*.py scripts/
cp backup/step4-research/tests/*.py tests/
mkdir -p output/step4 && cp backup/step4-research/output/*.json output/step4/
git apply backup/step4-research/page_and_docs.diff   # 或直接用 demo/view.html 覆盖
# 依次运行：step4_raw_plot → step4_tracks → step4_fold → step4_peel → step4_inner → step4_joint
```

## 结果（只用照片，照片误差）
- I 1.7688 ± 0.0008 天，II 3.5523 ± 0.0020，III 7.1518 ± 0.0058，IV 16.692 ± 0.024
- 205 个光点 204 个归属（20 个两颗共用）
- 四颗离线摆动同号，倾斜 1.7–2.9°：同一平面、同一方向
- log P–log a 斜率 1.47 ± 0.02（开普勒 1.5）；P2/P1 = 2.008，P3/P2 = 2.013；1/P1 − 3/P2 + 2/P3 = (0.5 ± 0.6)×10⁻³ 圈/天

## 待做
每张照片的比例修正、绝对比例校准（第 28 张）、README 更新、页面顶部摘要换新结果。
