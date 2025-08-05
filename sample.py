import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_pdf_links_from_url(url: str, timeout: int = 15) -> list:
    """
    Extracts all PDF URLs from a given NIRF webpage.

    Args:
        url (str): The webpage URL to scrape PDF links from.
        timeout (int): Timeout for the HTTP request.

    Returns:
        List[str]: A list of full PDF URLs.
    
    Raises:
        requests.exceptions.RequestException: If the request fails.
        ValueError: If no PDF links are found.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Failed to fetch URL: {e}")

    soup = BeautifulSoup(response.content, "html.parser")
    pdf_links = [
        urljoin(url, a["href"])
        for a in soup.find_all("a", href=True)
        if a["href"].lower().endswith(".pdf")
    ]

    if not pdf_links:
        raise ValueError("No PDF links found on the page.")

    return pdf_links