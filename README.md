# jupiter-study

木星伽利略卫星照片分析。58 张手机贴目镜拍摄的木星照片（2023-12-03 至 2024-01-11，31 个夜晚），
识别出每张照片中的木卫一至木卫四，换算成以木星半径（Rj）为单位的坐标，和 NASA JPL Horizons 星历对比，
并做成一个可交互的网页（照片浏览 + 3D 模型 + 分析图表）。

## 主要结果

| 项目 | 照片测得 | 真值 |
|---|---|---|
| 木卫一 Io 周期 | 1.768 ± 0.001 天 | 1.769 天 |
| 木卫二 Europa 周期 | 3.551 ± 0.002 天 | 3.551 天 |
| 木卫三 Ganymede 周期 | 7.149 ± 0.006 天 | 7.155 天 |
| 木卫四 Callisto 周期 | 16.70 ± 0.03 天 | 16.69 天 |
| 开普勒第三定律斜率 log a / log P | 0.671 | 2/3 |
| 木星质量（光晕修正后） | 1.80 × 10²⁷ kg | 1.90 × 10²⁷ kg |

- 一共识别出 186 个卫星位置（星历预计可见 219 个，其余大多太靠近木星，被光晕淹没）。
- 卫星之间的夹角：单张照片的测角精度约 ±3.6°，确认四颗卫星基本共面，但分辨不出它们轨道之间 <0.5° 的倾角差。
- 拍摄时间：文件名时间按太平洋标准时间（PST）解读，整体平移检验的最佳偏移只有 +5 分钟。
- 所有照片都是镜像的；画面随“视差角 + 高度角”旋转 → 推断使用的是**地平式支架 + 天顶镜**。只凭照片方向，估计观测地在北纬 32–41°、西经 114–121° 之间。

## 目录

```
data/manifest.csv          Drive 文件 ID、原文件名、大小
data/raw/                  原始照片（HEIC/JPEG，文件名 = 当地时间）
data/photos.csv            下载结果与解析出的拍摄时间
data/observer.json         观测地坐标（目前是占位值，见下）
data/detections.json       木星与候选光点
data/ephemeris_*.json      JPL Horizons 星历（拍摄时刻 + 逐小时）
data/positions.csv         每颗已识别卫星的坐标（像素、自定标 Rj、星历对齐 Rj、星历值）
data/photo_fits.json       每张照片的比例尺、方向、镜像、光晕系数等
data/results.json          周期拟合、开普勒、倾角、时间检验、画面旋转
scripts/01_download.py ... 06_analysis.py   处理流程（按编号依次运行）
tools/annotate.html        人工修正识别结果的小工具
web/                       交互网页（index.html + js/ + data.json + img/）
```

## 运行

```bash
pip install -r requirements.txt
```

```bash
for s in 01_download 02_decode 03_detect 04_ephemeris 05_calibrate 06_analysis; do python3 scripts/$s.py; done
```

第 3 步（检测）约 3–4 分钟；第 4 步需要能访问 `ssd.jpl.nasa.gov`。

查看网页（需要通过本地服务器打开，浏览器不允许直接从文件读取 data.json）：

```bash
python3 -m http.server -d web 8000
```

然后打开 http://localhost:8000 。

## 更新观测地坐标

`data/observer.json` 目前是占位值（加州圣何塞）。拿到实际坐标后修改 `lat_deg`、`lon_deg`（西经为负）、`elevation_m`，
把 `placeholder` 改成 `false`，再运行第 4–6 步。坐标几乎不影响卫星相对位置（< 0.001 Rj），但会影响木星高度、大气质量权重，
以及“画面旋转”检验。

## 人工修正

自动识别有遗漏时，用本地服务器在仓库根目录运行 `python3 -m http.server 8000`，打开
http://localhost:8000/tools/annotate.html ，在照片上点击放置卫星，下载得到的 `annotations.json` 放到 `data/`，
然后重新运行第 5–6 步。

## 方法要点

1. **找光点**：木星 = 最亮的饱和光斑，圆盘边缘取径向亮度下降最快处；卫星 = 扣除光晕背景后的局部亮点，过长的条纹（衍射星芒）排除。
2. **认卫星**：把星历预测的卫星分布缩放、旋转（镜像全局统一判定）后套到照片上，找对上最多光点的变换。
3. **两套坐标**：
   - 自定标（`X_self`）：木星圆盘半径当尺子，卫星连线当赤道方向，不依赖星历尺度，用于周期和开普勒定律；
   - 星历对齐（`X_fit`）：与星历最佳匹配的变换，用于残差和网页叠加。
4. **光晕系数**：过曝的木星在照片里平均比真实大 17%；它只影响半径和质量，不影响周期和开普勒斜率。
