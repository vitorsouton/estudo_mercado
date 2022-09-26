import string
import requests
import os

import pandas as pd

from bs4 import BeautifulSoup
from unidecode import unidecode
from time import sleep
from random import choice
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from fake_useragent import UserAgent
from urllib.parse import urlparse


HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0'}


def get_complains(company_id: str, company_name: str, n_complains: int) -> pd.DataFrame:

    complains = {'company_name': [], 'description': [], 'href': [], 'full_complain': []}

    for n in range(0, n_complains, 10):
        url = f'https://iosearch.reclameaqui.com.br/raichu-io-site-search-v1/query/companyComplains/10/{n}'
        res = requests.get(url, params={'company': company_id}, headers=HEADERS).json()

        for x in range(10):
            data = res['complainResult']['complains']['data']

            description = data[x]['description']
            soup = BeautifulSoup(description, 'lxml').text
            complains['description'].append(soup)

            id_ = data[x]['id']
            title = data[x]['title']
            clean_title = title.translate(str.maketrans('', '', string.punctuation))
            href = clean_title.lower().strip() + '_' + id_
            href = unidecode(href.replace(' ', '-'))
            complains['href'].append(href)

            complains['company_name'].append(company_name)

            complains['full_complain'].append('')

    df = pd.DataFrame(complains)

    for i, company_name, href in zip(df.index, df.company_name, df.href):
        try:
            url = f"https://www.reclameaqui.com.br/{company_name}/{href}/"
            res = requests.get(url, headers=HEADERS)

            soup = BeautifulSoup(res.text, 'lxml')
            complain = soup.find('p', {'class': 'lzlu7c-17 fXwQIB'}).text
            df.iloc[i]['full_complain'] = complain
        except:
            df.drop(index=i, inplace=True)

    return df


def get_proxies() -> list:
    url = 'https://free-proxy-list.net/'

    res = requests.get(url)

    if res.status_code == 200:
        soup = BeautifulSoup(res.content, 'html.parser')
        proxies = []

        for r in soup.find('table', attrs={'class': 'table table-striped table-bordered'}).find_all('tr')[1:]:
            tds = r.find_all('td')
            try:
                ip = tds[0].text.strip()
                port = tds[1].text.strip()
                host = f'{ip}:{port}'
                proxies.append(host)
            except IndexError:
                continue
    else:
        proxies = ['amsterdam.nl.socks.nordhold.net:1080',
                    'atlanta.us.socks.nordhold.net:1080',
                    'dallas.us.socks.nordhold.net:1080',
                    'los-angeles.us.socks.nordhold.net:1080',
                    'nl.socks.nordhold.net:1080',
                    'se.socks.nordhold.net:1080',
                    'stockholm.se.socks.nordhold.net:1080',
                    'us.socks.nordhold.net:1080']

    return proxies


def get_info(company: str) -> pd.DataFrame:
    p = '/home/vitor/code/VSNRUBR/estudo_mercado/utils/drivers/'
    ua = UserAgent()
    user_agent = ua.random

    firefox_options = Options()
    firefox_options.add_argument('--headless')
    firefox_options.add_argument(f'user-agent={user_agent}')

    proxies = get_proxies()
    proxy = choice(proxies)
    capabilities = dict(DesiredCapabilities.FIREFOX)
    capabilities['proxy'] = {
        'http': proxy,
        'https': proxy,
        'proxyType': 'MANUAL',
        'socksProxy': proxy,
        'socksVersion': 5,
        'ftpProxy': proxy,
        'noProxy': 'localhost,127.0.0.1',
        'class': 'org.openqa.selenium.Proxy',
        'autodetect': False
    }

    driver = webdriver.Firefox(p, options=firefox_options, desired_capabilities=capabilities)
    driver.get(f'https://www.similarweb.com/website/{company}/')

    sleep(5)

    result = {
        'company_name': [company],
        'brazilian_visitors': [-1]
    }

    try:
        comp_info = driver.find_elements(
            By.CSS_SELECTOR, 'div.wa-overview__column:nth-child(6)')

        country = comp_info[0].text.split('\n')[7].split(',')[0]
        result['hq_country'] = country

        info = driver.find_elements(By.CLASS_NAME, 'engagement-list__item')

        bounce_rate = float(info[1].text.split('\n')[1][:-1]) / 100
        result['bounce_rate'] = [round(bounce_rate, 3)]

        visit_dur = int(info[3].text.split('\n')[1][3:5])
        result['visit_duration'] = [visit_dur]

        if info[0].text.split('\n')[1][-1] == 'M':
            total_visits = float(info[0].text.split('\n')[1][:-1]) * 1_000_000
        else:
            total_visits = float(info[0].text.split('\n')[1][:-1]) * 1_000

        country = driver.find_elements(
            By.CLASS_NAME, 'wa-geography__country-name')
        pct = driver.find_elements(
            By.CLASS_NAME, 'wa-geography__country-traffic-value')
        for c, p in zip(country, pct):
            c_text = c.text
            p_text = p.text

            if c_text == 'Brazil':
                percentage = float(p_text[:-1]) / 100
                br_visits = round(total_visits * percentage)
                result['brazilian_visitors'] = [br_visits]
            else:
                continue

        sex = driver.find_elements(
            By.CLASS_NAME, 'wa-demographics__gender-legend')[0].text
        sex_text = sex.split('\n')
        male = float(sex_text[3][:-1]) / 100
        female = float(sex_text[1][:-1]) / 100
        result['male'] = [round(male, 3)]
        result['female'] = [round(female, 3)]

        svg_eles = driver.find_elements(By.CLASS_NAME, 'highcharts-root')
        svg = svg_eles[3]
        svg_text = svg.text

        idades = svg_text.split('\n')[:6]
        labels = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
        for i, l in zip(idades, labels):
            i_pct = round((float(i[:-1]) / 100), 3)
            result[l] = [i_pct]

    except IndexError:
        driver.quit()
        raise IndexError

    except Exception:
        driver.quit()
        df = pd.DataFrame(result)
        sleep(3)

        return df

    driver.quit()

    df = pd.DataFrame(result)

    sleep(3)

    return df


def get_domains(csv: str) -> pd.DataFrame:
    df = pd.read_csv(csv)
    df = df[['Website']]
    df['domain'] = [0] * df.shape[0]
    df = df.dropna().reset_index()
    df['domain'] = [urlparse(site).netloc[4:] for site in df.Website]

    return df


def run(empresas: pd.DataFrame, csv_path: str) -> str:
    os.system('nordvpn d')

    check_df = pd.read_csv(csv_path, index_col=0)
    last_comp_idx = empresas[empresas.domain ==
                             check_df.iloc[-1].company_name].index[0]

    tries = 0
    for i in range(last_comp_idx, empresas.shape[0]):
        if tries < 10:
            try:
                domain = empresas.domain[i]
                df = pd.read_csv(csv_path, index_col=0)
                new_df = pd.concat([df, get_info(domain)], ignore_index=True)
                new_df.to_csv(csv_path)
            except IndexError:
                tries += 1
                print(f'Erro: {tries}')
                sleep(60)
                continue

        elif 10 <= tries < 30:

            countries = ['Albania', 'Greece', 'Portugal', 'Argentina', 'Hong_Kong', 'Romania', 'Australia', 'Hungary', 'Serbia',
                         'Austria', 'Iceland', 'Singapore', 'Belgium', 'Indonesia', 'Slovakia', 'Bosnia_And_Herzegovina', 'Ireland',
                         'Slovenia', 'Brazil', 'Israel', 'South_Africa', 'Bulgaria', 'Italy', 'South_Korea', 'Canada', 'Japan', 'Spain',
                         'Chile', 'Latvia', 'Sweden', 'Costa_Rica', 'Lithuania', 'Switzerland', 'Croatia', 'Luxembourg', 'Taiwan',
                         'Cyprus', 'Malaysia', 'Thailand', 'Czech_Republic', 'Mexico', 'Turkey', 'Denmark', 'Moldova', 'Ukraine',
                         'Estonia', 'Netherlands', 'United_Kingdom', 'Finland', 'New_Zealand', 'United_States', 'France',
                         'North_Macedonia', 'Vietnam', 'Georgia', 'Norway', 'Germany', 'Poland']

            country = choice(countries)
            os.system(f'nordvpn c {country}> /dev/null 2>&1')

            try:
                domain = empresas.domain[i]
                df = pd.read_csv(csv_path, index_col=0)
                new_df = pd.concat([df, get_info(domain)], ignore_index=True)
                new_df.to_csv(csv_path)
            except IndexError:
                tries += 1
                print(f'Erro: {tries}')
                sleep(10)
                continue
        else:
            break

    return 'Done'
