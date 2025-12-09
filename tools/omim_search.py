import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup

ua = UserAgent()

def OMIMSearchTool(query: str):
    """
    Use the OMIM Website to search for Essamble results.

    Args:
        query (str): The search query.

    Returns:
        str: The search results or an error message.
    """
    # 代理设置
    proxyAddr = "tun-sbftjg.qg.net:12749"
    authKey = "15944DB1"
    password = "6D5A0323C226"
    
    proxyUrl = "http://%(user)s:%(password)s@%(server)s" % {
        "user": authKey,
        "password": password,
        "server": proxyAddr,
    }
    
    proxies = {
        "http": proxyUrl,
        "https": proxyUrl,
    }

    # 输入 OMIM ID
    if query.startswith('OMIM:'):
        query = query.split(':')[1]

    url = f'https://www.omim.org/entry/{query}'

    # use requests to get the page with proxy
    response = requests.get(url, 
                            headers={'User-Agent': ua.random},
                            proxies=proxies,
                            timeout=10)
    response.raise_for_status()
    all_paragraph = response.text

    # use BeautifulSoup to parse the page
    soup = BeautifulSoup(all_paragraph, 'html.parser')
    all_paragraph = soup.find_all('p')

    # only keep half of the paragraphs
    all_paragraph = all_paragraph[:len(all_paragraph)//2]

    all_paragraph = [i.text for i in all_paragraph]
    all_paragraph = ' '.join(all_paragraph).replace('\n', ' ').replace('\t', ' ').replace('  ', ' ')

    
    return all_paragraph + "\n"\
        "Database Link: https://www.omim.org/entry/{query} \n" + \
        "Data source: OMIM"


if __name__ == '__main__':
    for i in range(10):
        result = OMIMSearchTool('OMIM:600802')
        print(result[:100])