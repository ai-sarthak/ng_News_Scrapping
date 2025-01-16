import nltk
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Download NLTK data (if not already downloaded)
nltk.download('punkt')

# Function to limit text based on word count
def limit_text_by_word_count(text, max_words):
    words = nltk.word_tokenize(text)
    if len(words) > max_words:
        return ' '.join(words[:max_words])
    return text

# Your prompt template
template = """You are an expert in analyzing company news from the news provided.
    Please perform analysis on the provided news and return the following analysis:
    1) Sentiment of News
    2) Intent of News for example : "new product launch" , "leadership change" , "collaboration with company", "new tenders" etc.
    3) Readiness or willingness of the company to involve in sales conversation. Answer in yes or no.
    
    ### News to perform analysis on:
    {text}

    ---

    ### Please provide the extracted information in highly structured format like: ['Sentiment','Intent','Ready']. just provide answers in one to two words for each in provided format only.+dont include further explanation or introductory part in chat.
    """

# Load environment variables for API keys
load_dotenv()

api_key1 = os.getenv('API_KEY1')
api_key2 = os.getenv('API_KEY2')
api_key3 = os.getenv('API_KEY3')
API_Vault = [api_key1, api_key2, api_key3]

# Initialize counter for sequential key selection
api_key_index = 0

# Function to get the next API key in sequence
def get_next_api_key():
    global api_key_index
    api_key = API_Vault[api_key_index]
    api_key_index = (api_key_index + 1) % len(API_Vault)
    return api_key

# Configure the API client with the current API key
genai.configure(api_key=get_next_api_key())

# Create the LLM model
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

def get_analysis(text):
    """Perform the analysis on the provided text using the LLM API."""
    # Limit the input text to a maximum of 50,000 words
    max_input_words = 50000
    limited_text = limit_text_by_word_count(text, max_input_words)

    # Configure with the next API key in sequence for each request
    genai.configure(api_key=get_next_api_key())

    # Start a new chat session
    chat_session = model.start_chat(
        history=[]
    )

    # Use the limited text in the prompt
    prompt_text = template.format(text=limited_text)
    
    # Send the prompt to the model (this is a synchronous call)
    response = chat_session.send_message(prompt_text)

    # Return the analysis result
    return response.text
