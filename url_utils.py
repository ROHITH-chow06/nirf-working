import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def extract_pdf_links_from_url(url):
    """
    Fetches a URL, parses its HTML content, and extracts all absolute links to PDF files.

    Args:
        url (str): The URL of the webpage to scrape.

    Returns:
        list: A list of absolute URLs pointing to PDF files found on the page.
              Returns an empty list if the URL is invalid or no PDFs are found.
    """
    if not url or not url.startswith(('http://', 'https://')):
        st.error("Invalid URL. Please enter a full URL starting with http:// or https://")
        return []

    try:
        # Using a common user-agent can help avoid being blocked.
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        soup = BeautifulSoup(response.text, 'html.parser')
        pdf_links = []

        # Find all anchor tags that have an 'href' attribute.
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Check if the link ends with .pdf (case-insensitive).
            if href.lower().endswith('.pdf'):
                # Convert relative URLs (like '/docs/report.pdf') to absolute URLs.
                absolute_link = urljoin(url, href)
                pdf_links.append(absolute_link)
        
        # Return a list of unique links to avoid processing the same PDF twice.
        return list(set(pdf_links))

    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
        return []
    except Exception as e:
        st.error(f"An error occurred while parsing the webpage: {e}")
        return []
