import os
from dotenv import load_dotenv

load_dotenv()

SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')

# Custom search tool using Bright Data's request endpoint structure
def web_search(query: str) -> str:
    """Performs a Google Search using Bright Data's custom request SERP API."""
    import requests
    import urllib.parse
    import json

    if not SERPAPI_API_KEY:
        return "Error: SERPAPI_API_KEY is missing in Colab Secrets or Environment Variables."

    url = "https://api.brightdata.com/request"
    headers = {
        "Authorization": f"Bearer {SERPAPI_API_KEY}",
        "Content-Type": "application/json",
    }

    # Encode query to build a valid google search URL
    encoded_query = urllib.parse.quote_plus(query)
    google_url = f"https://www.google.com/search?q={encoded_query}"

    payload = {
        "zone": "serp_api1",
        "url": google_url,
        "format": "json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
        raw_data = response.json()

        # Bright Data returns the parsed page payload inside the 'body' key
        raw_body = raw_data.get("body", {})
        if isinstance(raw_body, str):
            data = json.loads(raw_body)
        else:
            data = raw_body

        # Parse organic results based on Google SERP JSON schema inside the body
        organic_results = data.get("organic_results", [])
        if not organic_results and "organic" in data:
            organic_results = data.get("organic", [])

        if not organic_results:
            return f"No results found for query: {query}"

        summary = []
        for item in organic_results[:5]:
            title = item.get("title") or item.get("name", "N/A")
            snippet = item.get("snippet") or item.get("description", "N/A")
            link = item.get("link") or item.get("url", "N/A")
            if title or snippet:
                summary.append(f"Title: {title}\nSnippet: {snippet}\nLink: {link}\n")

        if not summary:
            return "Search succeeded but could not extract titled results."

        return "\n".join(summary)
    except Exception as e:
        return f"An error occurred during Bright Data search execution: {str(e)}"

