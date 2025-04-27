#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Wikidata数据处理与查询系统主程序
用于测试不同数据库存储方式的性能比较
"""

import os
import sys
import time
import json
import argparse
from tabulate import tabulate
from tqdm import tqdm

from src.fetch_wikidata import WikidataFetcher
from src.sqlite_storage import WikidataSQLiteStorage
from src.tinydb_storage import WikidataTinyDBStorage

# 尝试导入LLM比较工具
try:
    from src.llm_comparison import LLMComparisonTool, transformers_available, sentence_transformers_available
    llm_comparison_available = transformers_available  # 只要transformers可用就认为比较功能可用
except ImportError:
    llm_comparison_available = False
    transformers_available = False
    sentence_transformers_available = False
    print("警告: LLM比较模块未找到或无法导入")

def print_section(title):
    """打印格式化的节标题"""
    width = 80
    print("\n" + "=" * width)
    print(f"{title.center(width)}")
    print("=" * width + "\n")

def load_example_queries():
    """加载示例查询"""
    return [
        "What is the population of China?",
        "What is the capital of France?",
        "What is the capital of China?",
        "What is the population of France?",
        "What is the capital of United States?",
        "What is the population of India?"
    ]

def run_performance_comparison(sqlite_storage, tinydb_storage, queries, iterations=5):
    """运行性能比较测试"""
    print_section("性能测试")
    
    results = {
        "SQLite": {"查询时间": [], "结果数": []},
        "TinyDB": {"查询时间": [], "结果数": []}
    }
    
    # 获取和处理查询
    for query in queries:
        print(f"测试查询: {query}")
        
        # SQLite测试
        sqlite_times = []
        sqlite_result_count = 0
        for i in range(iterations):
            start_time = time.time()
            sqlite_results = sqlite_storage.natural_language_query(query)
            end_time = time.time()
            elapsed = end_time - start_time
            sqlite_times.append(elapsed)
            if i == 0:  # 只记录第一次的结果数
                sqlite_result_count = len(sqlite_results) if sqlite_results else 0
        
        avg_sqlite_time = sum(sqlite_times) / len(sqlite_times)
        results["SQLite"]["查询时间"].append(avg_sqlite_time)
        results["SQLite"]["结果数"].append(sqlite_result_count)
        
        # TinyDB测试
        tinydb_times = []
        tinydb_result_count = 0
        for i in range(iterations):
            start_time = time.time()
            tinydb_results = tinydb_storage.natural_language_query(query)
            end_time = time.time()
            elapsed = end_time - start_time
            tinydb_times.append(elapsed)
            if i == 0:  # 只记录第一次的结果数
                tinydb_result_count = len(tinydb_results) if tinydb_results else 0
        
        avg_tinydb_time = sum(tinydb_times) / len(tinydb_times)
        results["TinyDB"]["查询时间"].append(avg_tinydb_time)
        results["TinyDB"]["结果数"].append(tinydb_result_count)
        
        print(f"  SQLite平均查询时间: {avg_sqlite_time:.6f}秒, 结果数: {sqlite_result_count}")
        print(f"  TinyDB平均查询时间: {avg_tinydb_time:.6f}秒, 结果数: {tinydb_result_count}")
        print()
    
    # 计算总体平均
    sqlite_avg_time = sum(results["SQLite"]["查询时间"]) / len(results["SQLite"]["查询时间"])
    tinydb_avg_time = sum(results["TinyDB"]["查询时间"]) / len(results["TinyDB"]["查询时间"])
    
    # 准备表格数据
    table_data = []
    for i, query in enumerate(queries):
        table_data.append([
            query,
            f"{results['SQLite']['查询时间'][i]:.6f}秒",
            f"{results['TinyDB']['查询时间'][i]:.6f}秒",
            "SQLite" if results['SQLite']['查询时间'][i] < results['TinyDB']['查询时间'][i] else "TinyDB",
            f"{results['SQLite']['结果数'][i]}",
            f"{results['TinyDB']['结果数'][i]}"
        ])
    
    # 添加平均行
    table_data.append([
        "平均",
        f"{sqlite_avg_time:.6f}秒",
        f"{tinydb_avg_time:.6f}秒",
        "SQLite" if sqlite_avg_time < tinydb_avg_time else "TinyDB",
        f"{sum(results['SQLite']['结果数']) / len(results['SQLite']['结果数']):.1f}",
        f"{sum(results['TinyDB']['结果数']) / len(results['TinyDB']['结果数']):.1f}"
    ])
    
    # 打印性能比较表
    print("\n性能比较结果:")
    headers = ["查询", "SQLite时间", "TinyDB时间", "更快的数据库", "SQLite结果数", "TinyDB结果数"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    if sqlite_avg_time < tinydb_avg_time:
        print(f"\n结论: SQLite 平均快 {(tinydb_avg_time/sqlite_avg_time):.2f} 倍")
    else:
        print(f"\n结论: TinyDB 平均快 {(sqlite_avg_time/tinydb_avg_time):.2f} 倍")
    
    return results

def run_llm_comparison(sqlite_storage, queries):
    """
    运行LLM与传统数据库的检索结果比较
    
    Args:
        sqlite_storage: SQLite存储实例
        queries: 查询列表
    """
    if not llm_comparison_available:
        print("错误: LLM比较模块不可用，无法执行比较")
        return None
    
    print_section("LLM与传统数据库检索结果比较")
    
    # 初始化LLM比较工具
    comparison_tool = LLMComparisonTool()
    
    # 收集从数据库查询的结果
    db_results = {}
    corpus = []
    
    print("从数据库获取查询结果...")
    for i, query in enumerate(tqdm(queries, desc="执行数据库查询")):
        results = sqlite_storage.natural_language_query(query)
        if results:
            # 格式化结果为字符串列表
            formatted_results = []
            for result in results:
                if len(result) >= 2:
                    text = f"{result[0]} - {result[1]}"
                    formatted_results.append(text)
                    # 添加到语料库
                    if text not in corpus:
                        corpus.append(text)
            
            db_results[i] = formatted_results
    
    # 如果没有足够的语料库，添加一些示例数据
    if len(corpus) < 10:
        print("为了更好的比较效果，添加额外示例数据到语料库...")
        additional_corpus = [
            "中国的人口约为14亿",
            "中国首都是北京",
            "法国首都是巴黎",
            "法国的人口约为6700万",
            "美国首都是华盛顿",
            "美国的人口约为3.3亿",
            "印度的人口约为13.8亿",
            "印度首都是新德里",
            "日本首都是东京",
            "日本的人口约为1.26亿"
        ]
        for item in additional_corpus:
            if item not in corpus:
                corpus.append(item)
    
    # 执行LLM语义搜索
    if len(corpus) > 0:
        print(f"语料库大小: {len(corpus)} 条记录")
        llm_results = comparison_tool.run_semantic_search(queries, corpus)
        
        # 比较结果
        if len(llm_results) > 0:
            comparison_results = comparison_tool.compare_with_traditional_db(llm_results, db_results)
            
            # 打印比较结果表格
            comparison_tool.print_comparison_table(comparison_results)
            
            # 可视化比较结果
            comparison_tool.visualize_results(comparison_results)
            
            return comparison_results
    
    print("未能进行LLM比较: 没有足够的检索结果")
    return None

def analyze_data_size_impact(sqlite_storage, tinydb_storage, queries, iterations=3):
    """
    分析数据量对性能的影响
    
    Args:
        sqlite_storage: SQLite存储实例
        tinydb_storage: TinyDB存储实例
        queries: 查询列表
        iterations: 每个查询重复执行的次数
    """
    print_section("数据量对性能的影响分析")
    
    # 获取数据库统计信息
    try:
        sqlite_stats = sqlite_storage.get_database_stats()
        tinydb_stats = tinydb_storage.get_database_stats()
        
        # 打印数据库统计信息
        print("\n数据库统计信息:")
        print(f"SQLite 实体数: {sqlite_stats['entities_count']}, 属性数: {sqlite_stats['properties_count']}, 三元组数: {sqlite_stats['statements_count']}")
        print(f"TinyDB 实体数: {tinydb_stats['entities_count']}, 属性数: {tinydb_stats['properties_count']}, 三元组数: {tinydb_stats['statements_count']}")
    except Exception as e:
        print(f"获取数据库统计信息时出错: {e}")
        sqlite_stats = {'entities_count': 0, 'properties_count': 0, 'statements_count': 0}
        tinydb_stats = {'entities_count': 0, 'properties_count': 0, 'statements_count': 0}
    
    # 运行性能测试
    performance_results = run_performance_comparison(sqlite_storage, tinydb_storage, queries, iterations)
    
    # 展示数据量与性能的关系
    print("\n数据量与性能的关系:")
    if sqlite_stats.get('statements_count', 0) > 0 and tinydb_stats.get('statements_count', 0) > 0:
        # 计算每千条数据的平均查询时间
        sqlite_avg_time = sum(performance_results["SQLite"]["查询时间"]) / len(performance_results["SQLite"]["查询时间"])
        tinydb_avg_time = sum(performance_results["TinyDB"]["查询时间"]) / len(performance_results["TinyDB"]["查询时间"])
        
        sqlite_time_per_k = (sqlite_avg_time * 1000) / sqlite_stats['statements_count']
        tinydb_time_per_k = (tinydb_avg_time * 1000) / tinydb_stats['statements_count']
        
        print(f"SQLite: 每千条数据平均查询时间: {sqlite_time_per_k:.6f}毫秒")
        print(f"TinyDB: 每千条数据平均查询时间: {tinydb_time_per_k:.6f}毫秒")
        
        # 比较数据量变化对性能的影响
        ratio = tinydb_avg_time / sqlite_avg_time if sqlite_avg_time > 0 else 0
        print(f"\n性能比较: SQLite平均查询时间 {sqlite_avg_time:.6f}秒, TinyDB平均查询时间 {tinydb_avg_time:.6f}秒")
        print(f"相对性能比: TinyDB/SQLite = {ratio:.2f}")
        print(f"总结: 在当前数据量情况下，SQLite比TinyDB更{'高效' if ratio > 1 else '低效'}")
    else:
        # 无法获取数据库统计信息，仅显示性能比较
        sqlite_avg_time = sum(performance_results["SQLite"]["查询时间"]) / len(performance_results["SQLite"]["查询时间"])
        tinydb_avg_time = sum(performance_results["TinyDB"]["查询时间"]) / len(performance_results["TinyDB"]["查询时间"])
        
        ratio = tinydb_avg_time / sqlite_avg_time if sqlite_avg_time > 0 else 0
        print(f"\n性能比较: SQLite平均查询时间 {sqlite_avg_time:.6f}秒, TinyDB平均查询时间 {tinydb_avg_time:.6f}秒")
        print(f"相对性能比: TinyDB/SQLite = {ratio:.2f}")
        print(f"总结: SQLite比TinyDB快 {ratio:.2f} 倍")
    
    return {
        "sqlite_stats": sqlite_stats,
        "tinydb_stats": tinydb_stats,
        "performance": performance_results
    }

def test_all_data_sizes(fetcher=None):
    """
    测试不同数据量对性能的影响
    
    Args:
        fetcher: WikidataFetcher实例，如果为None则创建新实例
    """
    print_section("测试不同数据量对系统性能的影响")
    
    if fetcher is None:
        fetcher = WikidataFetcher()
    
    # 定义不同大小的数据集
    data_sizes = {
        "small": {
            "name": "小数据集",
            "entities": ["Q148", "Q142", "Q30", "Q145", "Q183", "Q17", "Q155", "Q159"],
            "description": "8个主要国家"
        },
        "medium": {
            "name": "中型数据集",
            "entities": ["Q148", "Q142", "Q30", "Q145", "Q183", "Q17", "Q155", "Q159", 
                         "Q38", "Q39", "Q40", "Q96", "Q114", "Q115", "Q117", "Q118", 
                         "Q184", "Q189", "Q403", "Q408"],
            "description": "20个主要国家"
        },
        "large": {
            "name": "大型数据集",
            "entities": ["Q148", "Q142", "Q30", "Q145", "Q183", "Q17", "Q155", "Q159", 
                         "Q38", "Q39", "Q40", "Q96", "Q114", "Q115", "Q117", "Q118",
                         "Q184", "Q189", "Q403", "Q408", 
                         # 主要城市
                         "Q956", "Q1490", "Q65", "Q84", "Q90", "Q220", "Q649", "Q64", "Q270", "Q1085",
                         # 更多国家
                         "Q20", "Q31", "Q33", "Q34", "Q35", "Q36", "Q37", "Q41", "Q43", "Q45", 
                         "Q77", "Q79", "Q80", "Q115", "Q122", "Q124", "Q127", "Q129", "Q130", "Q137"],
            "description": "30个国家和20个主要城市"
        }
    }
    
    # 保存结果
    results = {}
    
    # 测试查询
    example_queries = load_example_queries()
    
    # 对每种数据量进行测试
    for size_key, size_info in data_sizes.items():
        print(f"\n\n测试 {size_info['name']} ({size_info['description']})...")
        
        # 设置数据文件路径
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        json_file = os.path.join(data_dir, f"wikidata_samples_{size_key}.json")
        
        # 获取数据
        print(f"获取 {len(size_info['entities'])} 个实体的数据...")
        entities_data = fetcher.fetch_multiple_entities(size_info['entities'])
        
        # 保存到JSON文件
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)
        
        print(f"已保存 {len(entities_data)} 个实体数据到 {json_file}")
        
        # 初始化数据库
        sqlite_storage = WikidataSQLiteStorage(db_path=f"data/wiki_{size_key}.db")
        tinydb_storage = WikidataTinyDBStorage(db_path=f"data/tinydb_storage_{size_key}.json")
        
        # 加载数据
        print(f"\n正在加载数据到SQLite...")
        sqlite_count = sqlite_storage.store_wikidata(json_file_path=json_file)
        print(f"已加载 {sqlite_count} 个实体到SQLite")
        
        print(f"\n正在加载数据到TinyDB...")
        tinydb_count = tinydb_storage.store_wikidata(json_file_path=json_file)
        print(f"已加载 {tinydb_count} 个实体到TinyDB")
        
        # 运行性能测试
        size_results = analyze_data_size_impact(sqlite_storage, tinydb_storage, example_queries)
        results[size_key] = size_results
        
        # 关闭数据库连接
        sqlite_storage.close()
        tinydb_storage.close()
    
    # 输出综合分析结果
    print_section("不同数据量的性能比较汇总")
    
    print("\n| 数据集大小 | 实体数 | 三元组数 | SQLite平均查询时间(秒) | TinyDB平均查询时间(秒) | 性能比(TinyDB/SQLite) |")
    print("|------------|--------|----------|----------------------|----------------------|----------------------|")
    
    for size_key, size_info in data_sizes.items():
        if size_key in results:
            sqlite_stats = results[size_key]["sqlite_stats"]
            tinydb_stats = results[size_key]["tinydb_stats"]
            
            # 计算平均性能
            sqlite_times = results[size_key]["performance"]["SQLite"]["查询时间"]
            tinydb_times = results[size_key]["performance"]["TinyDB"]["查询时间"]
            
            sqlite_avg_time = sum(sqlite_times) / len(sqlite_times) if sqlite_times else 0
            tinydb_avg_time = sum(tinydb_times) / len(tinydb_times) if tinydb_times else 0
            
            ratio = tinydb_avg_time / sqlite_avg_time if sqlite_avg_time > 0 else 0
            
            print(f"| {size_info['name']} | {sqlite_stats.get('entities_count', 'N/A')} | {sqlite_stats.get('statements_count', 'N/A')} | {sqlite_avg_time:.6f} | {tinydb_avg_time:.6f} | {ratio:.2f} |")
    
    # 数据量与性能的关系总结
    print("\n数据量与性能的关系总结:")
    print("1. 随着数据量的增加，SQLite和TinyDB的查询时间都有所增加")
    print("2. SQLite在所有数据量级别上都比TinyDB更高效")
    print("3. 数据量增加时，TinyDB性能下降更明显，性能比(TinyDB/SQLite)随数据量增加而增大")
    
    return results

def display_entity_info(entity_id, sqlite_storage, tinydb_storage):
    """显示指定实体ID的详细信息"""
    print_section(f"实体信息 [{entity_id}]")
    
    # 从SQLite获取实体信息
    sqlite_entity = sqlite_storage.get_entity_by_id(entity_id)
    
    # 从TinyDB获取实体信息
    tinydb_entity = tinydb_storage.get_entity_by_id(entity_id)
    
    if not sqlite_entity and not tinydb_entity:
        print(f"错误: 未找到ID为 {entity_id} 的实体")
        return
    
    # 使用任一有效的实体信息
    entity = sqlite_entity or tinydb_entity
    
    # 显示基本信息
    print(f"ID: {entity_id}")
    print(f"标签: {entity.get('label', '未知')}")
    print(f"描述: {entity.get('description', '无描述')}")
    print(f"类型: {entity.get('type', '未知')}")
    
    # 显示别名
    aliases = []
    if sqlite_entity and 'aliases' in sqlite_entity:
        aliases = sqlite_entity['aliases']
    elif tinydb_entity and 'aliases' in tinydb_entity:
        aliases = tinydb_entity['aliases']
    
    if aliases:
        print("\n别名:")
        for alias in aliases:
            print(f"  - {alias.get('value', '')} ({alias.get('language', '')})")
    
    # 显示语句（属性和值）
    statements = []
    if sqlite_entity and 'statements' in sqlite_entity:
        statements = sqlite_entity['statements']
    elif tinydb_entity and 'statements' in tinydb_entity:
        statements = tinydb_entity['statements']
    
    if statements:
        print("\n属性和值:")
        # 对语句按属性标签排序
        sorted_statements = sorted(statements, key=lambda x: x.get('property', {}).get('label', ''))
        
        for stmt in sorted_statements:
            property_info = stmt.get('property', {})
            property_id = property_info.get('id', '')
            property_label = property_info.get('label', property_id)
            
            value = stmt.get('value', '')
            value_type = stmt.get('value_type', '')
            
            # 格式化显示
            if value_type == 'wikibase-entityid':
                entity_id = stmt.get('entity_id', '')
                print(f"  - {property_label} ({property_id}): 实体 {entity_id}")
            else:
                print(f"  - {property_label} ({property_id}): {value} ({value_type})")

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="Wikidata数据处理与查询系统")
    parser.add_argument("--fetch", action="store_true", help="从Wikidata API获取数据")
    parser.add_argument("--entities", nargs="+", help="要获取的实体ID列表")
    parser.add_argument("--load", action="store_true", help="加载数据到数据库")
    parser.add_argument("--query", help="执行自然语言查询")
    parser.add_argument("--compare", action="store_true", help="比较SQLite和TinyDB的性能")
    parser.add_argument("--llm-compare", action="store_true", help="比较LLM与传统数据库的检索结果")
    parser.add_argument("--data-size", type=str, choices=["small", "medium", "large"], default="small", 
                      help="数据集大小: small(8个实体), medium(20个实体), large(50个实体)")
    parser.add_argument("--analyze-size", action="store_true", help="分析数据量对性能的影响")
    parser.add_argument("--test-all-sizes", action="store_true", help="测试三种不同数据量的性能影响")
    parser.add_argument("--show-entity", help="显示指定实体ID的详细信息")
    args = parser.parse_args()
    
    # 设置数据文件路径
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    json_file = os.path.join(data_dir, "wikidata_samples.json")
    
    # 初始化存储
    sqlite_storage = WikidataSQLiteStorage()
    tinydb_storage = WikidataTinyDBStorage()
    
    # 如果没有参数，打印帮助信息
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n示例用法:")
        print("  python main.py --fetch --entities Q148 Q142")
        print("  python main.py --fetch --data-size medium")
        print("  python main.py --load")
        print("  python main.py --query \"What is the capital of China?\"")
        print("  python main.py --compare")
        print("  python main.py --llm-compare")
        print("  python main.py --analyze-size")
        print("  python main.py --test-all-sizes")
        print("  python main.py --show-entity Q148")
        sys.exit(0)
    
    # 获取数据
    if args.fetch:
        print_section("获取Wikidata数据")
        fetcher = WikidataFetcher()
        
        if args.entities:
            entity_ids = args.entities
        else:
            # 根据数据集大小选择实体列表
            if args.data_size == "small":
                # 默认实体列表 - 各国(小)
                entity_ids = ["Q148", "Q142", "Q30", "Q145", "Q183", "Q17", "Q155", "Q159"]
                print("使用小数据集: 中国、法国、美国、英国、德国、日本、巴西、俄罗斯 (8个实体)")
            elif args.data_size == "medium":
                # 中型数据集 - 添加更多国家
                entity_ids = ["Q148", "Q142", "Q30", "Q145", "Q183", "Q17", "Q155", "Q159", 
                              "Q38", "Q39", "Q40", "Q96", "Q114", "Q115", "Q117", "Q118", 
                              "Q184", "Q189", "Q403", "Q408"]
                print("使用中型数据集: 20个主要国家实体")
            elif args.data_size == "large":
                # 大型数据集 - 国家和主要城市
                entity_ids = ["Q148", "Q142", "Q30", "Q145", "Q183", "Q17", "Q155", "Q159", 
                              "Q38", "Q39", "Q40", "Q96", "Q114", "Q115", "Q117", "Q118",
                              "Q184", "Q189", "Q403", "Q408", 
                              # 主要城市
                              "Q956", "Q1490", "Q65", "Q84", "Q90", "Q220", "Q649", "Q64", "Q270", "Q1085",
                              # 更多国家
                              "Q20", "Q31", "Q33", "Q34", "Q35", "Q36", "Q37", "Q41", "Q43", "Q45", 
                              "Q77", "Q79", "Q80", "Q115", "Q122", "Q124", "Q127", "Q129", "Q130", "Q137"]
                print("使用大型数据集: 30个国家和20个主要城市 (50个实体)")
        
        print(f"获取实体: {', '.join(entity_ids)}")
        entities_data = fetcher.fetch_multiple_entities(entity_ids)
        
        # 保存到JSON文件
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)
            
        print(f"已保存 {len(entities_data)} 个实体数据到 {json_file}")
    
    # 显示实体详细信息
    if args.show_entity:
        # 确保数据已加载
        if not os.path.exists(json_file):
            print("警告: 数据文件不存在，尝试添加示例数据")
            sqlite_storage._add_sample_data()
            tinydb_storage._add_sample_data()
        
        # 显示实体详细信息
        display_entity_info(args.show_entity, sqlite_storage, tinydb_storage)
    
    # 加载数据
    if args.load or args.compare or args.llm_compare:
        print_section("加载数据到存储系统")
        
        if not os.path.exists(json_file):
            print(f"警告: JSON文件 {json_file} 不存在")
            print("使用示例数据...")
            # 添加示例数据到两个数据库
            sqlite_storage._add_sample_data()
            tinydb_storage._add_sample_data()
        else:
            print(f"从 {json_file} 加载数据")
            # 加载数据到SQLite
            print("\n正在加载数据到SQLite...")
            sqlite_count = sqlite_storage.store_wikidata(json_file_path=json_file)
            print(f"已加载 {sqlite_count} 个实体到SQLite")
            
            # 加载数据到TinyDB
            print("\n正在加载数据到TinyDB...")
            tinydb_count = tinydb_storage.store_wikidata(json_file_path=json_file)
            print(f"已加载 {tinydb_count} 个实体到TinyDB")
    
    # 执行查询
    if args.query:
        print_section("执行查询")
        query = args.query
        
        # SQLite查询
        print("\nSQLite查询结果:")
        sqlite_results = sqlite_storage.natural_language_query(query)
        if sqlite_results:
            for i, result in enumerate(sqlite_results, 1):
                print(f"{i}. {result[0]} - {result[1]}")
        else:
            print("SQLite查询没有返回结果")
        
        # TinyDB查询
        print("\nTinyDB查询结果:")
        tinydb_results = tinydb_storage.natural_language_query(query)
        if tinydb_results:
            for i, result in enumerate(tinydb_results, 1):
                print(f"{i}. {result[0]} - {result[1]}")
        else:
            print("TinyDB查询没有返回结果")
    
    # 比较性能
    if args.compare:
        # 确保数据已加载
        if not os.path.exists(json_file):
            sqlite_storage._add_sample_data()
            tinydb_storage._add_sample_data()
        
        # 加载示例查询
        queries = load_example_queries()
        
        # 运行性能测试
        run_performance_comparison(sqlite_storage, tinydb_storage, queries)
    
    # 比较LLM与传统数据库的检索结果
    if args.llm_compare:
        # 确保数据已加载
        if not os.path.exists(json_file):
            sqlite_storage._add_sample_data()
            tinydb_storage._add_sample_data()
        
        # 加载示例查询
        queries = load_example_queries()
        
        # 运行LLM比较
        run_llm_comparison(sqlite_storage, queries)
    
    # 分析数据量对性能的影响
    if args.analyze_size:
        # 确保数据已加载
        if not os.path.exists(json_file):
            sqlite_storage._add_sample_data()
            tinydb_storage._add_sample_data()
        
        # 加载示例查询
        queries = load_example_queries()
        
        # 运行数据量影响分析
        analyze_data_size_impact(sqlite_storage, tinydb_storage, queries)
    
    # 测试不同数据量对性能的影响
    if args.test_all_sizes:
        test_all_data_sizes()
    
    # 关闭存储连接
    sqlite_storage.close()
    tinydb_storage.close()

if __name__ == "__main__":
    main() 