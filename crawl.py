# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------------#
#  Name:           crawl.py                                                           #
#  Description:    an efficient multi-process web crawler that automatically scrapes  #
#                  app info from Google Play                                          #
#-------------------------------------------------------------------------------------#
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import multiprocessing as mp
import json
import csv
import time
import argparse
from queue import Full, Empty

CATEGORIES = ['Action', 'Adventure', 'Arcade', 'Board', 'Card',
              'Casino', 'Casual', 'Educational', 'Music', 'Puzzle',
              'Racing', 'Role_Playing', 'Simulation', 'Sports',
              'Strategy', 'Trivia', 'Word']

CHROME_PATH = 'Z:/chromedriver.exe'

START_PACKAGES = [
    'com.orangeapps.piratetreasure',
    'se.hellothere.gravityhd',
    'com.makingfun.mageandminions',
    'com.gameloft.android.ANMP.Gloft5DHM',
    'com.Zeeppo.GuitarBand',
]

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
    # 'permission': {
    #     'button': "//div[div = 'Permissions']/span/div/span/div/a",
    #     'each_item': "//li[@class = 'NLTG4']/span",
    # },
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
    """
    A web crawler object that can fetch app pages from Google Play and parse them
    into app info dict.
    
    Parameters
    ----------
    driver: Selenium.webdriver.Chrome object
        a selenium webdriver object utilized to control the browser
    """

    def __init__(self, driver):
        self.driver = driver
        time.sleep(5)

    def get_page_by_package(self, package):
        """
        Given an Android package name, fetch the app info page from Google Play.

        Returns: None
        """
        self.driver.get(
            'https://play.google.com/store/apps/details?id=' + package)
        time.sleep(1)

    def parse_current_page(self):
        """
        Parse the current page into a python dict based on the key-xpath pairs in
        varaible XPATH.

        Returns: dict{str: str, ... , str: str}
        """
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
        """
        Click the see-more button, parse similar apps from this page, and return their
        package names in a python set.

        Returns: set{str, str, ... , str}
        """
        def scroll_down(driver, clicks):
            for _ in range(clicks):
                ActionChains(driver).key_down(Keys.DOWN).perform()

        res = set()
        try:
            self.driver.find_element_by_xpath(
                "//a[@aria-label and text() = 'See more']").click()
            # scroll_down(self.driver, 50)
            time.sleep(1)
            for elem in self.driver.find_elements_by_xpath("//span[@class = 'preview-overlay-container']"):
                res.add(elem.get_attribute('data-docid'))
        except Exception as e:
            print(e)
        return res


class PackageInfoWriter:
    """
    Converts app info dicts to a feature vector and buffer them. The buffer is
    periodically written to the target path.

    Parameters
    ----------
    csv_path: str
        the csv file to write data
    period: int
        the number of rows to buffer before writing to csv file
    strict_mode: bool
        skip the package if at least one attribute is missing
    """
    def __init__(self, csv_path, period, strict_mode):
        """
        csv_path: str
            the csv file to write data
        period: int
            the number of rows to buffer before writing to csv file
        strict_mode: bool
            skip the package if at least one attribute is missing

        Returns: None
        """
        self.buffer, self.count = [], 0
        self.path, self.period, self.strict = csv_path, period, strict_mode

    def write(self):
        """
        Write(append) the buffered rows to a csv file and clear the buffer.

        Returns: None
        """
        with open(self.path, 'a', encoding='utf-8', newline='') as fout:
            csvout = csv.writer(fout)
            csvout.writerows(self.buffer)
        self.buffer = []

    def process_dic(self, dic, package):
        """
        Given a package and its info dict, convert the dict to a vector based on the
        attributes specified in HEADERS['full'], replace the missing trivial attribute
        with '???', then append it to the buffer.

        dic: dict{str: str, ... str: str}
            the info dict parsed from a Google Play page
        package: str
            the name of the package

        Returns: None
        """

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
        """
        Write the remaining buffered rows to the csv file.

        Returns: None
        """
        self.write()


def scheduler(Q1, Q2, verbose):
    """
    A process that repeatedly sends packages to worker processes based on a BFS-search
    approach and fetches additional packages from worker process and append them to the
    BFS queue. Can only be terminated by Ctrl-C. Notes that visted packages and bfs-queue
    will be saved to and restored from "./log/scrape.json".

    Q1: multiprocessing.Queue object
    Q2: multiprocessing.Queue object
    verbose: bool

    Returns: None
    """
    try:
        with open('log/scrape.json', 'r') as fin:
            visited, queue = json.load(fin)
        visited = set(visited)
    except OSError:
        visited = set()
        queue = START_PACKAGES

    count = 0
    stop_flag = False
    try:
        while True:
            while queue:
                try:
                    if queue[0] not in visited:
                        Q1.put(queue[0], block=False)
                        visited.add(queue[0])
                        count += 1
                    queue.pop(0)
                except Full:
                    break
            else:
                if stop_flag:
                    break
                else:
                    stop_flag = True
            while True:
                try:
                    if stop_flag:
                        pkg = Q2.get(timeout=30)
                    else:
                        pkg = Q2.get(block=False)
                    stop_flag = False
                    if pkg not in visited and pkg not in queue and len(queue) < 100000:
                        queue.append(pkg)
                except Empty:
                    break
            if count % 100 == 0:
                count = 1
                if verbose:
                    print('storing data, current length of queue is %d' %
                          len(queue))
                with open('log/scrape.json', 'w') as fout:
                    json.dump([list(visited), queue], fout, indent=4)
    finally:
        with open('log/scrape.json', 'w') as fout:
            json.dump([list(visited), queue], fout, indent=4)


def crawl(Q1, Q2, pid, args):
    """
    The worker process that consumes packages from scheduler process, scrapes it from
    Google Play, parses it into a python dict, writes it to a csv file, and send more
    packages to scheduler. Can only be terminated by Ctrl-C.

    Q1: multiprocessing.Queue object
    Q2: multiprocessing.Queue object
    pid: int
    args: argparse.Namespace object

    Returns: None
    """
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
            try:
                package = Q1.get(timeout=120)
            except Empty:
                break
            crawler.get_page_by_package(package)
            dic = crawler.parse_current_page()
            if 'Category' in dic and dic['Category'].replace(' ', '_') in CATEGORIES:
                dic['Category'] = dic['Category'].replace(' ', '_')
                print('[%d] %s %s' % (pid, package, dic['Category']))
                writer.process_dic(dic, package)
                new_pkgs = crawler.explore_packages()
                if args.verbose:
                    print('appending %d packages to queue' % len(new_pkgs))
                for pkg in new_pkgs:
                    Q2.put(pkg)
    except Exception as e:
        print(e)
    finally:
        print('Process %d exit...' % pid)
        driver.quit()
        writer.close()


def main(args):
    """
    Create two multiprocessing.Queue objects for communication between sceduler and
    workers, then start one scheduler process and n (specified by args.n, default 8)
    worker processes.

    args: argparse.Namespace object

    Returns: None
    """
    Q1 = mp.Queue(maxsize=20)
    Q2 = mp.Queue(maxsize=1000)
    mp.Process(target=scheduler, args=(Q1, Q2, args.verbose)).start()
    for i in range(args.n):
        mp.Process(target=crawl, args=(Q1, Q2, i, args)).start()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-n',
                        type=int,
                        default=8,
                        help="the number of worker processes to use (default: 8)")
    parser.add_argument('--headless',
                        action='store_true',
                        help="use the headless version of Chrome")
    parser.add_argument('--strict',
                        action='store_true',
                        help="skip the package if at least one attribute is missing")
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help="increase verbosity")
    args = parser.parse_args()
    main(args)
