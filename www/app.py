# -*- coding: utf-8 -*-
import logging; logging.basicConfig(level=logging.INFO)
import asyncio, os, json, time
from datetime import datetime
from aiohttp import web
from urllib import parse
from jinja2 import Environment, FileSystemLoader
import orm
from coroweb import add_routes, add_static

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
				request.__data__=await request.json()
				if not isinstance(request.__data__,dict):
					return web.HTTPBadRequest(text='JSON body must be object')
				logging.info('request json: %s' % request.__data__)
			elif content_type.startswith(('application/x-www-form-urlencoded','multipart/form-data')):
				params=await request.post()
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
	
async def response_factory(app, handler):
	async def response(request):
		logging.info('Response handler...')
		r=await handler(request)
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
				resp=web.Response(body=json.dumps(r,ensure_ascii=False,default=lambda o:o.__dict__).encode('utf-8'))
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
	dt=datatime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)
	
async def init(loop):
	await orm.create_pool(loop=loop,host='127.0.0.1', port=3306,user='Moon',password='qwerasdf',database='awesome')
	app=web.Application(loop=loop,middlewares=[
		logger_factory,
		data_factory,
		response_factory
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