"""Check discovery, filtering, downloads and small screens on the public registry."""
import json
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import shutil
import sys

base=sys.argv[1].rstrip('/')+'/'
with urlopen('https://www.blyx-lang.space/packages.json', timeout=30) as response:
    gallery = {p['documentation'].rsplit('/', 1)[-1]: p['logo'] for p in json.load(response)['packages']}
options=webdriver.ChromeOptions()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.binary_location=shutil.which('google-chrome')
with webdriver.Chrome(options=options) as driver:
    wait=WebDriverWait(driver,15)
    def select(css): return driver.find_element(By.CSS_SELECTOR,css)
    def results(): return [e.text for e in driver.find_elements(By.CSS_SELECTOR,'.entry:not([hidden]) h3')]
    def check_logo(css, slug):
        image = select(css)
        wait.until(lambda _: image.get_property('naturalWidth') > 0)
        expected = urljoin(base, f'images/{slug}.png?{urlsplit(gallery[slug]).query}')
        assert image.get_property('currentSrc') == expected, (slug, image.get_property('currentSrc'), expected)
    driver.set_window_size(1300,900)
    driver.get(base+'index.html')
    wait.until(lambda d:len(results())==18)
    check_logo('[href="packages/blyxtorch.html"] img', 'blyxtorch')
    check_logo('[href="packages/moments.html"] img', 'moments')
    select('#next').click()
    wait.until(lambda _: 'Page 2 of' in select('#page-number').text)
    select('[data-filter="library"]').click()
    select('#query').send_keys('moments')
    wait.until(lambda d:results()==['Moments'])
    driver.refresh()
    wait.until(lambda d:results()==['Moments'])
    select('.entry:not([hidden]) a').click()
    wait.until(lambda d:select('h1').text=='Moments')
    check_logo('img.mark', 'moments')
    assert select('[data-copy]').get_attribute('data-copy')=='nest add moments@0.1.0'
    assert select('tbody a').get_attribute('href')==urljoin(base,'files/moments/0.1.0.zip')
    driver.get(base+'index.html?kind=tool')
    wait.until(lambda d:len(results())==3)
    assert set(results())=={'Nest CLI','Blyx Compiler','Nest JavaScript SDK'}
    select('#query').send_keys('this-tool-does-not-exist')
    wait.until(lambda d:select('#empty').is_displayed())
    driver.set_window_size(375,850)
    driver.get(base+'index.html')
    wait.until(lambda d:len(results())==18)
    assert driver.execute_script('return document.documentElement.scrollWidth <= window.innerWidth + 1')
    select('nav a[href="publish.html"]').click()
    wait.until(lambda d:select('h1').text=='Publish to Blyx Nest')
print('Verified search, shared filters, pagination, package details, mobile layout and the publishing guide.')
