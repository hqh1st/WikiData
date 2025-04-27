# Wikidata数据处理与查询系统

一个功能完整的系统，用于从Wikidata API获取数据，使用不同的数据库后端进行存储，并通过自然语言进行查询和性能比较。

## 功能特点

* **数据获取** - 从Wikidata API获取实体数据，支持指定实体ID
* **多种存储后端** - 支持SQLite和TinyDB两种存储系统，可扩展
* **自然语言查询** - 支持基于关键词的自然语言查询处理
* **性能分析** - 内置性能比较工具，可对不同存储后端的查询效率进行分析
* **示例数据** - 提供示例数据生成功能，便于快速测试和演示
* **LLM检索比较** - 支持使用大语言模型进行语义检索，并与传统数据库检索结果进行比较

## 目录结构

```
.
├── main.py                 # 主程序入口
├── README.md               # 项目说明文档
├── requirements.txt        # 项目依赖列表
├── data/                   # 数据目录
│   └── wikidata_samples.json  # Wikidata样本数据
├── results/                # 结果输出目录
│   ├── comparison_chart.png   # 比较结果图表
│   └── comparison_results.json # 比较结果数据
└── src/                    # 源代码目录
    ├── fetch_wikidata.py   # Wikidata API数据获取模块
    ├── sqlite_storage.py   # SQLite存储实现
    ├── tinydb_storage.py   # TinyDB存储实现
    ├── comparison.py       # 性能比较工具
    ├── llm_comparison.py   # LLM检索比较工具
    └── query_handler.py    # 查询处理器
```

## 安装说明

1. 克隆或下载本仓库到本地
2. 安装所需依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

### 获取Wikidata数据

从Wikidata API获取特定实体数据：

```bash
python main.py --fetch --entities Q148 Q142
```

其中Q148是中国，Q142是法国的实体ID。如不指定实体ID，将使用以下默认实体：
- Q148 (中国)
- Q142 (法国)
- Q30 (美国)
- Q145 (英国)
- Q183 (德国)
- Q17 (日本)
- Q155 (巴西)
- Q159 (俄罗斯)

### 加载数据到存储系统

将获取的数据加载到SQLite和TinyDB：

```bash
python main.py --load
```

### 执行自然语言查询

使用自然语言执行查询，系统将同时在SQLite和TinyDB中查询并显示结果：

```bash
python main.py --query "What is the capital of China?"
python main.py --query "What is the population of France?"
```

目前支持的查询类型：
- 国家/城市人口查询 (包含"population"关键词)
- 国家首都查询 (包含"capital"关键词)

### 性能比较

比较SQLite和TinyDB在不同查询场景下的性能：

```bash
python main.py --compare
```

这将执行一系列预定义的查询，测量查询时间并生成比较报告。

### LLM检索比较

使用大语言模型进行语义检索，并与传统数据库检索结果进行比较：

```bash
python main.py --llm-compare
```

此功能会：
1. 使用传统数据库（SQLite）检索结果构建语料库
2. 采用预训练的语言模型进行语义检索
3. 比较LLM检索结果与传统数据库检索结果的差异
4. 计算精确率、召回率和F1分数
5. 生成可视化比较图表

**注意**：此功能需要安装额外的依赖包：
```bash
pip install transformers sentence-transformers torch
```

## 数据库结构

### SQLite存储结构

- **entities表**: 存储实体基本信息
  - entity_id (TEXT): 实体ID，主键
  - label (TEXT): 实体标签
  - description (TEXT): 实体描述
  - entity_type (TEXT): 实体类型

- **properties表**: 存储属性信息
  - property_id (TEXT): 属性ID，主键
  - label (TEXT): 属性标签
  - description (TEXT): 属性描述

- **statements表**: 存储主语-谓词-宾语的三元组关系
  - id (INTEGER): 自增主键
  - subject_id (TEXT): 主语实体ID
  - property_id (TEXT): 谓词属性ID
  - object_value (TEXT): 宾语值
  - object_type (TEXT): 宾语类型
  - object_entity_id (TEXT): 如果宾语是实体，存储实体ID

- **aliases表**: 存储实体的别名
  - id (INTEGER): 自增主键
  - entity_id (TEXT): 实体ID
  - alias (TEXT): 别名
  - language (TEXT): 语言代码

### TinyDB存储结构

- **entities表**: 存储实体和别名
  ```json
  {
    "entity_id": "Q148",
    "label": "China",
    "description": "People's Republic of China in East Asia",
    "type": "item",
    "aliases": [{"value": "中国", "language": "zh"}]
  }
  ```

- **properties表**: 存储属性信息
  ```json
  {
    "property_id": "P1082",
    "label": "人口",
    "description": "number of people inhabiting the place"
  }
  ```

- **statements表**: 存储主语-谓词-宾语的三元组关系
  ```json
  {
    "subject_id": "Q148",
    "property_id": "P1082",
    "object_value": "1412600000",
    "value_type": "quantity",
    "object_entity_id": null
  }
  ```

## LLM检索比较说明

LLM检索比较使用以下指标评估检索质量：

- **精确率(Precision)**: 检索结果中相关项目的比例
- **召回率(Recall)**: 被成功检索到的相关项目占总相关项目的比例
- **F1分数**: 精确率和召回率的调和平均值

比较结果以表格形式展示并通过柱状图可视化，帮助直观了解不同检索方法的差异。

## 开发者指南

### 添加新的存储后端

要添加新的存储后端，请遵循以下步骤：

1. 在`src`目录下创建新模块，如`mongodb_storage.py`
2. 实现一个新的存储类，实现以下关键方法：
   - `__init__(self, db_path=None)` - 初始化存储
   - `store_wikidata(self, json_file_path=None, entities_list=None)` - 存储Wikidata数据
   - `natural_language_query(self, query_text)` - 处理自然语言查询
   - `get_entity_by_id(self, entity_id)` - 根据ID获取实体
   - `close(self)` - 关闭数据库连接
3. 在`main.py`中导入并初始化该类的实例
4. 根据需要修改性能比较逻辑

```python
# 实现示例
from src.mongodb_storage import WikidataMongoDBStorage
mongodb_storage = WikidataMongoDBStorage()
```

### 扩展自然语言查询能力

当前的自然语言查询支持简单的关键词匹配。要扩展查询能力：

1. 在存储类中修改`natural_language_query`方法
2. 添加更多的查询模式和逻辑，例如：
   - 增加更多实体关系查询
   - 加入实体属性查询
   - 使用更高级的NLP技术进行查询理解

```python
# 示例：添加一个新的查询类型
if "area" in query_lower or "size" in query_lower:
    # 处理国家/城市面积查询逻辑
    # ...
```

### 增强LLM检索功能

如需增强LLM检索功能，可以考虑以下方面：

1. 添加不同的预训练模型支持：
   ```python
   # 在_init_models方法中添加新模型
   self.models['bert'] = AutoModel.from_pretrained('bert-base-multilingual-cased')
   ```

2. 优化语义检索算法：
   - 实现高级检索策略如混合检索
   - 添加查询扩展或重写功能
   - 集成知识图谱增强检索结果

3. 评估指标：
   - 添加更多评估指标如NDCG、MAP等
   - 实现用户反馈评估机制

## 许可证

本项目采用MIT许可证。详情请参阅LICENSE文件。
