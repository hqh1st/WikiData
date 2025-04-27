import os
import sqlite3
import json
import re
from tinydb import TinyDB, Query

class WikidataSQLiteStorage:
    """使用SQLite存储Wikidata数据的类"""
    
    def __init__(self):
        """初始化SQLite存储"""
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "wikidata.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
    def _get_db_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_tables(self):
        """创建数据库表"""
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        # 创建实体表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            label TEXT,
            description TEXT,
            type TEXT
        )
        ''')
        
        # 创建别名表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT,
            value TEXT,
            language TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities (id)
        )
        ''')
        
        # 创建属性表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id TEXT PRIMARY KEY,
            label TEXT
        )
        ''')
        
        # 创建语句表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS statements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT,
            property_id TEXT,
            value TEXT,
            entity_value_id TEXT,
            FOREIGN KEY (entity_id) REFERENCES entities (id),
            FOREIGN KEY (property_id) REFERENCES properties (id),
            FOREIGN KEY (entity_value_id) REFERENCES entities (id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_entity(self, entity_data):
        """
        存储单个实体数据
        
        Args:
            entity_data: 包含实体所有信息的字典
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 插入实体
            cursor.execute('''
            INSERT OR REPLACE INTO entities (id, label, description, type)
            VALUES (?, ?, ?, ?)
            ''', (
                entity_data.get('entity_id', ''),
                entity_data.get('label', ''),
                entity_data.get('description', ''),
                entity_data.get('type', '')
            ))
            
            # 插入别名
            if 'aliases' in entity_data and entity_data['aliases']:
                # 先删除现有别名
                cursor.execute('DELETE FROM aliases WHERE entity_id = ?', (entity_data['entity_id'],))
                
                # 插入新别名
                for alias in entity_data['aliases']:
                    cursor.execute('''
                    INSERT INTO aliases (entity_id, value, language)
                    VALUES (?, ?, ?)
                    ''', (
                        entity_data['entity_id'],
                        alias.get('value', ''),
                        alias.get('language', '')
                    ))
            
            # 插入语句
            if 'statements' in entity_data and entity_data['statements']:
                # 先删除现有语句
                cursor.execute('DELETE FROM statements WHERE entity_id = ?', (entity_data['entity_id'],))
                
                for statement in entity_data['statements']:
                    # 确保属性存在
                    if 'property' in statement:
                        property_id = statement['property'].get('property_id', '')
                        property_label = statement['property'].get('label', '')
                        
                        cursor.execute('''
                        INSERT OR REPLACE INTO properties (id, label)
                        VALUES (?, ?)
                        ''', (property_id, property_label))
                        
                        # 插入语句
                        entity_value_id = statement.get('entity_id', None)
                        
                        cursor.execute('''
                        INSERT INTO statements (entity_id, property_id, value, entity_value_id)
                        VALUES (?, ?, ?, ?)
                        ''', (
                            entity_data['entity_id'],
                            property_id,
                            statement.get('value', ''),
                            entity_value_id
                        ))
            
            conn.commit()
            
        except Exception as e:
            print(f"存储实体 {entity_data.get('entity_id', 'unknown')} 时出错: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def store_entities(self, entities_data):
        """
        批量存储多个实体数据
        
        Args:
            entities_data: 包含多个实体数据的列表或字典
        """
        # 确保数据库表存在
        self.create_tables()
        
        # 如果输入是字典，转换为列表
        if isinstance(entities_data, dict):
            entities_data = list(entities_data.values())
        
        # 批量存储实体
        for entity_data in entities_data:
            self.store_entity(entity_data)
    
    def load_from_json(self, json_file):
        """
        从JSON文件加载数据到SQLite
        
        Args:
            json_file: JSON文件路径
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                entities_data = json.load(f)
            
            self.store_entities(entities_data)
            print(f"成功从 {json_file} 加载 {len(entities_data)} 个实体到SQLite数据库")
            
        except Exception as e:
            print(f"从JSON加载数据到SQLite时出错: {e}")
    
    def get_entity_by_id(self, entity_id):
        """
        根据实体ID获取完整的实体信息
        
        Args:
            entity_id: 要获取的实体ID
            
        Returns:
            dict: 包含实体所有信息的字典，如果未找到则返回None
        """
        # 连接数据库
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 获取实体基本信息
            cursor.execute("""
                SELECT id, label, description, type
                FROM entities
                WHERE id = ?
            """, (entity_id,))
            
            entity_row = cursor.fetchone()
            if not entity_row:
                return None
                
            entity = {
                'id': entity_row[0],
                'label': entity_row[1],
                'description': entity_row[2],
                'type': entity_row[3],
                'aliases': [],
                'statements': []
            }
            
            # 获取实体的别名
            cursor.execute("""
                SELECT value, language
                FROM aliases
                WHERE entity_id = ?
            """, (entity_id,))
            
            aliases = cursor.fetchall()
            for alias in aliases:
                entity['aliases'].append({
                    'value': alias[0],
                    'language': alias[1]
                })
            
            # 获取实体的语句/属性
            cursor.execute("""
                SELECT s.id, p.id, p.label, s.value, s.entity_value_id
                FROM statements s
                JOIN properties p ON s.property_id = p.id
                WHERE s.entity_id = ?
            """, (entity_id,))
            
            statements = cursor.fetchall()
            for stmt in statements:
                statement = {
                    'id': stmt[0],
                    'property': {
                        'id': stmt[1],
                        'label': stmt[2]
                    },
                    'value': stmt[3],
                }
                
                # 如果引用了另一个实体，添加实体ID
                if stmt[4]:
                    statement['entity_id'] = stmt[4]
                    
                entity['statements'].append(statement)
                
            return entity
                
        except Exception as e:
            print(f"获取实体 {entity_id} 时出错: {e}")
            return None
        finally:
            conn.close()
    
    def search_entities(self, query, limit=10):
        """
        搜索实体
        
        Args:
            query: 搜索关键词
            limit: 最大结果数
            
        Returns:
            list: 符合条件的实体列表
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 在实体标签、描述和别名中搜索
            cursor.execute("""
                SELECT DISTINCT e.id, e.label, e.description
                FROM entities e
                LEFT JOIN aliases a ON e.id = a.entity_id
                WHERE e.label LIKE ? OR e.description LIKE ? OR a.value LIKE ?
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row[0],
                    'label': row[1],
                    'description': row[2]
                })
                
            return results
                
        except Exception as e:
            print(f"搜索实体时出错: {e}")
            return []
        finally:
            conn.close()
    
    def _add_sample_data(self):
        """添加示例数据，用于测试"""
        sample_data = {
            "Q148": {
                "entity_id": "Q148",
                "label": "中国",
                "description": "亚洲东部国家",
                "type": "country",
                "aliases": [
                    {"value": "People's Republic of China", "language": "en"},
                    {"value": "PRC", "language": "en"},
                    {"value": "中华人民共和国", "language": "zh"}
                ],
                "statements": [
                    {
                        "property": {"property_id": "P36", "label": "首都"},
                        "entity_id": "Q956",
                        "value": "北京"
                    },
                    {
                        "property": {"property_id": "P37", "label": "官方语言"},
                        "value": "汉语"
                    },
                    {
                        "property": {"property_id": "P1082", "label": "人口"},
                        "value": "14亿"
                    }
                ]
            },
            "Q956": {
                "entity_id": "Q956",
                "label": "北京",
                "description": "中华人民共和国首都",
                "type": "city",
                "aliases": [
                    {"value": "Beijing", "language": "en"},
                    {"value": "Peking", "language": "en"}
                ],
                "statements": [
                    {
                        "property": {"property_id": "P17", "label": "国家"},
                        "entity_id": "Q148",
                        "value": "中国"
                    },
                    {
                        "property": {"property_id": "P1082", "label": "人口"},
                        "value": "2154万"
                    }
                ]
            }
        }
        
        self.store_entities(sample_data)
        print("已添加示例数据到SQLite数据库")

class WikidataTinyDBStorage:
    """使用TinyDB存储Wikidata数据的类"""
    
    def __init__(self):
        """初始化TinyDB存储"""
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "wikidata.json")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.db = TinyDB(self.db_path, encoding='utf-8')
        self.entities = self.db.table('entities')
    
    def store_entity(self, entity_data):
        """
        存储单个实体数据
        
        Args:
            entity_data: 包含实体所有信息的字典
        """
        # 使用entity_id作为文档ID
        entity_id = entity_data.get('entity_id')
        if not entity_id:
            print("警告: 实体数据缺少entity_id字段")
            return
        
        # 查找是否已存在相同ID的实体
        Entity = Query()
        existing = self.entities.get(Entity.entity_id == entity_id)
        
        if existing:
            # 更新现有实体
            self.entities.update(entity_data, Entity.entity_id == entity_id)
        else:
            # 添加新实体
            self.entities.insert(entity_data)
    
    def store_entities(self, entities_data):
        """
        批量存储多个实体数据
        
        Args:
            entities_data: 包含多个实体数据的列表或字典
        """
        # 如果输入是字典，转换为列表
        if isinstance(entities_data, dict):
            entities_data = list(entities_data.values())
        
        # 批量存储实体
        for entity_data in entities_data:
            self.store_entity(entity_data)
    
    def load_from_json(self, json_file):
        """
        从JSON文件加载数据到TinyDB
        
        Args:
            json_file: JSON文件路径
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                entities_data = json.load(f)
            
            self.store_entities(entities_data)
            print(f"成功从 {json_file} 加载 {len(entities_data)} 个实体到TinyDB数据库")
            
        except Exception as e:
            print(f"从JSON加载数据到TinyDB时出错: {e}")
    
    def get_entity_by_id(self, entity_id):
        """
        根据实体ID获取完整的实体信息
        
        Args:
            entity_id: 要获取的实体ID
            
        Returns:
            dict: 包含实体所有信息的字典，如果未找到则返回None
        """
        Entity = Query()
        return self.entities.get(Entity.entity_id == entity_id)
    
    def search_entities(self, query, limit=10):
        """
        搜索实体
        
        Args:
            query: 搜索关键词
            limit: 最大结果数
            
        Returns:
            list: 符合条件的实体列表
        """
        Entity = Query()
        
        # 搜索逻辑，匹配标签或描述中包含查询词的实体
        results = self.entities.search(
            (Entity.label.search(query, flags=re.IGNORECASE)) | 
            (Entity.description.search(query, flags=re.IGNORECASE))
        )
        
        # 限制结果数量
        results = results[:limit]
        
        # 只返回必要字段
        return [
            {
                'id': result.get('entity_id'),
                'label': result.get('label'),
                'description': result.get('description')
            }
            for result in results
        ]
    
    def _add_sample_data(self):
        """添加示例数据，用于测试"""
        # 清空现有数据
        self.entities.truncate()
        
        sample_data = {
            "Q148": {
                "entity_id": "Q148",
                "label": "中国",
                "description": "亚洲东部国家",
                "type": "country",
                "aliases": [
                    {"value": "People's Republic of China", "language": "en"},
                    {"value": "PRC", "language": "en"},
                    {"value": "中华人民共和国", "language": "zh"}
                ],
                "statements": [
                    {
                        "property": {"property_id": "P36", "label": "首都"},
                        "entity_id": "Q956",
                        "value": "北京"
                    },
                    {
                        "property": {"property_id": "P37", "label": "官方语言"},
                        "value": "汉语"
                    },
                    {
                        "property": {"property_id": "P1082", "label": "人口"},
                        "value": "14亿"
                    }
                ]
            },
            "Q956": {
                "entity_id": "Q956",
                "label": "北京",
                "description": "中华人民共和国首都",
                "type": "city",
                "aliases": [
                    {"value": "Beijing", "language": "en"},
                    {"value": "Peking", "language": "en"}
                ],
                "statements": [
                    {
                        "property": {"property_id": "P17", "label": "国家"},
                        "entity_id": "Q148",
                        "value": "中国"
                    },
                    {
                        "property": {"property_id": "P1082", "label": "人口"},
                        "value": "2154万"
                    }
                ]
            }
        }
        
        self.store_entities(sample_data)
        print("已添加示例数据到TinyDB数据库") 