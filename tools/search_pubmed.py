from langchain_community.retrievers import PubMedRetriever
from tools.llm_agent import Summarize_Agent

# PubMed API
# @tool
def search_PubMed(
    query: str = "", 
    max_results: int = 3,
    mini_handler = None
) -> list[dict]:
    """Search PubMed for articles related to the query

    When searching, you should consider:

    1. Search Fields:
    - Title [ti]
    - Abstract [ab]
    - Author [au]
    - Journal [jour]
    - MeSH Terms [mesh]
    - Publication Date [dp]
    - DOI [doi]

    2. Boolean Operators:
    - AND
    - OR 
    - NOT
    - Use parentheses () for complex queries

    3. Search Syntax Examples:
    - Basic: diabetes mellitus
    - Field-specific: glucose[ti] AND insulin[mesh]
    - Date range: (2020[dp]:2024[dp])
    - Author search: Smith J[au]
    - Complex: ((diabetes mellitus[mesh] OR hyperglycemia[ti]) AND treatment[ti]) NOT type 1[tiab]

    Args:
        query (str): The query to search for
        max_results (int): The maximum number of results to return, default is 50
    """

    # Initialize the PubMedRetriever object
    retriever = PubMedRetriever(
        top_k_results=max_results,
    )

    # Search for articles related to the query
    related_articles = retriever.invoke(query)

    # Extract the relevant information from the search results
    data_list = []
    for article in related_articles:
        # ipdb.set_trace()
        url = "https://pubmed.ncbi.nlm.nih.gov/" + article.metadata.get('uid', '')
        if article.page_content:
            content = Summarize_Agent(article.page_content, mini_handler)
        if type(article.metadata.get('Title', 'No Title')) == dict:
            data_list.append('Title: ' + article.metadata.get('Title', 'No Title')['#text']+ '\n ' + "Url: "+ url + '\n ' + 'Summary: ' + content)
            continue

        data_list.append('Title: ' + article.metadata.get('Title', 'No Title') + '\n '+ "Url: "+ url  + '\n ' + 'Summary: ' + content)

    return "\n".join(data_list) + '\n' + "Data source: PubMed"



if __name__ == "__main__":
    # conditions = 'COVID-19'
    # interventions = 'Vaccine'
    # res = search_ClinicalTrials(conditions=conditions, interventions=interventions)
    # print(res)

    query = 'Malar flattening' #Preauricular skin tag ',Conductive hearing impairment,Atresia of the external auditory canal,Choanal atresia,Myopia,Microtia,Aplasia/Hypoplasia of the middle ear,Proximal placement of thumb,Increased nuchal translucency,Mild global developmental delay,Primary microcephaly,Gastrostomy tube feeding in infancy'
    res = search_PubMed(query=query)
    print(res)