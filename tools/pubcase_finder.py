import requests
import pandas as pd
import os
import time
from fake_useragent import UserAgent

ua = UserAgent()

def PubCaseFinderSearchTool(args, query):
    """
    Use API to search for disease case information on PubCaseFinder.

    Args:
        query (str or list): The search query (e.g., HPO IDs like "HP:0000347" or disease name).
    
    Returns:
        str: The search results or an error message.
    """
    import traceback

    if isinstance(query, str):
        query = [query]
    
    # 处理HPO ID格式
    processed_query = []
    for q in query:
        if q.startswith('HP:'):
            processed_query.append(q)
        else:
            # 如果不是HPO ID，假设是HPO ID但缺少前缀
            if q.isdigit() or (len(q) == 7 and q.isdigit()):
                processed_query.append(f'HP:{q}')
            else:
                processed_query.append(q)
    
    # 构建API URL
    hpo_ids = ','.join(processed_query)
    api_url = f"https://pubcasefinder.dbcls.jp/api/pcf_get_ranked_list?target=orphanet&format=tsv&hpo_id={hpo_ids}"
    
    print(f"[LOG] API URL: {api_url}")
    
    # 创建下载文件夹
    download_folder = os.path.join(args.results_folder, 'tmp')
    download_folder = os.path.abspath(download_folder)
    
    if not os.path.isdir(download_folder):
        os.makedirs(download_folder, exist_ok=True)
    
    # 生成唯一文件名
    query_clean = [q.replace('HP:', '') if q.startswith('HP:') else q for q in processed_query]
    query_str = ''.join(query_clean)
    
    if len(query_str) > 200:
        unique_filename = f"pubcasefinder_{query_str[:200]}.tsv"
    else:
        unique_filename = f"pubcasefinder_{query_str}.tsv"
    
    target_file_path = os.path.join(download_folder, unique_filename)
    
    # 检查文件是否已存在
    if os.path.exists(target_file_path):
        print(f'[LOG] File already exists, reading: {unique_filename}')
        try:
            results = pd.read_csv(target_file_path, sep='\t')
            if len(results) > 0:
                results = results.head(5)
                diag = results['Disease_Name'].to_list()
                return f"PubCaseFinder gives related diseases about the patient: " + ", ".join(diag)
            else:
                print("[LOG] Existing file is empty, re-downloading...")
        except Exception as e:
            print(f"[LOG] Error reading existing file: {e}, re-downloading...")
    

    # 设置请求头
    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/tab-separated-values,*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    print("[LOG] Sending API request...")
    
    # 发送请求
    response = requests.get(api_url, headers=headers, timeout=60)
    response.raise_for_status()
    
    print(f"[LOG] API response status: {response.status_code}")
    print(f"[LOG] Response content type: {response.headers.get('content-type', 'unknown')}")
    
    # 检查响应内容
    if response.status_code == 200:
        content = response.text
        
        # 检查是否为空或错误响应
        if not content or content.strip() == "":
            return "PubCaseFinder: No results found for the given HPO IDs."
        
        # 检查是否包含错误信息
        if "error" in content.lower() or "not found" in content.lower():
            return "PubCaseFinder: No results found for the given HPO IDs."
        
        # 保存文件
        with open(target_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[LOG] File saved successfully: {target_file_path}")
        
        # 读取并解析结果

        results = pd.read_csv(target_file_path, sep='\t')
        
        if len(results) == 0:
            return "PubCaseFinder: No results found for the given HPO IDs."
        
        print(f"[LOG] Successfully loaded {len(results)} results")
        
        # 取前5个结果
        results = results.head(5)
        
        # 提取疾病名称
        if 'Disease_Name' in results.columns:
            diag = results['Disease_Name'].to_list()
        elif 'disease_name' in results.columns:
            diag = results['disease_name'].to_list()
        else:
            # 查看所有列名，寻找可能的疾病名称列
            print(f"[LOG] Available columns: {list(results.columns)}")
            possible_disease_columns = [col for col in results.columns 
                                        if 'disease' in col.lower() or 'name' in col.lower()]
            if possible_disease_columns:
                diag = results[possible_disease_columns[0]].to_list()
            else:
                # 如果找不到合适的列，返回所有列的第一列
                diag = results.iloc[:, 0].to_list()
        
        # 过滤掉空值和NaN
        diag = [str(d) for d in diag if pd.notna(d) and str(d).strip() != '']
        
        if not diag:
            return "PubCaseFinder: Results found but no valid disease names extracted."
        
        print(f"[LOG] Successfully extracted {len(diag)} disease names")
        return f"PubCaseFinder gives related diseases about the patient: " + ", ".join(diag)
            
    
    


# Example usage
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='PubCaseFinder API Search Tool')
    parser.add_argument('--results_folder', type=str, default='result_new/HMS', 
                       help='Path to the results folder')
    args = parser.parse_args()
    
    # Test with HPO IDs
    test_queries = [
        ["HP:0000347", "HP:0000384", "HP:0000405"],
        ["HP:0002089", "HP:0001998"],
        ["HP:0000347"]
    ]
    
    for query in test_queries:
        print(f"\n[TEST] Testing with query: {query}")
        result = PubCaseFinderSearchTool(args, query)
        print(f"[RESULT] {result}")
        print("-" * 80)