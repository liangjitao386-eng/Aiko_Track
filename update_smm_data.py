#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMM数据自动更新脚本
用于从上海有色金属网(SMM)获取最新价格数据并更新index.html

使用方法:
    python3 update_smm_data.py

数据获取原理:
    SMM提供了一个AJAX接口来获取历史价格数据:
    https://hq.smm.cn/ajax/spot/history/{product_id}/{start_date}/{end_date}
    
    返回JSON格式数据，包含每日的最低价、最高价、均价等信息
"""

import json
import re
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import ssl

# 创建不验证SSL证书的上下文
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# SMM产品ID映射
SMM_PRODUCTS = {
    'silver': '202512220022',        # Topcon正面细栅银浆
    'wafer': '202303220001',         # N型硅片-183mm
    'silicon': '202501060003',       # N型多晶硅
    'cell': '202210280001',          # 单晶Topcon电池片-183mm
    'bcModule': '202506060001',      # BC组件-210R(分布式)
    'topconDomestic': '202310160001', # Topcon组件-182mm(分布式)
    'hjtModule': '202505270001',     # HJT组件-210mm(分布式)
    'topconFob182': '202505060001',  # TOPCon组件-182mm(FOB)
    'topconFob210': '202505060002',  # TOPCon组件-210mm(FOB)
    'percFob': '202507240001',       # 单晶PERC电池片-182mm(FOB)
    'topconIntegrated': '202412190004',  # Topcon183成本指数-一体化
    'topconSemi': '202412190005',    # Topcon183成本指数-半一体化
}

# 产品名称（用于打印）
PRODUCT_NAMES = {
    'silver': 'Topcon正面细栅银浆',
    'wafer': 'N型硅片-183mm',
    'silicon': 'N型多晶硅',
    'cell': '单晶Topcon电池片-183mm',
    'bcModule': 'BC组件-210R(分布式)',
    'topconDomestic': 'Topcon组件-182mm(分布式)',
    'hjtModule': 'HJT组件-210mm(分布式)',
    'topconFob182': 'TOPCon组件-182mm(FOB)',
    'topconFob210': 'TOPCon组件-210mm(FOB)',
    'percFob': '单晶PERC电池片-182mm(FOB)',
    'topconIntegrated': 'Topcon183成本指数-一体化',
    'topconSemi': 'Topcon183成本指数-半一体化',
}


def fetch_smm_data(product_id, start_date, end_date):
    """
    从SMM获取价格数据
    
    Args:
        product_id: SMM产品ID
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
    
    Returns:
        list: 价格数据列表 [{date, price}, ...]
    """
    url = f"https://hq.smm.cn/ajax/spot/history/{product_id}/{start_date}/{end_date}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://hq.smm.cn/'
    }
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if not data.get('status') or data['status'] != 'ok':
                print(f"  警告: API返回状态异常")
                return []
            
            rows = data.get('data', {}).get('rows', [])
            result = []
            
            for row in rows:
                date = row.get('date', '')
                # 使用均价 (avg_price)
                price = row.get('avg_price')
                if price is None:
                    # 如果没有avg_price，尝试计算 (low + high) / 2
                    low = row.get('low_price')
                    high = row.get('high_price')
                    if low is not None and high is not None:
                        price = (float(low) + float(high)) / 2
                
                if date and price is not None:
                    result.append({
                        'date': date,
                        'price': float(price)
                    })
            
            return sorted(result, key=lambda x: x['date'])
            
    except HTTPError as e:
        print(f"  HTTP错误: {e.code}")
        return []
    except URLError as e:
        print(f"  URL错误: {e.reason}")
        return []
    except Exception as e:
        print(f"  获取失败: {e}")
        return []


def format_data_for_js(data):
    """将数据格式化为JavaScript数组字符串"""
    if not data:
        return "[]"
    
    items = []
    for d in data:
        items.append(f'{{date: "{d["date"]}", price: {d["price"]}}}')
    
    # 每行显示2个数据点，便于阅读
    lines = []
    for i in range(0, len(items), 2):
        chunk = items[i:i+2]
        lines.append("                " + ", ".join(chunk))
    
    return "[\n" + ",\n".join(lines) + "\n            ]"


def update_html_file(html_path, smm_data, update_date):
    """更新HTML文件中的smmData"""
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 构建新的smmData JavaScript对象
    smm_data_js = """        // SMM真实数据 ({}获取)
        const smmData = {{
            // 原材料
            silver: {},
            wafer: {},
            silicon: {},
            cell: {},
            // 组件
            bcModule: {},
            topconDomestic: {},
            hjtModule: {},
            topconFob182: {},
            topconFob210: {},
            percFob: {},
            // 成本指数
            topconIntegrated: {},
            topconSemi: {}
        }};""".format(
        update_date,
        format_data_for_js(smm_data.get('silver', [])),
        format_data_for_js(smm_data.get('wafer', [])),
        format_data_for_js(smm_data.get('silicon', [])),
        format_data_for_js(smm_data.get('cell', [])),
        format_data_for_js(smm_data.get('bcModule', [])),
        format_data_for_js(smm_data.get('topconDomestic', [])),
        format_data_for_js(smm_data.get('hjtModule', [])),
        format_data_for_js(smm_data.get('topconFob182', [])),
        format_data_for_js(smm_data.get('topconFob210', [])),
        format_data_for_js(smm_data.get('percFob', [])),
        format_data_for_js(smm_data.get('topconIntegrated', [])),
        format_data_for_js(smm_data.get('topconSemi', []))
    )
    
# 使用正则表达式替换smmData部分
    # 匹配从 "// SMM真实数据" 到 "};" 的整个smmData定义
    pattern = r'// SMM真实数据.*?const smmData = \{.*?\n        \};'
    
    new_content = re.sub(pattern, smm_data_js, content, flags=re.DOTALL)
    
    # 同时更新页面上显示的更新时间
    # 更新 logo-update 中的时间
    new_content = re.sub(
        r'数据更新时间: \d{4}-\d{2}-\d{2}',
        f'数据更新时间: {update_date}',
        new_content
    )
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"\n✅ HTML文件已更新: {html_path}")


def main():
    print("=" * 60)
    print("SMM数据自动更新脚本")
    print("=" * 60)
    
    # 计算日期范围
    today = datetime.now()
    # 大部分产品取最近45天的数据
    start_date = (today - timedelta(days=45)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    # 成本指数是周数据，需要更长时间范围
    cost_start_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    
    print(f"\n日期范围: {start_date} 至 {end_date}")
    print(f"成本指数日期范围: {cost_start_date} 至 {end_date}")
    print("-" * 60)
    
    smm_data = {}
    
    for key, product_id in SMM_PRODUCTS.items():
        name = PRODUCT_NAMES.get(key, key)
        print(f"\n正在获取: {name} (ID: {product_id})")
        
        # 成本指数使用更长的日期范围
        if key in ['topconIntegrated', 'topconSemi']:
            data = fetch_smm_data(product_id, cost_start_date, end_date)
        else:
            data = fetch_smm_data(product_id, start_date, end_date)
        
        if data:
            smm_data[key] = data
            latest = data[-1]
            print(f"  ✓ 获取成功: {len(data)}条数据, 最新: {latest['date']} = {latest['price']}")
        else:
            print(f"  ✗ 获取失败")
    
    print("\n" + "=" * 60)
    
    # 检查是否有足够的数据
    required_keys = ['silver', 'wafer', 'silicon', 'cell']
    missing = [k for k in required_keys if k not in smm_data or not smm_data[k]]
    
    if missing:
        print(f"❌ 缺少必要数据: {missing}")
        print("请检查网络连接或稍后重试")
        sys.exit(1)
    
    # 更新HTML文件
    html_path = '/Users/onekey/.minimax-agent/projects/1/index.html'
    update_date = today.strftime('%Y-%m-%d')
    
    try:
        update_html_file(html_path, smm_data, update_date)
        print("\n✅ 所有数据更新完成!")
        print("\n最新价格摘要:")
        print("-" * 40)
        for key in ['silver', 'wafer', 'topconSemi']:
            if key in smm_data and smm_data[key]:
                latest = smm_data[key][-1]
                name = PRODUCT_NAMES.get(key, key)
                print(f"  {name}: {latest['price']:.4f} ({latest['date']})")
    except Exception as e:
        print(f"❌ 更新HTML失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
