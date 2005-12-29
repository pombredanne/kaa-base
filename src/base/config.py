# -*- coding: iso-8859-1 -*-
import re
import copy
import locale

# find the correct encoding
try:
    ENCODING = locale.getdefaultlocale()[1]
    ''.encode(ENCODING)
except:
    ENCODING = 'latin-1'

class Var(object):
    def __init__(self, name, type='', descr=u'', default=None):
        self.name = name
        self.type = type
        self.descr = descr
        self.default = default
        self.value = default
        if type == '':
            if default == None:
                raise AttributeError('define type or default')
            self.type = default.__class__
        if not descr and hasattr(default, '_descr'):
            self.descr = default._descr
        if isinstance(self.descr, str):
            self.descr = unicode(self.descr, ENCODING, 'r')
        

    def _cfg_string(self, prefix, print_descr=True):
        if not prefix.endswith(']'):
            prefix = prefix + self.name
        if hasattr(self.value, '_cfg_string'):
            return self.value._cfg_string(prefix, print_descr)
        descr = newline = ''
        if print_descr:
            descr = '# %s\n' % self.descr.encode(ENCODING, 'r').replace('\n', '\n# ')
            newline = '\n'
        value = self.value
        if isinstance(self.value, unicode):
            # convert unicode to string
            value = self.value.encode(ENCODING, 'r')
        if self.value == self.default:
            return '%s# %s = %s%s' % (descr, prefix, value, newline)
        return '%s%s = %s%s' % (descr, prefix, value, newline)


    def _cfg_set(self, value):
        if isinstance(self.type, (list, tuple)):
            if not value in self.type:
                # This could crash, but that is ok
                value = self.type[0].__class__(value)
            if value in self.type:
                self.value = value
                return value
            raise AttributeError('Variable must be one of %s' % str(self.type))
        if not isinstance(value, self.type):
            # This could crash, but that is ok
            value = self.type(value)
        self.value = value
        return value

    
class Group(object):
    def __init__(self, schema, descr=u'', name=''):
        self._dict  = {}
        self._vars  = []
        self._descr = descr
        self._name  = name
        for data in copy.deepcopy(schema):
            if not isinstance(data, Var):
                if not data._name:
                    raise AttributeError('Inline Group needs name')
                data = Var(name=data._name, default=data)
            self._dict[data.name] = data
            self._vars.append(data.name)
        if isinstance(self._descr, str):
            self._descr = unicode(self._descr, ENCODING, 'r')
            
    def add_group(self, name, value):
        self._dict[name] = Var(name=name, default=value)
        self._vars.append(name)


    def _cfg_string(self, prefix, print_descr=True):
        ret  = []
        desc = self._descr.encode(ENCODING, 'r').replace('\n', '\n# ')
        if prefix:
            if print_descr:
                ret.append('#\n# %s\n# %s\n#\n' % (prefix, desc))
            prefix += '.'
        for name in self._vars:
            var = self._dict[name]
            ret.append(var._cfg_string(prefix, print_descr))
        return '\n'.join(ret)


    def __setattr__(self, key, value):
        if key.startswith('_'):
            return object.__setattr__(self, key, value)
        if not key in self._dict:
            raise AttributeError('No attribute %s' % key)
        self._dict[key]._cfg_set(value)


    def __getattr__(self, key):
        if key.startswith('_'):
            return object.__getattr__(self, key)
        if not key in self._dict:
            raise AttributeError('No attribute %s' % key)
        return self._dict[key].value



class Dict(object):
    def __init__(self, schema, descr=u'', name='', type=unicode):
        if not isinstance(schema, Var):
            schema = Var(name=name, default=schema)
        self._schema  = copy.deepcopy(schema)
        self._dict  = {}
        self._type  = type
        self._descr = descr
        self._name  = name
        if isinstance(self._descr, str):
            self._descr = unicode(self._descr, ENCODING, 'r')
        

    def __getitem__(self, index):
        if not isinstance(index, self._type):
            # this could crash, we don't care.
            # FIXME: but string/unicode stuff may be important here
            index = self._type(index)
        if not index in self._dict:
            self._dict[index] = copy.deepcopy(self._schema)
        return self._dict[index].value


    def __setitem__(self, index, value):
        if not isinstance(index, self._type):
            # this could crash, we don't care.
            if self._type == unicode and type(index) == str:
                index = unicode(index, ENCODING, 'r')
            elif self._type == str and type(index) == unicode:
                index = index.encode(ENCODING, 'r')
            index = self._type(index)
        if not index in self._dict:
            self._dict[index] = copy.deepcopy(self._schema)
        self._dict[index]._cfg_set(value)


    def _cfg_string(self, prefix, print_descr=True):
        ret = []
        if type(self._schema) == Var and print_descr:
            ret.append('#\n# %s\n# %s\n#\n' % \
                       (prefix, self._descr.encode(ENCODING, 'r')))
            print_descr = False

        # sort config by key names
        keys = self._dict.keys()[:]
        keys.sort()

        for key in keys:
            # get the var before we might change the key to string
            var = self._dict[key]
            if isinstance(key, unicode):
                key = key.encode(ENCODING, 'r')
            ret.append(var._cfg_string('%s[%s]' % (prefix, key), print_descr))
        if not print_descr:
            ret.append('')
        return '\n'.join(ret)

    
class List(Dict):
    def __init__(self, schema, descr=u'', name=''):
        Dict.__init__(self, schema, descr, name, int)


class Config(Group):
    def __init__(self, schema, descr=u'', name=''):
        Group.__init__(self, schema, descr, name)
        self._filename = ''
        self._bad_lines = []
        

    def save(self, filename=''):
        """
        Save file. If filename is not given, return the config as string.
        """
        if not filename:
            filename = self._filename
        if not filename:
            raise AttributeError('no file to save to')
        f = open(filename, 'w')
        f.write('# -*- coding: %s -*-\n' % ENCODING.lower())
        f.write('# *************************************************************\n')
        f.write('# This file is auto-generated\n#\n')
        f.write('# The possible variables are commented out with the default\n')
        f.write('# values. Removing lines has no effect, they will be added\n')
        f.write('# again when this file is saved again. Changing the order of\n')
        f.write('# the items will also be changed back on the next write.\n')
        if self._bad_lines:
            f.write('#\n# See the end of the file for bad lines ignored when the file\n')
            f.write('# was last saved.\n')
        f.write('# *************************************************************\n\n')
        f.write(self._cfg_string(''))
        if self._bad_lines:
            f.write('# *************************************************************\n')
            f.write('# The following lines caused some errors and were ignored\n')
            f.write('# Possible reasons are removed variables or bad configuration\n')
            f.write('# *************************************************************\n\n')
            for error in self._bad_lines:
                f.write('# %s\n%s\n\n' % error)
        f.close()


    def load(self, filename):
        self._filename = filename
        regexp = re.compile('(([a-zA-Z0-9_]+)|(\[.*?\]))')
        f = open(filename)
        for line in f.readlines():
            if line.find('#') >= 0:
                line = line[:line.find('#')]
            line = line.strip()
            if not line:
                continue
            if line.count('=') != 1:
                error = ('Unable to parse the line', line)
                if not error in self._bad_lines:
                    self._bad_lines.append(error)
                continue
            key, value = line.split('=')
            try:
                keylist = [x[0] for x in regexp.findall(key.strip()) if x[0] ]
                object = self
                while len(keylist) > 1:
                    key = keylist.pop(0)
                    if key.startswith('['):
                        object = object[key[1:-1]]
                    else:
                        object = getattr(object, key)
                key = keylist[0]
                value = value.strip()
                setattr(object, key, value)
            except Exception, e:
                error = (str(e), line)
                if not error in self._bad_lines:
                    self._bad_lines.append(error)
        f.close()
        return len(self._bad_lines) == 0
    
    
# TEST CODE

config = Config(descr='basic config group', schema=[
    Var(name='foo', descr='some text', default=5),
    Var(name='bar', default=u'bar',
        descr='more text\ndescription has two lines'),

    # group defined inside the basic schema
    Group(name='inline', descr='this is a subgroup', schema=[
    Var(name='x', descr='descr_x', default=7 ),
    Var(name='y', type=range(0,5), descr='descr_y', default=3 ) ])
    ])

# create extra group and add it to the schema
subgroup = Group(descr='this is a subgroup', schema=[
    Var(name='x', descr='descr_x with non ascii �', default=7 ),
    # the next variable allows numbers from 0-4
    Var(name='y', type=range(0,5), descr='descr_y', default=3 ) ])
config.add_group('subgroup', subgroup)

# create a group again deeper in the tree
subsubgroup = Group(descr='desrc of subsubgroup', schema=[
    Var(name='a', descr='descr a', default=3 ) ])
subgroup.add_group('z', subsubgroup)

# create a list of a group
l = List(descr='desrc of list subsubgroup', schema=Group([
    Var(name='a', type=int, descr='descr a', default=3 ),
    # z is again a group
    Group(name='z', descr='this is a subgroup', schema=[
    Var(name='x', descr='descr_x', default=7 ),
    Var(name='y', type=range(0,5), descr='descr_y', default=3 ) ]) ]))
subgroup.add_group('list', l)

# create a dict of strings
epg = Dict(descr='desrc of dict epg', schema=Var(name='a', descr='descr a', default='' ))
subgroup.add_group('epg', epg)

# store the schema up to this point, we will need it later
part_config = copy.deepcopy(config)

# create extra group and add it to the schema
subgroup = Group(descr='this is a subgroup', schema=[
    Var(name='x', descr='descr_x', default=7 ) ])
config.add_group('some_group', subgroup)

# OK, let's play with the config

print '** Test 1: change config.subgroup.list and create some errors **'
print config.subgroup.list[0].a
config.subgroup.list[0].a = 6
print config.subgroup.list[0].a

# This crashes because there is no .a
try:
    config.subgroup.list[1].z.a = 7
except Exception, e:
    print e

# This crashes because the index is no int
try:
    config.subgroup.list['foo'].z.x = 7
except Exception, e:
    print e

print config.subgroup.list[1].z.x
config.subgroup.list[1].z.x = 8
print config.subgroup.list[1].z.x

print
print '** Test 2: play with the dict **'

epg['foo'] = 'bar'
epg['x']   = 'non-ascii: �'
epg['also-non-ascii �'] = 'non-ascii: �'
epg['this.has.a.dot'] = 'something'

print epg['foo']

print
print '** Test 3: play some other variables **'

print config.foo

config.foo = 10
print config.foo
# This crashes because hello is no int
try:
    config.foo = 'hello'
except Exception, e:
    print e
print config.subgroup.x
config.subgroup.x = 10
print config.subgroup.x

print 'y', config.subgroup.y
# This crashes because 8 is not in range
try:
    config.subgroup.y = 8
except AttributeError, e:
    print e
print 'y', config.subgroup.y
config.subgroup.y = 2
print 'y', config.subgroup.y

try:
    config.not_there
except Exception, e:
    print e

config.some_group.x = 1

print
print '** Test 4: save and reload **'
    
print 'config.subgroup.z.a is', config.subgroup.z.a
print 'set to 5'
config.subgroup.z.a = 5
print 'config.subgroup.z.a is', config.subgroup.z.a

print 'save config to filename config.test'
config.save('config.test')
print 'change config object'
config.subgroup.z.a = 6
print 'config.subgroup.z.a is', config.subgroup.z.a
print 'read config file into new object'
if not config.load('config.test'):
    print 'load error, bad lines saved, not expected'
print 'config.subgroup.z.a is', config.subgroup.z.a
print 'load again in incomplete schema'
if not part_config.load('config.test'):
    print 'load error, bad lines saved as expected'
part_config.save('config.test2')