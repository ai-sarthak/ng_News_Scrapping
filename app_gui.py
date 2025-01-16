import asyncio
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time
import analyser
from webdriver_manager.chrome import ChromeDriverManager  # Using webdriver-manager

# Sidebar Input for API Keys
st.sidebar.header("Please Add Your API Keys")
num_api_keys = st.sidebar.number_input("How many API keys?", min_value=1, max_value=5, step=1, value=1)
api_keys = [st.sidebar.text_input(f"API Key {i+1}", type="password") for i in range(num_api_keys)]
API_Vault = api_keys

# Sidebar Input for Async Semaphore and Max Websites
async_semaphore = st.sidebar.number_input("Set Async Semaphore", min_value=1, max_value=10, step=1, value=4)
max_websites = st.sidebar.number_input("Max Websites to Scrape", min_value=1, max_value=20, step=1, value=5)

# Headless Chrome Setup for Selenium
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--remote-debugging-port=9222")

# Use WebDriver Manager to automatically handle the ChromeDriver version
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# Function to perform LLM analysis asynchronously with a semaphore
async def analysis_from_llm(flag,company,news_extracted, api_semaphore):
    """Perform LLM analysis asynchronously while controlling access to API keys using a semaphore."""
    if flag == 0:
        st.write(f"Analyzing with LLM company: {company}")
    
    async with api_semaphore:
        analysis = analyser.get_analysis(news_extracted)
        return analysis

# Function to extract news from Google News and process it asynchronously
async def extract_news(company, url, linkedin_url, max_websites, api_semaphore):
    """Extract news data from Google News search results and open news links to extract full content asynchronously."""
    driver.get(f'https://www.google.com/search?q={company}&tbm=nws')
    st.write(f"Processing company: {company} with URL: {url}")
    flag = 0
    news_items = []
    news_results = driver.find_elements(By.CSS_SELECTOR, 'div#rso > div > div > div > div')

    count = 0
    for news_div in news_results:
        if count >= max_websites:  # Stop if we have reached the limit
            break
        
        try:
            news_item = {}
            news_item['Link'] = news_div.find_element(By.TAG_NAME, 'a').get_attribute('href')
            divs_inside_news = news_div.find_elements(By.CSS_SELECTOR, 'a>div>div>div')

            if len(divs_inside_news) >= 4:
                news_item['Domain'] = divs_inside_news[1].text
                news_item['Title'] = divs_inside_news[2].text
                news_item['Description'] = divs_inside_news[3].text
                news_item['Date'] = divs_inside_news[4].text

                news_link = news_item['Link']
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(news_link)
                time.sleep(2)

                try:
                    article_content = driver.find_element(By.TAG_NAME, 'body').text 
                    news_item['Full Content'] = article_content

                    combined_text = news_item['Title'] + ' ' + article_content
                    analysis = await analysis_from_llm(flag,company,combined_text, api_semaphore)
                    flag = 1
                    news_item['Analysis'] = analysis

                except Exception as e:
                    print(f"Error scraping news content: {e}")
                    news_item['Full Content'] = 'N/A'

                driver.close()  
                driver.switch_to.window(driver.window_handles[0])

                news_item['Company'] = company
                news_item['Website'] = url  
                news_item['Person LinkedIn Url'] = linkedin_url  # Add LinkedIn URL to the news item

                news_items.append(news_item)

                count += 1  # Increment the counter after successfully processing a news item

        except Exception as e:
            print(f"Error processing news item: {e}")

    return news_items

# Function to save data to Excel
def save_to_excel(data, filename):
    """Save the extracted news data to an Excel file."""
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)

# Function to read company data from CSV
def read_company_data(file_path):
    df = pd.read_csv(file_path)
    return df[['Company', 'Website', 'Person LinkedIn Url']].dropna()  # Include LinkedIn URL column

# Streamlit UI and Main Process
st.title("Company News Scraper and LLM Analyzer")

# Upload CSV File
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file:
    st.sidebar.write("Processing CSV: ", uploaded_file.name)

    # Get input from CSV and configure settings
    companies = read_company_data(uploaded_file)
    all_results = []
    api_semaphore = asyncio.Semaphore(async_semaphore)  # Set the async semaphore limit

    # Button to trigger processing
    run_button = st.button("Run Processing")

    if run_button:
        # Show a progress bar while processing
        progress_bar = st.progress(0)
        
        # Create async tasks for each company
        tasks = []
        total_companies = len(companies)
        completed_tasks = 0
        
        for index, row in companies.iterrows():
            company = row['Company']
            url = row['Website']
            linkedin_url = row['Person LinkedIn Url']  # Read LinkedIn URL from input
            
            tasks.append(extract_news(company, url, linkedin_url, max_websites, api_semaphore))

        # Manually handling event loop instead of asyncio.run()
        loop = asyncio.new_event_loop()  # Create a new event loop explicitly
        asyncio.set_event_loop(loop)  # Set the event loop for the current thread
        results = loop.run_until_complete(asyncio.gather(*tasks))
        
        # Flatten the list of results
        for result in results:
            all_results.extend(result)
            completed_tasks += 1
            progress_bar.progress(completed_tasks / total_companies)  # Incremental progress update

        # Save the results to a file
        save_to_excel(all_results, 'news_data.csv')
        st.write("Data saved to news_data.csv")

        # Provide download link
        with open('news_data.csv', 'rb') as file:
            st.download_button("Download the CSV", file, file_name="news_data.csv")

driver.quit()
