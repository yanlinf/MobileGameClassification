from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import multiprocessing as mp
from queue import Full, Empty
import json
import csv
import time
import argparse
from spider import CATEGORYIES, CHROME_PATH, GOOGLE_PLAY_BASE_URL
from package_spider import scrape_packages_in_category

XPATHS = {
    'general': {
        'Category': "//a[@itemprop='genre']",
        'Name': "//h1[@itemprop = 'name']/span",
        'Price': "//button[@aria-label and span[span]]",
        'Updated': "//div[div='Updated']/span/div/span",
        'Size': "//div[div='Size']/span/div/span",
        'Installs': "//div[div='Installs']/span/div/span",
        'Requires_Android': "//div[div='Requires Android']/span/div/span",
        'Age': "//div[div='Content Rating']/span/div/span/div",
        'Inapp_Products': "//div[div='In-app Products']/span/div/span",
        'Developer': "//div[div='Offered By']/span/div/span",
        'Description': "//content/div[@jsname='sngebd']",
        'Rating': "//div[@class='BHMmbe']",
        'Rating_Total': "//span[@aria-label]",
        'Content_Feature': "//div[div='Content Rating']/span/div/span/div[2]",
        'Version': "//div[div='Current Version']/span/div/span",
    },
    'rating': {
        'Rating_5': "//div[span = '5']/span[@title]",
        'Rating_4': "//div[span = '4']/span[@title]",
        'Rating_3': "//div[span = '3']/span[@title]",
        'Rating_2': "//div[span = '2']/span[@title]",
        'Rating_1': "//div[span = '1']/span[@title]",
    },
    'permission': {
        'button': "//div[div = 'Permissions']/span/div/span/div/a",
        'each_item': "//li[@class = 'NLTG4']/span",
    },
}

HEADERS = {
    'full': ['Category', 'Package', 'Name', 'Updated', 'Size',
             'Installs', 'Requires_Android', 'Age', 'Developer', 'Rating',
             'Rating_Total', 'Rating_5', 'Rating_4', 'Rating_3', 'Rating_2',
             'Rating_1', 'Price', 'Description',
             'Content_Feature', 'Permission', 'Inapp_Products', 'Version'],
    'trivial': ['Inapp_Products', 'Permission'],
}


class Crawler:

    def __init__(self, driver):
        self.driver = driver
        time.sleep(5)

    def get_page_by_package(self, package):
        self.driver.get(GOOGLE_PLAY_BASE_URL + 'details?id=' + package)
        time.sleep(1)

    def parse_current_page(self):
        parsed_dic = {}
        for key, xpath in XPATHS['general'].items():
            try:
                parsed_dic[key] = self.driver.find_element_by_xpath(xpath).text
            except Exception as e:
                pass
        for key, xpath in XPATHS['rating'].items():
            try:
                parsed_dic[key] = self.driver.find_element_by_xpath(
                    xpath).get_attribute('title')
            except Exception as e:
                pass
        return parsed_dic

    def explore_packages(self):
        def scroll_down(driver, clicks):
            for _ in range(clicks):
                ActionChains(driver).key_down(Keys.DOWN).perform()
        res = set()
        try:
            self.driver.find_elements_by_xpath(
                "//a[text() = 'See more']")[-1].click()
            scroll_down(self.driver, 50)
            for elem in self.driver.find_elements_by_xpath("//span[@class = 'preview-overlay-container']"):
                res.add(elem.get_attribute('data-docid'))
        except Exception as e:
            print(e)
        return res


class PackageInfoWriter:

    def __init__(self, csv_path, period, strict_mode):
        self.buffer, self.count = [], 0
        self.path, self.period, self.strict = csv_path, period, strict_mode

    def write(self):
        with open(self.path, 'a', encoding='utf-8', newline='') as fout:
            csvout = csv.writer(fout)
            csvout.writerows(self.buffer)
        self.buffer = []

    def process_dic(self, dic, package):

        def vectorize_dic(dic, package):
            for key in HEADERS['trivial']:
                dic[key] = dic.get(key, '???')
            dic['Package'] = package
            return [dic.get(key, '').replace('\n', ' ') for key in HEADERS['full']]

        vec = vectorize_dic(dic, package=package)
        if len(dic) < 10 or self.strict and '' in vec:
            print('pakcage %s missing property %d' %
                  (package, vec.index('')))
            return False

        self.buffer.append(vec)
        self.count += 1
        if self.count % self.period == 0:
            self.write()
        return True

    def close(self):
        self.write()


def scheduler(Q1, Q2):
    with open('log/scrape.json', 'r') as fin:
        visited, queue = json.load(fin)
    visited = set(visited)
    try:
        while True:
            while queue:
                try:
                    if queue[0] not in visited:
                        Q1.put(queue[0], block=False)
                        visited.add(queue[0])
                    queue.pop(0)
                except Full:
                    break
            while True:
                try:
                    pkg = Q2.get(block=False)
                    if pkg not in visited and pkg not in queue and len(queue) < 100000:
                        queue.append(pkg)
                except Empty:
                    break
    finally:
        with open('log/scrape.json', 'w') as fout:
            json.dump([list(visited), queue], fout, indent=4)


def crawl(Q1, Q2, pid, args):
    print('Process %d started...' % pid)
    options = Options()
    options.add_experimental_option(
        'prefs', {'intl.accept_languages': 'en,en_US'})
    if args.headless:
        options.add_argument('--headless')
    options.add_argument('--log-level=3')
    driver = webdriver.Chrome(executable_path=CHROME_PATH, options=options)
    writer = PackageInfoWriter('raw/%d.csv' % pid, 5, args.strict)
    crawler = Crawler(driver)

    try:
        while True:
            package = Q1.get()
            crawler.get_page_by_package(package)
            dic = crawler.parse_current_page()
            if dic.get('Category', None) in CATEGORYIES:
                print('[%d] %s' % (pid, package))
                writer.process_dic(dic, package)
                new_pkgs = crawler.explore_packages()
                for pkg in new_pkgs:
                    Q2.put(pkg)
    except Exception as e:
        print(e)
    finally:
        print('Process %d exit...' % pid)
        driver.quit()
        writer.close()


def main(args):
    Q1 = mp.Queue(maxsize=20)
    Q2 = mp.Queue(maxsize=1000)
    mp.Process(target=scheduler, args=(Q1, Q2)).start()
    for i in range(args.n):
        mp.Process(target=crawl, args=(Q1, Q2, i, args)).start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n',
                        type=int,
                        default=8,
                        help="the number of worker processes to use")
    parser.add_argument('--headless',
                        action='store_true',
                        help="use the headless version of Chrome")
    parser.add_argument('--strict',
                        action='store_true',
                        help="skip the package if at least one property is missing")
    args = parser.parse_args()
    main(args)