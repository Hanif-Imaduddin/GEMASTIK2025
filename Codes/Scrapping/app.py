from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support import expected_conditions as EC
import chromedriver_autoinstaller
import time

import os

import argparse
import json

from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException

import numpy as np
import pandas as pd

class Article:
    def __init__(self):
        self.authors = ''
        self.title = ''
        self.abstract = ''
        self.submitted_date = ''
        self.pdf_link = ''

def send_key(driver,xpath,key_word):
    elm = driver.find_element(By.XPATH,xpath)
    elm.send_keys(key_word)

def set_search_term(driver,key_word,dropdown_value="abstract"):
    dropdown_xpath = '//*[@id="terms-0-field"]'
    dropdown = Select(driver.find_element(By.XPATH,dropdown_xpath))
    dropdown.select_by_value(dropdown_value)

    send_key(driver,'//*[@id="terms-0-term"]',key_word)

def set_subject(driver):
    checkbox_xpath = '//*[@id="main-container"]/div[2]/div[2]/div[1]/div/form/section[2]/fieldset[1]/div[2]/div[1]/div[1]/div/div/label'
    checkbox = driver.find_element(By.XPATH,checkbox_xpath)
    checkbox.click()

def set_date_range(driver,date_from,date_to):
    label_xpath = '//*[@id="main-container"]/div[2]/div[2]/div[1]/div/form/section[2]/fieldset[2]/div[4]/div/div/label'
    label = driver.find_element(By.XPATH,label_xpath)
    label.click()
    time.sleep(0.5)

    date_from_xpath = '//*[@id="date-from_date"]'
    send_key(driver,date_from_xpath,date_from)
    
    date_to_xpath = '//*[@id="date-to_date"]'
    send_key(driver,date_to_xpath,date_to)

def click_search_button(driver):
    search_button_xpath = '//*[@id="main-container"]/div[2]/div[2]/div[1]/div/form/section[3]/button'
    search_button = driver.find_element(By.XPATH,search_button_xpath)
    search_button.click()


def click_next_button(driver):
    next_btn_xpath = '//*[@id="main-container"]/div[2]/nav[2]/a[2]'
    try:
        next_btn = driver.find_element(By.XPATH,next_btn_xpath)
        next_btn.click()
        return True
    except:
        return False
    
def extract_article_box(article_box):
    article = Article()
    try:
        more_btn = article_box.find_element(By.XPATH,'./p[3]/span[2]/a')
        more_btn.click()
        long_abstract = True
    except:
        long_abstract = False
    try:
        authors_xpath = './p[2]/a'
        authors = article_box.find_elements(By.XPATH,authors_xpath)
        author_list = []
        for author in authors:
            author_list.append(author.text)
        article.authors = ';'.join(author_list)
    except NoSuchElementException:
        print("Author tidak ditemukan")
        return article,False

    try:
        title_xpath = './p[1]'
        title = article_box.find_element(By.XPATH,title_xpath)
        article.title = title.text
    except NoSuchElementException:
        print("Title tidak ditemukan")
        return article,False

    try:
        if long_abstract:
            abstract = article_box.find_element(By.CSS_SELECTOR,'.abstract-full')
        else:
            abstract = article_box.find_element(By.CSS_SELECTOR,'.abstract-short')
        article.abstract = abstract.text
    except NoSuchElementException:
        print("Abstract tidak ditemukan")
        return article,False

    try:
        submitted_date = article_box.find_element(By.XPATH,'./p[4]')
        article.submitted_date = submitted_date.text.split(';')[0][10:]
    except NoSuchElementException:
        print("Submitted Date tidak ketemu")
        return article,False

    try:
        pdf_link = article_box.find_element(By.XPATH,'./div/p/span/a[1]')
        article.pdf_link = pdf_link.get_attribute('href')

        if 'pdf' not in article.pdf_link:
            raise('Link PDF tidak tersedia')
    except:
        print("Link PDF tidak tersedia")
        return article,False
    
    print(f'Author {article.authors} || Title {article.title} || Submitted Date {article.submitted_date} || PDF Link {article.pdf_link}')
    return article,True

def extract_article_boxes(driver):
    articles = []
    article_boxes_xpath = '//*[@id="main-container"]/div[2]/ol/li'
    article_boxes = driver.find_elements(By.XPATH,article_boxes_xpath)
    for article_box in article_boxes:
        article,valid = extract_article_box(article_box)
        if valid:
            articles.append(article)
    return articles

def get_data(driver,n=np.inf):
    articles = []
    i = 0
    while i < n:
        articles = articles + extract_article_boxes(driver)
        if not click_next_button(driver):
            break
        i += 1
        time.sleep(1)
    return articles

def article_list_to_df(article_list):
    df_dict = {
        'title': [],
        'authors':[],
        'abstract' : [],
        'submitted_date' : [],
        'pdf_link':[]
    }
    for article in article_list:
        df_dict['title'].append(article.title)
        df_dict['authors'].append(article.authors)
        df_dict['abstract'].append(article.abstract)
        df_dict['submitted_date'].append(article.submitted_date)
        df_dict['pdf_link'].append(article.pdf_link)
    return pd.DataFrame(df_dict)

def main():
    parser = argparse.ArgumentParser(description="Aplikasi Scraper")
    parser.add_argument('--config',type=str,required=True,help="Path ke file konfigurasi dalam format JSON")

    args = parser.parse_args()
    config_path = args.config
    config_data = None

    try:
        with open(config_path,'r') as f:
            config_data = json.load(f)
            print("Konfigurasi berhasil ditemukan")
        
        required_keys = ['batches']
        for key in required_keys:
            if key not in config_data:
                raise ValueError(f'Config harus memiliki key {key}')
    except FileExistsError:
        print(f'File {config_path} tidak ditemukan.')
    except json.JSONDecodeError as e:
        print(f'File bukan JSON yang falid')
    except ValueError as ve:
        print(ve)

    for batch in config_data['batches']:
        if batch['scraped'] == False:
            try:
                os.mkdir(batch['save_dir'])
            except:
                pass
            date_starts = pd.date_range(str(batch['year_start']),str(batch['year_end']),freq='YS')
            date_ends = pd.date_range(str(batch['year_start']),str(batch['year_end']+1),freq='YE')

            for date_start,date_end in zip(date_starts,date_ends):
                date_start = str(date_start)[:-9]
                date_end = str(date_end)[:-9]
                
                url = "https://arxiv.org/search/advanced"
                driver = webdriver.Chrome()
                driver.get(url)
                time.sleep(3)
                set_search_term(driver,batch['key_word'])
                set_subject(driver)
                set_date_range(driver,date_from=date_start,date_to=date_end)
                click_search_button(driver)
                time.sleep(2)
                articles = get_data(driver)
                driver.quit()

                df = article_list_to_df(articles)

                file_name = batch['save_dir']+date_end+".csv"
                df.to_csv(file_name,index=False)
                print(f'\n{file_name} saved!')

            batch['scraped'] = True
    with open(config_path,'w') as f:
        json.dump(config_data,f,indent=2)

        print(f"Config sudah diperbarui di {config_path}")
if __name__ == "__main__":
    main()