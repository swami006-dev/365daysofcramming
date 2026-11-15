from app.prompts import (
    research_prompt,
    writer_prompt,
    critic_prompt,
    image_prompt_template,
    caption_prompt
)
from langchain_groq import ChatGroq

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser
import os 
from dotenv import load_dotenv
load_dotenv()
# ==========================================
# 1. SETUP API KEYS & MODELS (Groq Exclusive)
# ==========================================
GOOGLE_API_KEY=os.getenv('GOOGLE_API_KEY')
GROQ_API_KEY=os.getenv('GROQ_API_KEY')

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is missing")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing")
# Use Groq exclusively for rapid, hilarious iteration
llm_gemini_creative = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=1.1
)

llm_groq_analytical = ChatGroq(
    model="openai/gpt-oss-120b",
    groq_api_key=GROQ_API_KEY,
    temperature=0.3
)
research_chain = research_prompt | llm_groq_analytical | StrOutputParser()
writer_chain   = writer_prompt   | llm_gemini_creative | StrOutputParser()
critic_chain   = critic_prompt   | llm_groq_analytical | StrOutputParser()
image_prompt_chain = image_prompt_template | llm_gemini_creative | StrOutputParser()
caption_chain = caption_prompt | llm_gemini_creative | StrOutputParser()

from app.search_tool import web_search

