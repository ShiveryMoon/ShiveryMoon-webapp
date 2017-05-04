#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re, time, json, logging, hashlib, base64, asyncio
import markdown2
from coroweb import get, post
from models import User, Comment, Blog, next_id
from apis import APIValueError,APIResourceNotFoundError
from config import configs
from aiohttp import web

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')
COOKIE_NAME='awesession'
_COOKIE_KEY=configs.session.secret

'''功能函数'''

def user2cookie(user,max_age):
	'''
	Generate cookie str by user.
	build cookie string by:id-expires-sha1
	'''
	expires=str(int(time.time()+max_age))
	s='%s-%s-%s-%s' % (user.id,user.passwd,expires,_COOKIE_KEY)
	L=[user.id,expires,hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)
	
async def cookie2user(cookie_str):
	'''
	Parse cookie and load user if cookie is valid.
	'''
	if cookie_str is None:
		return None
	try:
		L=cookie_str.split('-')
		if len(L) != 3:
			return None
		uid,expires,sha1=L
		if int(expires) < time.time():
			return None
		user = await User.find(uid)
		if user is None:
			return None
		s='%s-%s-%s-%s' % (uid,user.passwd,expires,_COOKIE_KEY)
		if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
			logging.info('invalid sha1')
			return None
		user.passwd='******'
		return user
	except Exception as e:
		logging.exception(e)
		return None
		
def check_admin(request):
	if request.__user__ is None or request.__user__.admin is None:
		raise APIPermissionError()
		
def get_page_index(page_str):
	p=1
	try:
		p=int(page_str)
	except ValueError as e:
		pass
	if p<1:
		p=1
	return p
	
def text2html(text):
	lines=map(lambda s:'<p>%s</p>' % s.replace('&','&amp;').replace('>','&gt;').replace('<','&lt;'),filter(lambda s:s.strip()!='',text.split('\n')))#把几行代码去掉空行后变成list，然后各种replace
	
'''功能函数END'''
'''网页'''		
		
@get('/')
async def index(request):#这里不用async，因为这个主页的加载没有任何IO操作
	summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
	content = 'You shall not pass!'
	blogs = [
		Blog(id='1', user_id='a', user_name='Bob', user_image='a', name='Test Blog', content=content, summary=summary, created_at=time.time()-120),
		Blog(id='2', user_id='a', user_name='Bob', user_image='a', name='Something New', content=content, summary=summary, created_at=time.time()-3600),
		Blog(id='3', user_id='a', user_name='Bob', user_image='a', name='Learn Swift', content=content, summary=summary, created_at=time.time()-7200)
	]
	return {
		'__template__': 'blogs.html',
		'blogs': blogs,
		'__user__':request.__user__
	}

@get('/blog/{id}')
async def get_blog(id,request):
	blog=await Blog.find(id)
	comments=await Comment.findAll('blog_id=?',[id],orderBy='created_at desc')
	for c in comments:
		c.html_content=text2html(c.comtent)
	blog.html_content=markdown2.markdown(blog.content)
	return{
		'__template__':'blog.html',
		'blog':blog,
		'comments':comments,
		'__user__':request.__user__
	}
		
@get('/manage/blogs/create')
def manage_create_blog(request):
	return{
		'__template__':'manage_blog_edit.html',
		'id':'',
		'action':'/api/blogs',
		'__user__':request.__user__
	}
	
@get('/register')
def register():
	return {
		'__template__':'register.html'
	}
		
@get('/signin')
def signin():
	return {
		'__template__':'signin.html'
	}
	
@get('/signout')
def signout(request):
	referer=request.headers.get('Referer')
	r=web.HTTPFound(referer or '/')
	r.set_cookie(COOKIE_NAME,'-delete-',max_age=0,httponly=True) #这里不能使用del_cookie，因为这是个新定义的r，根本没cookie给你删啊
	logging.info('user signed out.')
	return r

'''网页END'''
'''api'''
	
@post('/api/authenticate')	#登录
async def authenticate(email,passwd):
	if not email:
		raise APIValueError('email','Invalid email.')
	if not passwd:
		raise APIValueError('passwd','Invalid password.')
	users=await User.findAll('email=?',[email])
	if len(users)==0:
		raise APIValueError('email','Email not exist.')
	user=users[0]
	#check passwd:
	sha1=hashlib.sha1()
	sha1.update(user.id.encode('utf-8'))
	sha1.update(b':')
	sha1.update(passwd.encode('utf-8'))
	if user.passwd != sha1.hexdigest():
		raise APIValueError('passwd','Invalid password.')
	#authenticate ok ,set cookie:
	r=web.Response()
	r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)
	user.passwd='******'
	r.content_type='application/json'
	r.body=json.dumps(user,ensure_ascii=False).encode('utf-8')
	return r
	
@post('/api/users') #注册
async def api_register_user(email,name,passwd):
	if not name or not name.strip():
		raise APIValueError('name')
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError('email')
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError('passwd')
	users=await User.findAll('email=?',[email])
	if len(users) > 0:
		raise APIError('register:failed','email','Email is already in use.')
	uid=next_id()
	sha1_passwd='%s:%s' % (uid,passwd)
	user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest(), admin=False)
	await user.save()
	#make session cookie:
	r=web.Response()
	r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)
	user.passwd='******'
	r.content_type='application/json'
	r.body=json.dumps(user,ensure_ascii=False).encode('utf-8')
	return r
	
@get('/api/blogs/{id}')
async def api_get_blog(id):
	blog=await Blog.find(id)
	return blog
	
@post('/api/blogs')
async def api_create_blog(name,summary,content,request):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError('name','name cannot be empty.')
	if not summary or not summary.strip():
		raise APIValueError('summary','summary cannot be empty.')
	if not content or not content.strip():
		raise APIValueError('content','content cannot be empty.')
	blog=Blog(user_id=request.__user__.id,user_name=request.__user__.name,user_image=request.__user__.image,name=name.strip(),summary=summary.strip(),content=content.strip())
	await blog.save()
	return blog
	
'''api END'''	