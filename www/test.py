# -*- coding: utf-8 -*-
import orm
import asyncio
from faker import Faker
from models import User,Blog,Comment
'''这里是用户的操作'''
fake=Faker()
async def test():
	await orm.create_pool(loop=loop,user='Moon', password='qwerasdf',database='awesome')#这里只写loop居然也可以
	u=User(name=fake.name(), email=fake.email(), passwd=fake.state(),image=fake.company(),admin=False)
	await u.save()
	await orm.destory_pool() #所有操作最后要跟上这个函数
	
loop=asyncio.get_event_loop()
loop.run_until_complete(test())
loop.close()			
		