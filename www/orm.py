#!/usr/bin python3
# -*- coding: utf-8 -*-
import asyncio, logging
import aiomysql
#可参考http://lib.csdn.net/snippet/python/47292
#logging.basicConfig(level=logging.WARNING) #其实orm框架的logging级别设定会被app.py中的设定给覆盖掉
#正常情况下执行完sql语句后返回的是内tuple外list的二元组合（不知道是否还有别的情况）
''' 
	关闭event loop前先关闭连接池 
	即loop.close()前，先进行conn.close() or __pool.close() （因为with (await __pool) as conn）
	当然了，别忘了关闭游标。游标是在连接池之前就已经关闭的。
	async&await真的可以和@asyncio.coroutine&yield from替换使用，如果有问题，可能是库的版本老了
	反引号的作用是把一段字符串变成机器能够编译的代码
	python3已经不支持反引号了，这个文件里的反引号是写给mysql看的。
'''
def log(sql, args=()):
	logging.info('SQL: %s' %(sql))

async def create_pool(loop, **kw):#**kw的逻辑就是，你给我传进来一个kw包，我不管里面有什么，有多少，我只管用kw.get在里面找东西。真牛逼。
	logging.info('create database connection pool...')
	global __pool
	__pool=await aiomysql.create_pool(
			host=kw.get('host', 'localhost'),
			user=kw['user'],
			password=kw['password'],
			db=kw['db'],
			port=kw.get('port',3306),
			charset=kw.get('charset','utf8'),#not utf-8!
			autocommit=kw.get('autocommit', True),
			maxsize=kw.get('maxsize',10),
			minsize=kw.get('minisize',1),
			loop=loop
			)

async def destory_pool():
	global __pool
	if __pool is not None:
		__pool.close()#这个不是协程,不用await
		await __pool.wait_closed()
			
async def select(sql, args, size=None):
	log(sql, args)
	global __pool
	with (await __pool) as conn: #这个with会对conn进行conn.acquire()和conn.release()，并不是.close()
		cur=await conn.cursor(aiomysql.DictCursor)
		await cur.execute(sql.replace('?','%s'), args or ()) #这里execute语句的写法，看有道云笔记
		if size:
			rs=await cur.fetchmany(size)
		else:
			rs=await cur.fetchall()
		await cur.close()
		logging.info('rows return: %s' %(len(rs)))
		return rs #由于是DictCursor，所以这里rs是个dict
		
async def execute(sql, args,autocommit=True):  #conn.commit:Commit changes to stable storage coroutine.
	log(sql)								   #就是说，只有insert，update，delete这种改动语句才需要commit，select类似于查询语句，没有改动，不需要commit
	global __pool							   #先cur.close(),再conn.commit(),再conn.close()
	with (await __pool) as conn:				#但是话说回来了，正式上线的网站不需要关闭和数据库的连接，所以我也没有写conn.close()的代码。commit也没写是因为autocommit了
		try:
			cur=await conn.cursor()
			await cur.execute(sql.replace('?','%s'),args)
			affectedLine=cur.rowcount
			await cur.close()
		except BaseException as e:
			raise
		return affectedLine
		
def create_args_string(num):
	L=[]
	for n in range(num):
		L.append('?')
	return (','.join(L))
	
class Field(object):
	def __init__(self,name,column_type,primary_key,default):
		self.name=name
		self.column_type=column_type
		self.primary_key=primary_key
		self.default=default
		
	def __str__(self):
		return('<%s, %s: %s>' %(self.__class__.__name__, self.column_type, self.name))
		
class StringField(Field):
	def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(100)'):
		super().__init__(name, ddl, primary_key, default) #This does the same thing: super(StringField,self).__init__()
	
class BooleanField(Field):
	def __init__(self, name=None, default=None):
		super().__init__(name, 'boolean', False, default)
		
class IntegerField(Field):
	def __init__(self, name=None, primary_key=False,  default=0):
		super().__init__(name, 'bigint', primary_key, default)
	
class FloatField(Field):
	def __init__(self, name=None, primary_key=False,  default=0.0):
		super().__init__(name, 'real', primary_key, default)
			
class TextField(Field):
	def __init__(self, name=None, default=None):
		super().__init__(name, 'Text', False, default)
		
class ModelMetaclass(type):
	def __new__(cls, name, bases, attrs):
		if name=='Model':
			return type.__new__(cls,name,bases,attrs)
		tableName=attrs.get('__table__', None) or name
		logging.info('found model: %s (table: %s)' % (name, tableName))
		mappings=dict()
		fields=[]
		primaryKey=None
		for k,v in attrs.items():
			if isinstance(v,Field):
				logging.info('found mapping:%s --> %s' % (k,v))
				mappings[k]=v
				if v.primary_key:
					if primaryKey:
						raise RuntimeError('Duplicate primary key for field: %s' % k)
					primaryKey=k
				else:
					fields.append(k)		
		if not primaryKey:
			raise RuntimeError('Primary key is not found')
		for k in mappings.keys():
			attrs.pop(k)
		escaped_fields=list(map(lambda f:'`%s`' %f, fields))
		attrs['__mappings__']=mappings
		attrs['__table__']==tableName
		attrs['__primary_key__']=primaryKey #这个是主键所在列的列名
		attrs['__fields__']=fields#这个是除了主键以外的其他列的列名
		attrs['__select__']='select `%s`, %s from `%s`' % (primaryKey, ','.join(escaped_fields),tableName)
		attrs['__insert__']='insert into `%s` (%s, `%s`) values (%s)' %(tableName,','.join(escaped_fields),primaryKey, create_args_string(len(escaped_fields)+1))
		attrs['__update__']='update `%s` set %s where `%s`=?' % (tableName, ','.join(map(lambda f:'`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
		attrs['__delete__']='delete from `%s` where `%s`=?' % (tableName, primaryKey)
		return type.__new__(cls, name, bases, attrs)
		
class Model(dict,metaclass=ModelMetaclass):
	def __init__(self, **kw):
		super(Model, self).__init__(**kw)
	
	def __getattr__(self, key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r'"Model" object has no attribute: %s' % key)
			
	def __setattr__(self,key,value):
		self[key]=value
		
	def getValue(self,key):
		return getattr(self,key,None)
	
	def getValueOrDefault(self,key):
		#用户输入的数据，是由这个函数拿到的。用户创建实例时，传入的dict被**kw接收，
		#然后由于Model本身继承自dict，所以直接self[key]就能拿到用户输入的实实在在的数据
		value=getattr(self,key,None) #value=self[key],这个self是用户自己创建的，比如u=User(name=...,email=...),而User继承自Model
		if value is None:  #这个if就是用来获取默认值的，如果用户输入值了，就直接return value
			field=self.__mappings__[key]
			if field.default: #有毒...如果把admin的default设置成False，那么这里的判断进不来...所以admin别设置默认值了
				value=field.default() if callable(field.default) else field.default
				logging.debug('using default value for %s: %s' % (key, str(value)))
				setattr(self,key,value)
		return value

	@classmethod
	async def findAll(cls, where=None, args=None, **kw):
		'''find objects by where clause'''
		sql=[cls.__select__]
		if where:
			sql.append('where ')
			sql.append(where)
		if args is None:
			args=[]
		orderBy=kw.get('orderBy',None)
		if orderBy:
			sql.append('order by ')
			sql.append(orderBy)
		limit=kw.get('limit',None)
		if limit is not None:
			sql.append('limit ')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit)==2:
				sql.append('?,?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value: %s' %str(limit))
		rs=await select(''.join(sql),args)
		return [cls(**r) for r in rs]#懂了。就好像user=User(id=....)后user是User的实例一样，这里返回去的也必须是元类的实例，这样才可以用cls里的各种函数
		#这种返回cls的函数。。。他们返回的居然是类，不是实例。。。这里返回的list里是一堆类？都是同一种类，名字也一样，但是内容不一样。。。
		#其实这里就直接看作返回了一堆dict（{'id'='','name'=''...}）就行了。。而这个dict同时又是个类，所以可以用点(.)来获取属性
	@classmethod
	async def findNumber(cls,selectField,where=None,args=None):
		'''find number by select and where.'''
		sql=['select %s __num__ from `%s`' %(selectField, cls.__table__)]
		if where:
			sql.append('where ')
			sql.append(where)
		rs=await select(''.join(sql),args,1)
		if len(rs)==0:
			return None
		return rs[0]['__num__']
		
	@classmethod
	async def find(cls,primarykey):
		'''find object by primary key'''
		rs=await select('%s where `%s`=?' %(cls.__select__, cls.__primary_key__),[primarykey],1)
		if len(rs)==0:
			return None
		return cls(**rs[0]) 
	'''为什么上面三种find方法需要定义成类方法？
	   答：因为需要用到cls.的属性，呃
	'''	
	
	'''
	懂了懂了，下面这三个self的方法，类就不能用，只有实例可以使用。比如注册用户的时候，用户的数据是储存在user=User()里的，当然可以user.save()了，但你见过User.save()的嘛？
	而且上面三个方法，都是查找类型的，查找当然不需要创建一个实例了，又不需要改动，创建实例干嘛。
	所以其实上面三个函数返回实例应该也是可以的，但是没必要，从逻辑上来说画蛇添足了
	'''
	async def save(self):
		args=list(map(self.getValueOrDefault,self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows=await execute(self.__insert__,args)
		if rows!=1:
			logging.warn('failed to insert record: affected rows: %s' %rows)
			
	async def update(self):
		args=list(map(self.getValue,self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows=await execute(self.__update__,args)
		if rows !=1:
			logging.warn('failed to update by primary key:affected rows: %s' % rows)
	
	async def remove(self):
		args=[self.getValue(self.__primary_key__)]
		rows=await execute(self.__delete__,args)
		if rows!=1:
			logging.warn('failed to remove by primary key:affected rows: %s' % rows)
			
		