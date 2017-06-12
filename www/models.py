#!/usr/bin python3
# -*- coding: utf-8 -*-
import time,uuid
from orm import Model,StringField,BooleanField,FloatField,TextField
''' 用户输入的东西并不会进入各种Field里面。Field类是管理者用来给各个列名设置属性的工具
	比如管理者可以给id这列规定默认值，规定是否为主键，而这些规定的操作在model.py里
	至于用户，他们根本不用关心给每个列名设置属性，他们只要给对应列名输入数据就行了，比如给id赋1，给name赋Tom。
	用户输入的数据由Model的init(**kw)来接收，用self[key]就可以获取用户输入的数据。
'''
def next_id():
	return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)
	
class User(Model):
	__table__='users'
	
	id=StringField(primary_key=True,default=next_id,ddl='varchar(50)')
	email=StringField(ddl='varchar(50)')
	passwd=StringField(ddl='varchar(50)')
	admin=BooleanField()
	name=StringField(ddl='varchar(50)') 
	image=StringField(ddl='varchar(500)')
	created_at=FloatField(default=time.time)
	
class Blog(Model):
	__table__='blogs'

	id=StringField(primary_key=True,default=next_id,ddl='varchar(50)')
	user_id=StringField(ddl='varchar(50)')
	user_name=StringField(ddl='varchar(50)')
	user_image=StringField(ddl='varchar(500)')
	name = StringField(ddl='varchar(50)')
	summary = StringField(ddl='varchar(200)')
	content = TextField()
	created_at = FloatField(default=time.time)
	
class Comment(Model):
	__table__='comments'
	
	id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
	blog_id = StringField(ddl='varchar(50)')
	user_id = StringField(ddl='varchar(50)')
	user_name = StringField(ddl='varchar(50)')
	user_image = StringField(ddl='varchar(500)')
	content = TextField()
	created_at = FloatField(default=time.time)
			
		