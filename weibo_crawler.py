import time

import logging

from scrapy import Selector
import re
import requests
import os
from datetime import datetime
import hashlib

import oss2

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


import setting
import table
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker



##################
## 新浪微博图片下载
##################

def download_pic(image_url,local_path):
    authority = ''
    auth_re = re.search(r'//([^/]+)/\S+$', image_url)
    if auth_re:
        authority = auth_re.groups()[0]
        logger.info("authority = " + str(authority))

    path_re = re.search(r'//[^/]+(/\S+)$', image_url)
    if path_re:
        path = path_re.groups()[0]
        if path:
            logger.info("path = " + path)
            headers = {'authority': authority,
                       'method': 'GET',
                       'path': path,
                       'scheme': 'https',
                       'accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                       'accept-encoding': 'gzip, deflate, br',
                       'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7',
                       'cache-control': 'no-cache',
                       'pragma': 'no-cachee',
                       'referer': 'https://weibo.com/',
                       'sec-ch-ua': '"Chromium";v="88", "Google Chrome";v="88", ";Not A Brand";v="99"',
                       'sec-ch-ua-mobile': '?0',
                       'Sec-Fetch-Dest': 'image',
                       'Sec-Fetch-Mode': 'no-cors',
                       'Sec-Fetch-Site': 'cross-site',
                       'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.67 Safari/537.3'
                       }

            count = 0
            while count < 3:
                pic = requests.get('https:' + image_url, headers=headers)
                if pic.status_code == 200:
                    logger.info("download successfully -- " + image_url)
                    with open(local_path, 'wb') as fp:
                        fp.write(pic.content)
                        fp.close()
                    break

                count += 1
##############
## oss图片上传 #
##############
def upload_pic(bucket, object_name, local_path):
    result = bucket.put_object_from_file(object_name, local_path)
    logger.info('http status: {0}'.format(result.status))

    if result.status == 200:
        logger.info("oss upload successfully -- " + local_path)
        return True
    else:
        logger.warning('oss upload fail,status:%s,local_path:%s', result.status,local_path)
        return False


logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)8s\t%(message)s', )
logger = logging.getLogger(__name__)

engine = create_engine('mysql://root:David_2020@localhost:3306/hjdang')
DBSession = sessionmaker(bind=engine)
# 创建DBSession类型:
session = DBSession()

OSS_ACCESS_KEY = 'LTAI4G3hELVPQ1BoTGyhm8cq'
OSS_ACCESS_SECTET = 'hrktHTNKsj1jZpm6HTRdKsEL2Wff0h'
OSS_BUCKET_SMALL = 'food-small'
OSS_BUCKET_CLEAR = 'food-clear'
OSS_ENDPOINT = 'oss-cn-hangzhou.aliyuncs.com'

auth = oss2.Auth(OSS_ACCESS_KEY, OSS_ACCESS_SECTET)
# Endpoint以杭州为例，其它Region请按实际情况填写。
bucket_food_small = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_SMALL)
bucket_food_clear = oss2.Bucket(auth, OSS_ENDPOINT, OSS_BUCKET_CLEAR)

broswer = webdriver.Chrome()


####################
# 插入或更新food_items
####################
def insert_or_update(cls,table_item,**kwargs):
    logger.info("kwargs = " + str(kwargs))

    exist = session.query(cls).filter_by(**kwargs).first()
    logger.info("exist = " + str(exist))
    if not exist:
        logger.info("inserting new ")
        logger.info("table_item = " + str(table_item))
        session.add(table_item)
        try:
            session.flush()
            session.identity_map
        except:
            session.rollback()
    else:
        for key in table_item.__dict__:
            if key == '_sa_instance_state':
                continue
            if hasattr(exist,key):
                setattr(exist,key,getattr(table_item,key))
        logger.info("updating exist")

    try:
        session.commit()
    except:
        session.rollback()
    finally:
        session.close()


################
### 新浪微博登陆
################
def login():
    broswer.get("https://www.sina.com.cn")

    login_tab = broswer.find_element_by_xpath("//div[@id='SI_Top_Login']")
    ActionChains(broswer).move_to_element(login_tab).perform()

    login_name_input = broswer.find_element_by_xpath("//input[@node-type='loginname']")
    print(login_name_input)
    login_name_input.send_keys("zjhgx@sina.com")
    time.sleep(1)

    passowrd_input = broswer.find_element_by_xpath("//input[@node-type='password']")
    passowrd_input.send_keys("zjhgx_7114217")
    time.sleep(1)

    login_button = broswer.find_element_by_xpath("//span/a[@node-type='submit']")
    login_button.click()

    time.sleep(20)


##################
## 爬虫工作过程 ###
##################
def crawl():
    last_height = broswer.execute_script("return document.body.scrollHeight")
    logger.info("last_height = " + str(last_height))
    count = 0
    # 滑到一页的最低层
    while True:
        broswer.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        new_height = broswer.execute_script("return document.body.scrollHeight")
        logger.info("new_height = " + str(new_height))
        # result = EC.invisibility_of_element_located((By.XPATH,
        #                   '//div[@node-type="feed_list_page"]/div/a[contains(concat(" ", normalize-space(@class), " "), "next")]'))(broswer)

        # 下一页按钮出现时表示已经滑倒底，
        if not EC.invisibility_of_element_located((By.XPATH, '//div[@node-type="feed_list_page"]/div/a[contains(concat(" ", normalize-space(@class), " "), "next")]'))(broswer):
            break
        # last_height = new_height
        count = count + 1

    source = broswer.page_source

    html_selector = Selector(text=source)
    items_selector = html_selector.xpath('//div[@node-type="feed_list"]/div[@action-type="feed_list_item"]')

    if items_selector:
        for item_selector in items_selector:
            food_item = table.CrawlFood()
            small_img_url_list = []
            clear_img_url_list = []
            mid = item_selector.xpath('./@mid').get()
            if mid:
                food_item.mid = mid
            title_list = item_selector.xpath('.//div[@node-type="feed_list_content"]/text()').getall()
            for title in title_list:
                # filter_title = filter(lambda x: x in string.printable, title)
                # 结果中存在unicode是\u200b-zero width space，无法用strip()给过滤掉，先手动替换
                title = title.replace(u'\u200b', '')
                # filter_result = [f for f in title]
                if title.strip():
                    # b2 = bytes(title.strip(), encoding='utf8')
                    # logger.info("len = " + str(len(title.strip())))
                    food_item.title = title.strip()
                    logger.info("title = " + title.strip())

            raw_clear_pics_text = item_selector.xpath('.//ul[@node-type="fl_pic_list"]/@action-data').get()
            if not raw_clear_pics_text:
                continue

            clear_pics_text = requests.utils.unquote(raw_clear_pics_text.strip())
            clear_pic_src_m = re.search(r'clear_picSrc=(\S+)&thumb_picSrc=\S+', clear_pics_text)
            if clear_pic_src_m:
                clear_pic_src_str = clear_pic_src_m.groups()[0]
                if clear_pic_src_str:
                    clear_pic_imgs = clear_pic_src_str.split(',')
                    logger.info("clear_pic_imgs = " + str(clear_pic_imgs))
            thumb_150_imgs = item_selector.xpath('.//li[@action-type="fl_pics"]//img/@src').getall()
            logger.info(thumb_150_imgs)

            if len(clear_pic_imgs) == len(thumb_150_imgs):
                logger.info("大小图片长度符合")
                clear_pic_img_names = [img[img.rfind('/') + 1:] for img in clear_pic_imgs]
                logger.info("clear_pic_img_names = " + str(clear_pic_img_names))
                i = 0
                for img in thumb_150_imgs:
                    name = img[img.rfind('/') + 1:]
                    logger.info("name = " + name)
                    if name == clear_pic_img_names[i]:
                        logger.info("匹配成功 -- " + name)
                        byte_name = bytes(name, encoding='utf8')
                        upload_name = hashlib.md5(byte_name).hexdigest()
                        today_str = datetime.today().strftime('%Y%m/%d')
                        object_name = today_str + "/" + upload_name
                        logger.info("object_name = " + object_name)
                        # 下载上传小图片
                        local_path = setting.image_location + os.sep + 'small_' + name
                        download_pic(img, local_path)
                        small_upload_result = upload_pic(bucket_food_small, object_name, local_path)
                        # 下载上传清晰图片
                        local_path = setting.image_location + os.sep + 'clear_' + name
                        download_pic(clear_pic_imgs[i], local_path)
                        clear_upload_result = upload_pic(bucket_food_clear, object_name, local_path)
                        if small_upload_result and clear_upload_result:
                            small_img_url = 'https://' + OSS_BUCKET_SMALL + '.' + OSS_ENDPOINT + '/' + object_name
                            small_img_url_list.append(small_img_url)
                            clear_img_url = 'https://' + OSS_BUCKET_CLEAR + '.' + OSS_ENDPOINT + '/' + object_name
                            clear_img_url_list.append(clear_img_url)
                    i = i + 1
                # 把数据插入数据库
                food_item.clear_image_urls = json.dumps(clear_img_url_list)
                food_item.small_image_urls = json.dumps(small_img_url_list)
                food_item.creator = 'weibo_crawler'
                food_item.last_operator = 'weibo_crawler'
                insert_or_update(table.CrawlFood, food_item, mid=mid)
            else:
                logger.warning("大小图片长度不符，跳过这条")

    next_page_button = broswer.find_element_by_xpath('//div[@node-type="feed_list_page"]/div/a[contains(concat(" ", normalize-space(@class), " "), "next")]')
    time.sleep(2.2)
    if next_page_button:
        ActionChains(broswer).move_to_element(next_page_button).perform()
        next_page_button.click()
        time.sleep(4.2)
        crawl()


#######################
# 程序运行 ##########
#######################
login()
broswer.get("https://weibo.com/u/5871715453?from=myfollow_all&is_all=1#_rnd1612635683916")
time.sleep(7)

crawl()

        # for thumb_150_li_selector in thumb_150_lis_selector:
        #     thumb_150_img_selector = thumb_150_li_selector.find_element_by_xpath('./img')
        #
        #     print(thumb_150_img_selector.get_attribute("src"))
            # thumb_150_li_selector.click()
            # time.sleep(3)
            #
            # img_to_small_button = item_selector.find_element_by_xpath('.//a[@action-type="feed_list_img_toSmall"]')
            # print(img_to_small_button.get_attribute('innerHTML'))
            # # broswer.execute_script("window.scrollTo(0, 2);")
            # broswer.execute_script("arguments[0].click();", img_to_small_button)

            # webdriver.ActionChains(broswer).move_to_element(img_to_small_button).click(img_to_small_button).perform()
            # time.sleep(1)






