from langchain_community.retrievers import WikipediaRetriever
from tools.llm_agent import Summarize_Agent

# Wikipedia API
def search_Wiki(
    query: str = "", 
    max_results: int = 3,
    mini_handler = None
) -> list[dict]:
    """Search Wikipedia for articles related to the query

    When searching, you should consider:

    Args:
        query (str): The query to search for
        max_results (int): The maximum number of results to return, default is 3
    """

    # Initialize the WikipediaRetriever object
    retriever = WikipediaRetriever(
        top_k_results=max_results,
        lang="en"
    )

    # Search for articles related to the query
    related_articles = retriever.invoke(query)
    
    if not related_articles:
        return ''

    # Extract the relevant information from the search results
    data_list = []
    for article in related_articles:
        url = "https://en.wikipedia.org/wiki/" + article.metadata.get('title', 'No URL')

        if article.page_content:
            content = Summarize_Agent(article.page_content, mini_handler)
        
        title = article.metadata.get('title', 'No Title')
        data_list.append('Title: ' + title + '\n' + \
            '             Url: ' + url + '\n' +
                        'Summary: ' + content)

    return '\n'.join(data_list) + '\n' + "Data source: Wikipedia"

if __name__ == "__main__":
    query = "Huntington's disease"
    results = search_Wiki(query)
    print(results)