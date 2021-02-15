from sqlalchemy import Column, Integer,String, SmallInteger, DateTime,DECIMAL,create_engine
from sqlalchemy.ext.declarative import declarative_base

# 创建对象的基类:
Base = declarative_base()

# 无效商品表
class CrawlFood(Base):
    __tablename__ = 'crawl_food'

    id = Column(Integer, primary_key=True)
    mid = Column(String(32))
    title = Column(String(127))
    small_image_urls = Column(String(1024), default='')
    clear_image_urls = Column(String(1024), default='')
    status = Column(SmallInteger,default=1)
    creator = Column(String(50))
    last_operator = Column(String(50))

