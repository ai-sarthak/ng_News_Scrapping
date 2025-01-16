import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import pandas as pd
import time
import analyser

# Set up chromedriver
chromedriver_path = 'c:\\Program Files\\chromedriver.exe' 
service = Service(chromedriver_path)
driver = webdriver.Chrome(service=service)

async def analysis_from_llm(news_extracted, api_semaphore):
    """Perform LLM analysis asynchronously while controlling access to API keys using a semaphore."""
    async with api_semaphore:
        # No need to await here, as get_analysis is now synchronous
        analysis = analyser.get_analysis(news_extracted)
        print(analysis)
        return analysis


async def extract_news(company, url, linkedin_url, max_websites, api_semaphore):
    """Extract news data from Google News search results and open news links to extract full content asynchronously."""
    driver.get(f'https://www.google.com/search?q={company}&tbm=nws')
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
                    analysis = await analysis_from_llm(combined_text, api_semaphore)
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

def save_to_excel(data, filename):
    """Save the extracted news data to an Excel file."""
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)

def read_company_data(file_path):
    df = pd.read_csv(file_path)
    return df[['Company', 'Website', 'Person LinkedIn Url']].dropna()  # Include LinkedIn URL column

async def main():
    input_file = 'testing - updated.csv' 
    max_websites = 5  # Define the number of websites to scrape
    companies = read_company_data(input_file)

    all_results = []
    api_semaphore = asyncio.Semaphore(4)  # Limit concurrent API usage to 4

    tasks = []
    for index, row in companies.iterrows():
        company = row['Company']
        url = row['Website']
        linkedin_url = row['Person LinkedIn Url']  # Read LinkedIn URL from input
        print(f"Processing company: {company} with URL: {url} and LinkedIn: {linkedin_url}")

        # Create async tasks for each company
        tasks.append(extract_news(company, url, linkedin_url, max_websites, api_semaphore))

    # Gather results from all tasks
    results = await asyncio.gather(*tasks)
    
    # Flatten the list of results
    for result in results:
        all_results.extend(result)

    save_to_excel(all_results, 'news_data.csv')
    driver.quit()

# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
