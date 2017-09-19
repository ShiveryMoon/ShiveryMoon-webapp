#!/usr/bin python3
# -*- coding: utf-8 -*-
#https://github.com/moling3650/mblog/blob/master/www/app/frame/__init__.py
import asyncio
import functools
import inspect
import logging
import os
from aiohttp import web
from apis import APIError

def request(path,*,method):
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args, **kw):#原函数有什么，就给他原样传回去，我们并不需要动传来的参数
			return func(*args, **kw)
		wrapper.__method__=method#就只是给wrap加两个属性
		wrapper.__route__=path
		return wrapper
	return decorator
	
get=functools.partial(request, method='GET')#大概的意思是说，创建一个新函数get，它从request函数继承，并且预先传一个method参数
post=functools.partial(request, method='POST')#这他妈不就是偏函数吗
put=functools.partial(request, method='PUT')#偏函数：把一个函数的某些参数给固定住（也就是设置默认值），返回一个新的函数，调用这个新函数会更简单。
delete=functools.partial(request, method='DELETE')

class RequestHandler(object):
	def __init__(self, func):
		self._func=asyncio.coroutine(func) #就是老版的async def，把参数变成协程
		
	#把url函数需要的参数找出来存到required_args(以OrderedDict形式)里，然后从request里根据required_args来抽出材料搭配制作kw，再判断数据是否符合要求，最后把kw直接用作func参数
	async def __call__(self, request):
		required_args=inspect.signature(self._func).parameters
		logging.info('required args: %s' % required_args)
		kw={arg:value for arg, value in request.__data__.items() if arg in required_args}
		kw.update(request.match_info)
		if 'request' in required_args:
			kw['request']=request
		for key, arg in required_args.items():
			if key=='request' and arg.kind in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD):
				return web.HTTPBadRequest(text='request parameter cannot be the var arugment.')
			if arg.kind not in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD):
				if arg.default==arg.empty and arg.name not in kw:
					return web.HTTPBadRequest(text='Missing argument: %s' % arg.name)
		logging.info('call with args: %s' % kw)
		try:
			return await self._func(**kw)
		except APIError as e:
			return dict(error=e.error,data=e.data,message=e.message)
			
			
def add_routes(app,module_name):		
		try:
			mod=__import__(module_name, fromlist=['get_submodule'])#这个fromlist写不写都无所谓啊。。。
		except ImportError as e:
			raise e
		for attr in dir(mod): #dir(X),这个函数可以返回X的所有属性和方法，超级多
			if attr.startswith('_'):
				continue
			func=getattr(mod,attr)
			if callable(func) and hasattr(func,'__method__') and hasattr(func, '__route__'):
				args=','.join(inspect.signature(func).parameters.keys()) #keys()返回一个dict的所有键
				logging.info('add route %s %s => %s(%s)'% (func.__method__, func.__route__, func.__name__, args))
				app.router.add_route(func.__method__, func.__route__, RequestHandler(func))
				
def add_static(app):
		path1=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
		app.router.add_static('/static/', path1)
		logging.info('add static %s => %s' %('/static/', path1))
		path2=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'avatar')
		app.router.add_static('/avatar/',path2)
		logging.info('add static %s => %s' %('/avatar/', path2))
			
			
			