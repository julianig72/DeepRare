import requests
from fake_useragent import UserAgent

import time


ua = UserAgent()

# @tool
def PhenobrainAPITool(query):
    """
    Use the Phenobrain API to search for Essamble results.

    Args:
        query (str): The search query.

    Returns:
        str: The search results or an error message.
    """
    # try:
    # if query is list
    
    headers = {'User-Agent': ua.random}
    
    if isinstance(query, str):
        
        url = "https://www.phenobrain.cs.tsinghua.edu.cn/extract-hpo"
        payload = {
            "text": query,
            "method": "HPO/CHPO",
            "threshold": ""
        }

        response = requests.post(url, json=payload, headers=headers)
        task_id = response.json()['TASK_ID']
        
        get_url = f"https://www.phenobrain.cs.tsinghua.edu.cn/query-extract-hpo-result?taskId={task_id}"
        # print(pred_url)
        response = requests.get(get_url, headers=headers)
        if response.json()['state'] == 'FAILURE':
            return
        hpo_list = response.json()['result']['HPO_LIST']
        print("Phenobrain HPO List: ", hpo_list)
        
    else:
        hpo_list = query
    
    
    pred_url = "https://www.phenobrain.cs.tsinghua.edu.cn/predict?model=Ensemble"
    for hpo in hpo_list:
        pred_url += f"&hpoList[]={hpo}"
    pred_url += "&topk=5"
    
    response = requests.get(pred_url, headers=headers)
    if response.status_code != 200:
        print(f"Phenobrain Failed Code: {response.status_code}")
        return ""
    task_id = response.json()['TASK_ID']
    
    get_url = f"https://www.phenobrain.cs.tsinghua.edu.cn/query-predict-result?taskId={task_id}"
    # response = requests.get(get_url, headers=headers)
    # print(response.json())
    
    # 轮询查询任务状态
    while True:
        response = requests.get(get_url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            state = result.get("state", "").lower()  # 获取状态并转为小写

            if state == "success":
                print("Phenobrain Search Success!")
                phenobrain_result = result['result']
                break
            else:
                print("Phenobrain Processing...")
                time.sleep(2)  # 等待2秒后再次查询
        else:
            print(f"Failed Code: {response.status_code}")
            break
        
    disease_list = [i['CODE'] for i in phenobrain_result]
        
    # http://www.phenobrain.cs.tsinghua.edu.cn/disease-list-detail

    # Request Payload:
    # {"diseaseList":["RD:454","RD:8366"]}
    
    disease_url = "https://www.phenobrain.cs.tsinghua.edu.cn/disease-list-detail"
    disease_payload = {
        "diseaseList": disease_list
    }
    
    response = requests.post(disease_url, json=disease_payload, headers=headers)
    
    # {'RD:10439': {'CNS_NAME': '2型 Van Maldergem 综合征（VMLDS2）', 'ENG_NAME': 'VAN MALDERGEM SYNDROME 2; VMLDS2', 'SOURCE_CODES': ['OMIM:615546']}, 'RD:12154': {'ENG_NAME': 'MANDIBULOFACIAL DYSOSTOSIS WITH PTOSIS, AUTOSOMAL DOMINANT', 'SOURCE_CODES': ['OMIM:608257']}, 'RD:3506': {'CNS_NAME': '外侧脑脊膜膨出综合征', 'ENG_NAME': 'Lateral meningocele syndrome', 'SOURCE_CODES': ['OMIM:130720', 'ORPHA:2789']}, 'RD:5266': {'CNS_NAME': '半侧颅面短小征', 'ENG_NAME': 'Goldenhar syndrome', 'SOURCE_CODES': ['OMIM:164210', 'ORPHA:374']}, 'RD:5345': {'CNS_NAME': '身材矮小、耳道闭锁、下颌发育不全和骨骼异常综合征（SAMS）', 'ENG_NAME': 'SHORT STATURE, AUDITORY CANAL ATRESIA, MANDIBULAR HYPOPLASIA, AND SKELETAL ABNORMALITIES; SAMS', 'SOURCE_CODES': ['OMIM:602471', 'ORPHA:397623']}}
    
    results = response.json()
    disease_list_phenobrain = []
    for result in results.values():
        disease_list_phenobrain.append(result['ENG_NAME'] + ' ('+ ' '.join(result['SOURCE_CODES']) + ')')

    return f"Phenobrain gives related diseases about the patient: " + ", ".join(disease_list_phenobrain)




if __name__ == '__main__':
    print(PhenobrainAPITool("Malar flattening, Micrognathia, Preauricular skin tag, Conductive hearing impairment, Atresia of the external auditory canal,"))
