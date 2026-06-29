# Expansion-Squeeze-Excitation Fusion Network for Elderly Activity Recognition — 论文解析报告

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| **论文标题** | Expansion-Squeeze-Excitation Fusion Network for Elderly Activity Recognition |
| **中文译名** | 面向老年人活动识别的扩展-压缩-激励融合网络 |
| **作者** | Xiangbo Shu, Jiawen Yang, Rui Yan, Yan Song |
| **单位** | 南京理工大学 计算机科学与工程学院 |
| **发表期刊** | IEEE Transactions on Circuits and Systems for Video Technology (IEEE TCSVT) |
| **卷/期/年** | Vol. 32, No. 8, August 2022 |
| **页数** | 12页 (页码 5281–5292) |
| **DOI** | 10.1109/TCSVT.2022.3142771 |
| **投稿/录用日期** | 2021年11月16日投稿，2022年1月9日录用，2022年1月13日在线发表 |

---

## 二、研究背景与动机

### 2.1 问题定义

本文聚焦于**老年人活动识别（Elderly Activity Recognition）**任务。随着人口老龄化加剧，空巢老人比例不断上升，利用计算机视觉技术对老年人日常活动进行智能监测具有重要意义。

### 2.2 挑战

与常规动作识别相比，老年人活动识别面临以下独特挑战：

1. **个体动作与人-物交互并存**：老年人活动中既包含纯身体动作（个体动作），也包含与物体交互的行为（如吹头发、梳头）。
2. **局部交互微小**：许多人-物交互动作是局部性的（如手部细微动作），容易被忽略。
3. **动作幅度不明显**：老年人动作幅度较小，特征不显著。
4. **相似动作混淆**：某些动作在时空轨迹上非常相似，仅靠微小的局部差异（如手中物体不同）才能区分。

**典型案例**（如图2所示）：
- "吹头发" vs "梳头"：动作轨迹和幅度高度相似，仅交互物体不同（吹风机 vs 梳子）
- "打电话" vs "玩手机"：大部分运动和交互对象相同，仅局部手部动作有差异

---

## 三、核心方法：ESE-FN

### 3.1 总体框架

ESE-FN（Expansion-Squeeze-Excitation Fusion Network）的整体框架（图3）包含四个核心模块：

1. **特征提取模块（Feature Extractor Module）**
2. **模态融合模块（Modal-Fusion Module）— M-Net**
3. **通道融合模块（Channel-Fusion Module）— C-Net**
4. **多模态损失（Multi-modal Loss）**

**整体流程**：

```
RGB视频 → RGB主干网络(ResNeXt101) → RGB特征 fr
骨架序列 → 骨架主干网络(Shift-GCN) → 骨架特征 fs
     ↓
特征拼接 → M-Net（模态级ESE融合） → C-Net（通道级ESE融合） → 融合特征 frs
     ↓
多模态损失优化（同时使用 fr, fs, frs）
```

### 3.2 SENet回顾（理论基础）

SENet通过两个步骤学习通道级非线性注意力：

- **Squeeze（压缩）**：全局平均池化获得通道级表示
- **Excitation（激励）**：通过全连接层+Sigmoid获得通道级注意力权重

本文的创新点在于：在SENet的Squeeze之前引入**Expansion（扩展）**步骤，形成**ESE**（Expansion-Squeeze-Excitation）结构。

### 3.3 M-Net（模态融合网络）

M-Net通过**模态级ESE注意力（M-ESEA）**实现模态间的粗粒度融合：

**三个步骤**：
1. **模态级扩展（Modal-wise Expansion）**：使用多个不同卷积核的卷积层堆叠，从局部视角扩展模态信息，捕获局部空间相关性
2. **模态级压缩（Modal-wise Squeeze）**：通过全局平均池化，从全局视角获得模态级表示，捕获全局空间相关性
3. **模态级激励（Modal-wise Excitation）**：通过FC层+Sigmoid学习M-ESEA注意力权重，更新特征

**核心创新**：扩展+压缩的结合，实现了从**局部和全局两个视角**交互特征信息，优于SENet仅使用全局池化。

### 3.4 C-Net（通道融合网络）

C-Net通过**通道级ESE注意力（C-ESEA）**实现通道间的细粒度融合：

**三个步骤**：
1. **通道级扩展（Channel-wise Expansion）**：使用单层卷积扩展通道信息（因经过M-Net后跨模态差异已减小，只需较小扩展）
2. **通道级压缩（Channel-wise Squeeze）**：全局平均池化获得通道级表示
3. **通道级激励（Channel-wise Excitation）**：通过FC层+Sigmoid学习C-ESEA注意力权重

**关键设计**：M-Net（粗融合）→ C-Net（细融合）逐步递进，M-Net使用多层卷积（大扩展），C-Net使用单层卷积（小扩展），实现轻量化设计。

### 3.5 多模态损失（Multi-modal Loss, ML）

设计了一种新损失函数，核心思想：**保持单模态特征与融合多模态特征之间的一致性**。

**公式**：
```
L = α × L_rs + β × (min(L_r, L_s) − L_rs)
```

其中：
- `L_r`：RGB模态的交叉熵损失
- `L_s`：骨架模态的交叉熵损失
- `L_rs`：融合模态的交叉熵损失
- `α`, `β`：超参数（实验最优值：α=0.7, β=0.3）

**创新点**：引入惩罚项 `min(L_r, L_s) − L_rs`，促使融合特征的预测损失不低于最优单模态的预测损失，从而保证融合特征的有效性。

---

## 四、实验设置

### 4.1 数据集

#### 主要数据集：ETRI-Activity3D
- **规模**：目前最大的老年人活动识别数据集
- **样本数**：112,620个样本
- **参与者**：100人
- **数据模态**：RGB视频、深度图、骨架序列
- **类别数**：55类（包含个体活动、人-物交互、多人交互）
- **采集环境**：真实监控环境
- **划分方式**：按Person ID划分（奇数为测试集，偶数为训练集）

#### 扩展实验数据集：NTU RGB+D
- **规模**：56,880个骨架序列，60个类别，40个受试者
- **评价协议**：Cross-Subject (CS) 和 Cross-View (CV)

### 4.2 实现细节

| 参数 | 设置 |
|------|------|
| 视频分片数 T | 64 clips |
| RGB主干网络 | ResNeXt101（默认）/ ResNeXt18（消融实验） |
| 骨架主干网络 | Shift-GCN |
| 优化器 | SGD |
| 动量 | 0.9 |
| 初始学习率 | 0.1 |
| 权重衰减 | 10⁻⁴ |
| Batch Size | 32 |
| 总Epochs | 30 |
| 框架 | PyTorch |
| 硬件 | Titan RTX GPU |

### 4.3 超参数诊断

通过实验调优超参数 α 和 β（图7），确定最优组合：
- **α = 0.7, β = 0.3**

当 β = 0 时（退化为基础损失），性能明显下降，验证了多模态损失的有效性。

---

## 五、实验结果

### 5.1 消融实验

#### 组件消融（表II）

| 基线 | 描述 | 准确率 |
|------|------|--------|
| B1 | 仅RGB单模态 | 较低 |
| B2 | 仅骨架单模态 | 较低 |
| B3 | 简单拼接多模态 | 基准 |
| B4 | ESE-FN w/o C-Net | 优于B3 |
| B5 | ESE-FN w/o M-Net | 优于B3 |
| B6 | ESE-FN w/o ML | 优于B4/B5 (+0.4%/+1.2%) |
| **B7** | **完整ESE-FN** | **最佳** |

**结论**：M-Net、C-Net、ML三个组件均对性能有正向贡献，完整ESE-FN效果最优。

#### 与SENet对比（表III）

| 基线 | 描述 | 准确率 |
|------|------|--------|
| A1 | SENet仅通道融合 | 较低 |
| A2 | SENet仅模态融合 | 较低 |
| A3 | SENet模态+通道融合 | 较高 |
| A4 | ESE-FN仅通道融合 | 较高 |
| A5 | ESE-FN仅模态融合 | 较高 |
| **A6** | **ESE-FN模态+通道融合（完整）** | **最佳** |

**结论**：ESE-FN比SENet高出0.6%，验证了Expansion步骤的有效性；模态+通道双重融合策略优于单一融合策略。

### 5.2 老年人活动识别性能（ETRI-Activity3D）

| 方法 | 模态 | 准确率 |
|------|------|--------|
| Deep Bilinear Learning | RGB+Depth+Skeleton | - |
| Evolution Pose Map | 2D/3D Pose | - |
| c-ConvNet | RGB+Depth | - |
| FSA-CNN | 2D/3D Skeleton | 93.7% |
| **ESE-FN (Ours)** | **RGB+Skeleton** | **95.9%** |

**主要结果**：
- ESE-FN达到 **95.9%** 的准确率，为当前最优（SOTA）
- 比前SOTA方法FSA-CNN（93.7%）高出 **2.2%**（相对提升2.3%）
- 混淆矩阵（图8）显示ESE-FN主对角线颜色明显更亮，说明各活动类别识别效果均很好

### 5.3 常规动作识别性能（NTU RGB+D）

| 方法 | CS准确率 | CV准确率 |
|------|----------|----------|
| ST-GCN | - | - |
| Shift-GCN | - | 96.5% |
| Evolution Pose Map | 91.7% | - |
| **ESE-FN (Ours)** | **92.4%** | **96.7%** |

**结论**：ESE-FN在常规动作识别任务上也取得了有竞争力的结果（CS提升0.7%，CV提升0.2%），验证了方法的泛化能力。

---

## 六、论文贡献总结

1. **提出ESE-FN框架**：首次将扩展（Expansion）引入SENet家族，形成Expansion-Squeeze-Excitation（ESE）结构，用于多模态特征的注意力融合
2. **设计M-Net和C-Net**：分别从模态级和通道级捕获特征依赖关系，实现从粗到细的递进式融合
3. **提出多模态损失ML**：通过惩罚项保持单模态与融合特征之间的一致性
4. **取得SOTA性能**：在ETRI-Activity3D上达到95.9%，并在NTU RGB+D上验证了泛化能力

---

## 七、论文结构概览

| 章节 | 内容 |
|------|------|
| **I. Introduction** | 研究背景、问题定义、挑战、方法概述、贡献总结 |
| **II. Related Work** | RGB-based方法、Skeleton-based方法、多模态融合相关工作综述 |
| **III. Methodology** | SENet回顾、ESE-FN整体框架、M-Net详述、C-Net详述、多模态损失 |
| **IV. Experiments** | 数据集介绍、实现细节、超参数诊断、消融实验、对比实验、扩展实验 |
| **V. Conclusion** | 方法总结、贡献重申、讨论与展望 |
| **References** | 71篇参考文献 |

---

## 八、关键图表索引

| 图/表编号 | 内容描述 |
|-----------|----------|
| 图1 | 方法核心理念示意：模态级和通道级ESE注意力融合 |
| 图2 | 老年人活动示例：相似动作对比（吹头发vs梳头、打电话vs玩手机） |
| 图3 | ESE-FN整体框架图 |
| 图4 | M-Net详细配置图 |
| 图5 | C-Net详细配置图 |
| 图6 | 训练Loss和Accuracy曲线 |
| 图7 | 超参数α和β的敏感性分析 |
| 图8 | ETRI-Activity3D上的混淆矩阵对比 |
| 图9 | NTU RGB+D上的混淆矩阵 |
| 表I | 不同主干网络的表示能力对比 |
| 表II | 组件消融实验 |
| 表III | 与SENet对比消融实验 |
| 表IV | ETRI-Activity3D上与SOTA方法对比 |
| 表V | NTU RGB+D上与SOTA方法对比 |

---

## 九、讨论与局限性

论文在Conclusion部分讨论指出：

1. **与SENet的关系**：本文借鉴SENet的通道注意力思想，但引入了Expansion步骤实现上采样和下采样的特征交互，是SENet家族中首次尝试
2. **扩展性**：ESE-FN不仅限于老年人活动识别，还可推广到一般特征学习和多模态特征融合任务
3. **本文是首个将扩展+压缩结合用于非线性注意力学习的工作**

---

*报告生成日期：2026年6月26日*
*源文件：Expansion-Squeeze-Excitation_Fusion_Network_for_Elderly_Activity_Recognition.pdf (IEEE TCSVT 2022)*
