from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

ua = UserAgent()

# @tool
def HPOSearchTool(args, query: str):
    """
    Use the HPO API to search for Human Phenotype Ontology terms.

    Args:
        query (str): The search query.

    Returns:
        str: The search results or an error message.
    """
    url = f"https://hpo.jax.org/browse/term/{query}"
    print(url)
    headers = {'User-Agent': ua.random}

    options = Options()
    if not args.visualize:
        options.add_argument("--headless") # Run in headless mode (no GUI)
    # options.add_argument("--no-sandbox")  # This is helpful in certain environments (e.g., Docker)
    # options.add_argument("--disable-dev-shm-usage")  # Helps in environments with limited shared memory
    options.add_argument(f'user-agent={headers["User-Agent"]}')

    service = Service(args.chrome_driver)  # Update with the path to your chromedriver
    driver = webdriver.Chrome(service=service, options=options)

    driver.get(url)

    # wait 10s for the page to load
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="mat-tab-content-0-0"]/div/div[1]/div/div[2]/mat-table')))

    # only keep text in <mat-row _ngcontent-wgi-c197="" role="row" class="mat-row cdk-row ng-star-inserted"><mat-cell _ngcontent-wgi-c197="" role="cell" class="mat-cell cdk-cell cdk-column-id mat-column-id ng-star-inserted"><a _ngcontent-wgi-c197="" href="/browse/disease/ORPHA:448237">ORPHA:448237</a></mat-cell><mat-cell _ngcontent-wgi-c197="" role="cell" class="mat-cell cdk-cell cdk-column-name mat-column-name ng-star-inserted">Zika virus disease</mat-cell><!----></mat-row>
    all_paragraph = []
    for i in driver.find_elements(By.XPATH, '//*[@id="mat-tab-content-0-0"]/div/div[1]/div/div[2]/mat-table/mat-row'):
        all_paragraph.append(i.text)

    time.sleep(1)
    driver.save_screenshot("hpo.png")
    driver.quit()

    return all_paragraph



if __name__ == '__main__':
    print(HPOSearchTool("HP:0001225"))
