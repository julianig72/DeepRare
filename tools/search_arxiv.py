from langchain_community.retrievers import ArxivRetriever
from tools.llm_agent import Summarize_Agent

# ArXiv API
def search_Arxiv(
    query: str = "", 
    max_results: int = 3,
    mini_handler = None
) -> list[dict]:
    """Search ArXiv for papers related to the query

    When searching, you should consider:

    Args:
        query (str): The query to search for
        max_results (int): The maximum number of results to return, default is 3
    """

    # Initialize the ArxivRetriever object
    retriever = ArxivRetriever(
        top_k_results=max_results,
        load_max_docs=max_results,
        load_all_available_meta=True
    )

    # Search for papers related to the query
    related_papers = retriever.invoke(query)

    # Extract the relevant information from the search results
    data_list = []
    for paper in related_papers:

        url = paper.metadata.get('Entry ID', 'No URL')
        
        if paper.page_content:
            content = Summarize_Agent(paper.page_content, mini_handler)
        
        title = paper.metadata.get('Title', paper.metadata.get('title', 'No Title'))
        authors = paper.metadata.get('Authors', paper.metadata.get('authors', 'Unknown Authors'))
        
        if isinstance(authors, list):
            authors = ', '.join(authors)
            
        data_list.append('Title: ' + title + '\n' + 'Url: ' + url + '\n' + 'Summary: ' + content)

    return "\n".join(data_list) + '\n' + "Data source: ArXiv"


if __name__ == "__main__":
    query = "Huntington's disease"
    results = search_Arxiv(query)
    for result in results:
        print(result)