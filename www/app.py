#!/usr/bin python3
# -*- coding: utf-8 -*-
import logging; #logging.basicConfig(level=logging.INFO)#不设置logging级别的话，默认是WARNING
import asyncio, os, json, time, orm
from datetime import datetime
from aiohttp import web
from urllib import parse
from jinja2 import Environment, FileSystemLoader
from config import configs
from coroweb import add_routes, add_static
from handlers import cookie2user,COOKIE_NAME

#每次加载新的url都会把中间件跑一遍的，没错我尤其指的就是auth_factory，每次打开页面就是它来处理cookie判断用户是否登录的

def init_jinja2(app, **kw):
	logging.info('init jinja2...')
	options=dict(
		autoescape=kw.get('autoescape',True),
		block_start_string=kw.get('block_start_string','{%'),
		block_end_string=kw.get('block_end_string','%}'),
		variable_start_string=kw.get('variable_start_string','{{'),
		variable_end_string=kw.get('variable_end_string','}}'),
		auto_reload=kw.get('auto_reload',True)
	)
	path=kw.get('path', None)
	if path is None:
		path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
	logging.info('set jinja2 template path: %s' % path)
	env=Environment(loader=FileSystemLoader(path), **options)
	filters=kw.get('filters', None)
	if filters is not None:
		for name,f in filters.items():
			env.filters[name]=f
	app['__templating__']=env
	
	'''
	中间件参数中第二个handler，也可以叫别的名字，它只是一个代号，这第二个参数是由aiohttp来把从add_routes函数里注册好的url处理函数传进去的。
	'''
async def logger_factory(app, handler):
	async def logger(request):
		logging.info('Request: %s %s' % (request.method, request.path))
		return await handler(request) #这里的装饰器逻辑很明确，我就多加一个logging，加完了以后还原样调用函数
	return logger

async def data_factory(app, handler):
	async def parse_data(request):
		logging.info('data_factory...')
		if request.method=='POST':
			if not request.content_type:
				return web.HTTPBadRequest(text='Missing Content_Type')
			content_type=request.content_type.lower()
			if content_type.startswith('application/json'):
				request.__data__=await request.json() #Read request body decoded as json.
				if not isinstance(request.__data__,dict):
					return web.HTTPBadRequest(text='JSON body must be object')
				logging.info('request json: %s' % request.__data__)
			elif content_type.startswith(('application/x-www-form-urlencoded','multipart/form-data')):
				params=await request.post() #A coroutine that reads POST parameters from request body.
				request.__data__=dict(**params)
				logging.info('request form: %s' % request.__data__)
			else:
				return web.HTTPBadRequest(text='Unsupported Content_Type: %s'% content_type)
		elif request.method=='GET':
			qs=request.query_string
			request.__data__={k:v[0] for k,v in parse.parse_qs(qs,True).items()}
			logging.info('request query: %s' % request.__data__)
		else:
			request.__data__=dict()
		return await handler(request)
	return parse_data
	
async def auth_factory(app,handler):
	async def auth(request):
		logging.info('check user: %s %s' % (request.method,request.path))
		request.__user__=None
		cookie_str=request.cookies.get(COOKIE_NAME)#从用户的请求中获取cookie
		if cookie_str:#如果得到了用户的cookie：
			user=await cookie2user(cookie_str)#用cookie2user函数来返回用户数据
			if user:#如果用户的cookie确实是我给他发的cookie（表现为user得到了数据）
				logging.info('set current user:%s' % user.email)
				request.__user__=user#把用户数据绑定在用户的请求里
		if request.path.startswith('/manage/') and (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound('/signin')
		if request.path.startswith('/setavatar') and (request.__user__ is None):
			return web.HTTPFound('/signin')
		return await handler(request)
	return auth
	
async def response_factory(app, handler):
	async def response(request):
		logging.info('Response handler...')
		r=await handler(request) 
		'''我靠看到这行没有？这就是为什么从逻辑上来说data工厂函数是在url处理函数之前运行，而response工厂函数是在url处理函数之后运行。
		其实本质上来说两者没区别，都是url处理函数的装饰函数，是同一时间运行的。只不过response工厂函数要等url处理函数先运行完。
		所以从一维上来看，中间件就是一个在数轴上从两头把url处理函数包裹起来的功能拓展包，中间件既可以在前面运行，也可以在后面运行（而装饰器本来就是这样运作的）'''
		if isinstance(r,web.StreamResponse):
			return r
		if isinstance(r,bytes):
			resp=web.Response(body=r)
			resp.content_type='application/octet-stream'
			return resp
		if isinstance(r,str):
			if r.startswith('redirect:'):
				return web.HTTPFound(r[9:])
			resp=web.Response(body=r.encode('utf-8'))
			resp.content_type='text/html;charset=utf-8'
			return resp
		if isinstance(r,dict):
			template=r.get('__template__')
			if template is None:
				resp=web.Response(body=json.dumps(r,ensure_ascii=False,default=lambda o:o.__dict__).encode('utf-8')) #dumps是将dict转化成str格式，loads是将str转化成dict格式。(但这里json依旧是json)
				resp.content_type='application/json;charset=utf-8'
				return resp
			else:
				resp=web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))#(**r)表示dict里面所有东西都传到模板里了
				resp.content_type='text/html;charset=utf-8'
				return resp
		if isinstance(r,int) and r>=100 and r<600:
			return web.Response(r) #这里直接带r，因为r是int，在Response接受的参数中只有状态码是int，所以直接带r。我想(status=r)也行
		if isinstance(r, tuple) and len(r) == 2:
			t,m=r
			if isinstance(t, int) and t>=100 and t<600:
				return web.Response(t,str(m))
		#default:
		resp=web.Response(body=str(r).encode('utf-8'))
		resp.content_type='text/plain;charset=utf-8'
		return resp
	return response

def datetime_filter(t):
	delta=int(time.time()-t)
	if delta<60:
		return u'1分钟前'
	if delta<3600:
		return u'%s分钟前' % (delta // 60)
	if delta<86400:
		return u'%s小时前' % (delta // 3600)
	if delta<604800:
		return u'%s天前' % (delta // 86400)
	dt=datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)
	
async def init(loop):
	await orm.create_pool(loop=loop, **configs['db'])
	app=web.Application(loop=loop,middlewares=[
		logger_factory,
		data_factory,
		response_factory,
		auth_factory
	])
	init_jinja2(app,filters=dict(datetime=datetime_filter))
	add_routes(app,'handlers')
	add_static(app)
	srv=await loop.create_server(app.make_handler(),'127.0.0.1','9000')
	logging.info('server started at http://127.0.0.1:9000...')
	return srv
	
loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()