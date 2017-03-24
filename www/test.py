# -*- coding: utf-8 -*-
import orm
import asyncio
from models import User,Blog,Comment
'''这里是用户的操作'''
async def test():
	await orm.create_pool(loop=loop,user='Moon', password='qwerasdf',database='awesome')	
	u=User(id='1',name='Test', email='test@example.com', passwd='123123123',image='about:blank',admin=False)
	await u.save()

loop=asyncio.get_event_loop()
loop.run_until_complete(test())
loop.close()			
		