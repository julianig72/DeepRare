import os
import requests
import time
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from duckduckgo_search import DDGS

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from tools.page_fetch import fetch_page_content_and_summarize
os.environ['DISPLAY'] = ':99'

ua = UserAgent()


def BingSearchTool(args, query: str, mini_handler, read_content: bool = True, return_num: int = 5, screenshot: bool = False):
    """
    Use Selenium to get search results from Bing. Optionally, fetch content from the links and summarize.

    Args:
        args: Namespace: The argument namespace containing configurations.
        query (str): The search query.
        mini_handler: The LLM handler for summarization.
        read_content (bool): Whether to read the content of each link.
        return_num (int): The number of search results to return.
        screenshot (bool): Whether to take a screenshot.

    Returns:
        str: Search results or an error message.
    """
    driver = None
    results = []


    url = f"https://www.bing.com/search?q={query}"

    user_agent = ua.random

    options = Options()
    if not getattr(args, 'visualize', False):
        options.add_argument("--headless")
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1550,1000")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--incognito")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--blink-settings=imagesEnabled=false")  

    service = Service(args.chrome_driver)
    driver = webdriver.Chrome(service=service, options=options)

    driver.get(url)

    time.sleep(5)

    driver.set_window_size(1280, 800)

    if screenshot:
        driver.save_screenshot("bing.png")

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    search_results = soup.find_all("li", class_="b_algo")
    success_count = 0

    for result in search_results:
        title_elem = result.find("h2")
        if not title_elem:
            continue

        title = title_elem.get_text().strip()

        link_elem = result.find("a")
        if not link_elem or not link_elem.has_attr("href"):
            continue

        link = link_elem["href"]

        if not (link.startswith('http://') or link.startswith('https://')):
            continue

        if read_content:
            try:
                page_content = fetch_page_content_and_summarize(args, link, mini_handler, False)
                results.append(f"Title: {title}\nURL: {link}\n\n Content:{page_content}")
            except:
                continue
        else:
            snippet_elem = result.find("p")
            snippet = snippet_elem.get_text().strip() if snippet_elem else "No snippet available."
            results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}")

        success_count += 1
        if success_count >= return_num:
            break


    if results:
        return "\n\n-----------------------\n\n".join(results)
    else:
        return "No results found on Bing."


# @tool
def GoogleSearchTool(
    args,
    query: str,
    mini_handler,
    read_content: bool = True,
    return_num: int = 5,
    screenshot: bool = False,
    start: int = 1  
):
    """
    Use API to get search results from Google. Optionally, fetch content from the links and summarize.

    Args:
        query (str): The search query.
        mini_handler: The LLM handler for summarization.
        read_content (bool): Whether to read the content of each link.
        return_num (int): Number of results to return (1–10).
        screenshot (bool): Whether to take a screenshot.
        start (int): 1-based index of the first result to return (e.g., 11 for items 11–20).

    Returns:
        str: The search results or an error message.
    """

    # Basic validation
    if not isinstance(query, str) or not query.strip():
        return "Error: query must be a non-empty string."
    if not getattr(args, "google_api", None):
        return "Error: missing args.google_api (API key)."
    if not getattr(args, "search_engine_id", None):
        return "Error: missing args.search_engine_id (CSE cx)."
    try:
        return_num = int(return_num)
        start = int(start)
    except Exception:
        return "Error: return_num and start must be integers."

    if not (1 <= return_num <= 10):
        return "Error: return_num must be between 1 and 10."
    if start < 1 or start > 91:  # The official limit is usually around 100, but we conservatively use 91 to ensure start+num-1 <= 100
        return "Error: start must be between 1 and 91."

    try:
        api_key = args.google_api
        search_engine_id = args.search_engine_id

        url = 'https://www.googleapis.com/customsearch/v1'
        params = {
            'key': api_key,
            'cx': search_engine_id,
            'q': query.strip(),
            'num': return_num,
            'start': start
        }


        response = requests.get(url, params=params, timeout=20)

        if response.status_code != 200:
            try:
                err = response.json()
            except Exception:
                err = response.text
            return f"Error: {response.status_code}\n{err}"

        results_json = response.json()
        items = results_json.get('items', [])
        if not items:
            return "No results found."

        search_results = []
        for i, item in enumerate(items):
            title = item.get('title')
            link = item.get('link')
            snippet = item.get('snippet', 'No snippet available.')
            # print(f"Result {i}: {title}\nSnippet: {snippet}\nURL: {link}\n")
            # ipdb.set_trace()
            if read_content and link:
                try:
                    page_content = fetch_page_content_and_summarize(args, link, mini_handler, False)
                    search_results.append(page_content)
                except Exception as e:
                    search_results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}")
                    
                # print(f"Fetched and summarized content from: {link}\n")
            else:
                search_results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}")

        return "\n\n".join(search_results)

    except requests.RequestException as re:
        return f"Network error during Google search: {re}"
    except Exception as e:
        return f"Error during Google search: {e}"

# @tool
def DuckDuckGoSearchTool(args, query: str, read_content: bool = True, return_num: int = 5, mini_handler=None):
    """
    Use the DDGS (DuckDuckGo Search) to get search results. Optionally, fetch content from the links and summarize.

    Args:
        query (str): The search query.
        read_content (bool): Whether to read the content of each link.
        return_num (int): The number of search results to return.
        mini_handler: The LLM handler for summarization.

    Returns:
        str: The search results or an error message.
    """

    try:
        # Perform a DuckDuckGo search using DDGS
        ddgs = DDGS()
        results = ddgs.text(query, max_results = return_num)  # Modify max_results if needed

        # If no results found
        if not results:
            return "No results found on DuckDuckGo."


        search_results = []

        for result in results:
            title = result.get('title')
            snippet = result.get('snippet', 'No snippet available.')
            link = result.get('link')


            # If read_content is True, fetch and parse the content of the linked page
            if read_content:
                page_content = fetch_page_content_and_summarize(args, link, mini_handler, False)
                search_results.append(page_content)
            else:
                search_results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}")

        return "\n\n".join(search_results)

    except Exception as e:
        return f"Error during DuckDuckGo search: {e}"

if __name__ == "__main__":
    # Test with a Bing search
    import argparse
    parser = argparse.ArgumentParser(description="Search Tool")
    parser.add_argument('--chrome_driver', type=str, default="/usr/local/bin/chromedriver", help='Path to ChromeDriver')
    parser.add_argument('--visualize', action='store_true', help='Visualize the search results')
    args = parser.parse_args()
    # Test Bing search
    result = GoogleSearchTool(args, "Genetic disease", read_content=True, return_num=5, screenshot=False)
    print(result)



    
