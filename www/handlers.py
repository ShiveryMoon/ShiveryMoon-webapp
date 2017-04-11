# -*- coding: utf-8 -*-
from coroweb import get,post
from aiohttp import web
from models import User

@get('/')
async def index(request):
	users=await User.findAll()
	return {
		'__template__':'test.html',
		'users':users
	}
	
@get('/blog')
async def blog(request):
	body='<h1>Awesome: /blog</h1>'
	return body

@get('/greeting')
async def greeting(name,request):#request必须是最后获取的，RequestHandler里制作**kw的时候就是这个顺序
	body='<h1>Awesome: /greeting %s</h1>'%name
	return body

@get('/input')
async def input(request):
	body='<form action="/result" method="post">E-mail: <input type="email" name="user_email" /><input type="submit" /></form>'
	return body

@post('/result')
async def result(user_email,request):
	body='<h1>您输入的邮箱是%s</h1>'%user_email
	return body

@get('/create_comment')
async def create_comment(request):
	body='<h1>Awesome: /create_comment</h1>'
	return body	

			